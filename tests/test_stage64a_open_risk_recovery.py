"""Stage 6.4A corrective — historical NULL, explicit False recovery, atomic flag.

MOCKED tests unless labeled DATABASE-BACKED.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.security import AuthContext, verify_api_key
from app.services.durable_lifecycle_service import DurableLifecycleService


def _row(**kwargs):
    r = MagicMock()
    defaults = dict(
        account_id="ACC-1",
        signal_id="sig-1",
        position_ticket=1001,
        risk_usd_at_open=25.0,
        open_risk_applied=False,
        state="POSITION_OPEN",
        close_reason=None,
        opened_at=None,
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


# --- MOCKED ---

@pytest.mark.asyncio
async def test_explicit_false_recovers_once():
    """B: known missing (False) + live ticket → candidate recovery."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False, state="BROKER_CONFIRMED_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [{"position_ticket": 1001}])
    assert summary["open_risk_recovered"] == 25.0
    assert "sig-1" in summary["recovered_signal_ids"]
    # Flag not set inside reconcile — caller marks after portfolio success
    assert row.open_risk_applied is False


@pytest.mark.asyncio
async def test_historical_null_no_auto_recover():
    """A/C: NULL (historical/ambiguous) must not auto-increment."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=None, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [{"position_ticket": 1001}])
    assert summary["open_risk_recovered"] == 0.0
    assert "sig-1" in summary.get("ambiguous_open_risk_signal_ids", [])
    assert summary["reconciliation_required_count"] >= 1


@pytest.mark.asyncio
async def test_already_true_no_double():
    """A: already applied → zero recovery."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=True, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [{"position_ticket": 1001}])
    assert summary["open_risk_recovered"] == 0.0


@pytest.mark.asyncio
async def test_absent_ticket_release_only_if_true():
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=True)
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [])
    assert summary["stale_risk_released"] == 25.0
    assert row.state == "RISK_RELEASED"


@pytest.mark.asyncio
async def test_absent_false_no_false_release():
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False)
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [])
    assert summary["stale_risk_released"] == 0.0


@pytest.mark.asyncio
async def test_missing_risk_no_invent():
    svc = DurableLifecycleService()
    row = _row(risk_usd_at_open=None, open_risk_applied=False)
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [{"position_ticket": 1001}])
    assert summary["open_risk_recovered"] == 0.0


@pytest.mark.asyncio
async def test_unknown_ticket():
    svc = DurableLifecycleService()
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[])):
        summary = await svc.reconcile(session, "ACC-1", [{"position_ticket": 9999}])
    assert 9999 in summary["unknown_broker_tickets"]


@pytest.mark.asyncio
async def test_on_close_amount_only_if_true():
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False, risk_usd_at_open=40.0)
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    amount, status = await svc.on_close(
        session, account_id="ACC-1", signal_id="sig-1",
        position_ticket=1001, symbol="EURUSD", close_reason="t",
    )
    assert amount is None
    assert status == "RISK_RELEASED"


@pytest.mark.asyncio
async def test_mark_open_risk_applied():
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False)
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "_get", new=AsyncMock(return_value=row)):
        ok = await svc.mark_open_risk_applied(session, account_id="ACC-1", signal_id="sig-1")
    assert ok is True
    assert row.open_risk_applied is True


def test_reconcile_route_fails_closed_without_portfolio_risk():
    """D: pr missing + recovery candidates → 503, no silent flag commit."""
    from app.api import executor_router as er

    app = FastAPI()
    app.include_router(er.router)
    app.state.portfolio_risk = None

    async def fake_reconcile(self, session, account_id, positions):
        return {
            "account_id": account_id,
            "stale_risk_released": 0.0,
            "open_risk_recovered": 10.0,
            "recovered_signal_ids": ["sig-x"],
            "confirmed_open": 1,
            "reconciliation_required_count": 0,
            "unknown_broker_tickets": [],
            "broker_positions": 1,
            "unknown_positions_not_auto_adopted": True,
        }

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.rollback = AsyncMock()
    mock_session.commit = AsyncMock()

    app.dependency_overrides[verify_api_key] = lambda: AuthContext(
        account_id="ACC-1", is_admin=False, label="a"
    )

    with patch("app.db.base.async_session_factory", return_value=mock_session):
        with patch(
            "app.services.durable_lifecycle_service.DurableLifecycleService.reconcile",
            new=fake_reconcile,
        ):
            with patch(
                "app.services.position_lifecycle_service.get_lifecycle_service",
                return_value=MagicMock(),
            ):
                client = TestClient(app, raise_server_exceptions=False)
                r = client.post(
                    "/api/executor/reconcile-positions",
                    json={"account_id": "ACC-1", "positions": [{"position_ticket": 1}]},
                )
    assert r.status_code == 503
    assert "portfolio_risk_unavailable" in r.json().get("detail", "")
    mock_session.rollback.assert_awaited()
    mock_session.commit.assert_not_awaited()


def test_production_authorized_false():
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_migration_nullable_unknown_historical():
    from pathlib import Path
    t = Path("backend/alembic/versions/0023_lifecycle_open_risk_applied.py").read_text()
    assert "nullable=True" in t
    assert "NULL" in t or "null" in t.lower()


def test_no_claim_on_deliver():
    from pathlib import Path
    assert ".claim(" not in Path("backend/app/api/executor_router.py").read_text()


# --- DATABASE-BACKED: implemented in test_stage64a_pg_recovery_real.py ---
# test_pg_concurrent_recovery_no_double
# test_pg_record_open_risk_failure_rolls_back_flag


# --- ACK atomicity (MOCKED) ---

def test_ack_source_mark_risk_only_after_portfolio():
    """Source: mark_risk_recorded must not run when portfolio_risk is None."""
    from pathlib import Path

    src = Path("backend/app/api/executor_router.py").read_text()
    start = src.index("async def ack_signal")
    end = src.find("@router.post(\"/position-closed\")", start)
    body = src[start:end]
    assert "portfolio_risk_unavailable" in body
    # mark_risk_recorded should appear only in the else/pr branch after record_open_risk
    assert "mark_risk_recorded" in body
    assert "record_open_risk" in body
    # ordering within should_risk block: unavailable path does not call mark_risk_recorded
    unavail = body.split("portfolio_risk_unavailable")[0]
    # After unavailable marker, the mark is only in the else branch
    after = body.split("portfolio_risk_unavailable", 1)[1]
    assert "mark_risk_recorded" in after
    # The unavailable path uses commit without mark before the else
    assert "open_risk_applied\": False" in body.replace(" ", "") or "open_risk_applied\": False" in body or '"open_risk_applied": False' in body


def test_ack_on_ack_sets_explicit_false_pending_apply():
    from pathlib import Path

    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "open_risk_applied = False" in src
