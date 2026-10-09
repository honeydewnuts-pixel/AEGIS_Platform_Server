"""Stage 6.3 — durable ACK authority and no memory/durable divergence."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.security import AuthContext, verify_api_key
from app.services.executor_signal_service import ExecutorSignalService


def _acct(aid: str = "ACC-1") -> AuthContext:
    return AuthContext(account_id=aid, is_admin=False, label="a")


@pytest.fixture
def app_with_svc():
    from app.api.executor_router import router

    app = FastAPI()
    app.include_router(router)
    app.state.executor_signals = ExecutorSignalService()
    # queue a pending signal in memory
    sid = app.state.executor_signals.publish(
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        confidence=0.8,
        rule_name="controlled_demo_test",
        volume=0.01,
        methodology="controlled_demo_test",
        production_authorized=False,
        controlled_demo_authorized=True,
    )
    app.state._test_signal_id = sid
    return app


def test_production_authorized_still_false():
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_ack_durable_failure_does_not_complete_memory(app_with_svc):
    """If durable ACK raises, memory must remain incomplete and HTTP 503."""
    app = app_with_svc
    app.dependency_overrides[verify_api_key] = lambda: _acct("ACC-1")
    client = TestClient(app)

    with patch("app.db.base.async_session_factory") as fac:
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.commit = AsyncMock(side_effect=RuntimeError("db down"))
        # Durable ack path will call get_durable_execution_queue().ack then commit
        fac.return_value = session
        with patch(
            "app.services.durable_execution_queue.DurableExecutionQueueService.ack",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ):
            r = client.post(
                "/api/executor/ack",
                json={
                    "account_id": "ACC-1",
                    "signal_id": app.state._test_signal_id,
                    "ok": True,
                    "position_ticket": 123,
                    "symbol": "EURUSD",
                    "side": "SELL",
                    "volume": 0.01,
                },
            )
    assert r.status_code == 503
    assert "durable_ack_failed" in r.json().get("detail", "")
    # Memory should still have pending or not be in completed
    svc: ExecutorSignalService = app.state.executor_signals
    assert app.state._test_signal_id not in svc._completed


def test_ack_source_orders_durable_before_memory():
    """Static source order: durable_execution_queue.ack appears before svc.ack in handler."""
    from pathlib import Path

    src = Path("backend/app/api/executor_router.py").read_text()
    start = src.index("async def ack_signal")
    end = src.find("@router.", start + 10)
    body = src[start:end]
    i_dur = body.find("get_durable_execution_queue().ack")
    i_mem = body.find("svc.ack(")
    assert i_dur > 0 and i_mem > 0
    assert i_dur < i_mem, "durable ACK must run before in-memory svc.ack"


def test_pending_authorized_true_for_controlled_demo(app_with_svc):
    app = app_with_svc
    app.dependency_overrides[verify_api_key] = lambda: _acct("ACC-1")
    client = TestClient(app)

    # Memory path only — no durable needed
    with patch("app.db.base.async_session_factory") as fac:
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        fac.return_value = session
        # Registry: allow EURUSD
        reg = MagicMock()
        reg.list_instruments.return_value = [
            {"instrument": "EURUSD", "good": True, "tradeable": True, "router_status": "ok"}
        ]
        app.state.registry = reg
        app.state.registry_service = reg
        r = client.get("/api/executor/pending", params={"account_id": "ACC-1", "symbol": "EURUSD"})
    assert r.status_code == 200
    body = r.json()
    if body.get("has_signal"):
        assert body.get("authorized") is True
        assert body.get("production_authorized") is False
        assert body.get("controlled_demo_authorized") is True


def test_research_still_blocked():
    row = {
        "methodology": "rsi9_transfer",
        "rule_name": "rsi9",
        "production_authorized": True,
        "controlled_demo_authorized": False,
    }
    assert ExecutorSignalService.is_execution_authorized(row) is False
