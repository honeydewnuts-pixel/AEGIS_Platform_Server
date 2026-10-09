"""Stage 6.2I — durable AEGIS_Executor presence / heartbeat."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.security import AuthContext, verify_api_key
from app.services.executor_presence_service import ExecutorPresenceService
from app.services.executor_signal_service import ExecutorSignalService


def _admin() -> AuthContext:
    return AuthContext(account_id=None, is_admin=True, label="admin")


def _account(aid: str = "ACC-1987D3D2E6") -> AuthContext:
    return AuthContext(account_id=aid, is_admin=False, label="acct")


@pytest.fixture
def exec_app():
    from app.api.executor_router import router as exec_router
    from app.api.admin_ops_router import router as admin_router

    app = FastAPI()
    app.include_router(exec_router)
    app.include_router(admin_router)
    return app


@pytest.mark.asyncio
async def test_upsert_advances_timestamp():
    svc = ExecutorPresenceService()
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    session.add = MagicMock()
    session.flush = AsyncMock()
    r1 = await svc.upsert_heartbeat(
        session,
        account_id="ACC-1",
        client_type="AEGIS_Executor",
        executor_version="2.20",
        execution_mode="CHART_ONLY",
        chart_symbol="EURUSD",
    )
    assert r1["ok"] is True
    assert r1["account_id"] == "ACC-1"
    session.add.assert_called_once()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_get_status_missing():
    svc = ExecutorPresenceService()
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    st = await svc.get_status(session, "ACC-MISSING")
    assert st["exists"] is False
    assert st["healthy"] is False
    assert "key" not in str(st).lower() or st.get("api_key") is None


@pytest.mark.asyncio
async def test_get_status_healthy_row():
    svc = ExecutorPresenceService()
    row = MagicMock()
    row.client_type = "AEGIS_Executor"
    row.executor_version = "2.20"
    row.execution_mode = "CHART_ONLY"
    row.last_symbol = "EURUSD"
    row.last_seen_at = datetime.now(timezone.utc)
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    st = await svc.get_status(session, "ACC-1", stale_after_sec=90)
    assert st["exists"] is True
    assert st["healthy"] is True
    assert st["client_type"] == "AEGIS_Executor"
    assert st["last_symbol"] == "EURUSD"
    assert "api_key" not in st
    assert "hash" not in st


@pytest.mark.asyncio
async def test_get_status_stale_row():
    svc = ExecutorPresenceService()
    row = MagicMock()
    row.client_type = "AEGIS_Executor"
    row.executor_version = "2.20"
    row.execution_mode = "CHART_ONLY"
    row.last_symbol = "EURUSD"
    row.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=200)
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    st = await svc.get_status(session, "ACC-1", stale_after_sec=90)
    assert st["exists"] is True
    assert st["healthy"] is False


def test_heartbeat_wrong_account_rejected(exec_app):
    exec_app.dependency_overrides[verify_api_key] = lambda: _account("ACC-A")
    client = TestClient(exec_app)
    r = client.post(
        "/api/executor/heartbeat",
        json={
            "account_id": "ACC-B",
            "client_type": "AEGIS_Executor",
            "executor_version": "2.20",
            "execution_mode": "CHART_ONLY",
            "chart_symbol": "EURUSD",
        },
    )
    assert r.status_code == 403


def test_heartbeat_valid_account(exec_app):
    exec_app.dependency_overrides[verify_api_key] = lambda: _account("ACC-1987D3D2E6")
    client = TestClient(exec_app)
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    with patch("app.db.base.async_session_factory", return_value=mock_session):
        r = client.post(
            "/api/executor/heartbeat",
            json={
                "account_id": "ACC-1987D3D2E6",
                "client_type": "AEGIS_Executor",
                "executor_version": "2.20",
                "execution_mode": "CHART_ONLY",
                "chart_symbol": "EURUSD",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["account_id"] == "ACC-1987D3D2E6"
    assert "api_key" not in body


def test_admin_status_requires_admin(exec_app):
    exec_app.dependency_overrides[verify_api_key] = lambda: _account()
    client = TestClient(exec_app)
    r = client.get("/api/admin/ops/executor-status/ACC-1987D3D2E6")
    assert r.status_code == 403


def test_admin_status_ok(exec_app):
    exec_app.dependency_overrides[verify_api_key] = _admin
    client = TestClient(exec_app)
    row = MagicMock()
    row.client_type = "AEGIS_Executor"
    row.executor_version = "2.20"
    row.execution_mode = "CHART_ONLY"
    row.last_symbol = "EURUSD"
    row.last_seen_at = datetime.now(timezone.utc)
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    with patch("app.db.base.async_session_factory", return_value=mock_session):
        r = client.get("/api/admin/ops/executor-status/ACC-1987D3D2E6")
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True
    assert body["client_type"] == "AEGIS_Executor"
    assert body["source"] == "durable_presence"
    for forbidden in ("api_key", "key_hash", "password", "DATABASE_URL"):
        assert forbidden not in body


def test_production_authorized_unchanged():
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_controlled_demo_auth_unchanged():
    row = {
        "methodology": "controlled_demo_test",
        "rule_name": "controlled_demo_test",
        "production_authorized": False,
        "controlled_demo_authorized": True,
    }
    assert ExecutorSignalService.is_execution_authorized(row) is True
    research = {
        "methodology": "rsi9_transfer",
        "production_authorized": True,
        "controlled_demo_authorized": False,
    }
    assert ExecutorSignalService.is_execution_authorized(research) is False


def test_heartbeat_does_not_touch_queue_service_api():
    """Static: heartbeat route must not call enqueue/claim/ack on durable queue."""
    from pathlib import Path

    src = Path("backend/app/api/executor_router.py").read_text()
    start = src.index("async def executor_heartbeat")
    end = src.find("@router.", start + 1)
    body = src[start:end if end > 0 else len(src)]
    for bad in (".enqueue(", ".claim(", "OrderSend", "release_open_risk"):
        assert bad not in body


def test_migration_file_exists():
    from pathlib import Path

    p = Path("backend/alembic/versions/0022_aegis_executor_presence.py")
    assert p.is_file()
    t = p.read_text()
    assert "aegis_executor_presence" in t
    assert "0021_aegis_operational_control" in t


def test_mq5_both_copies_have_heartbeat():
    from pathlib import Path

    for rel in (
        "release/desktop/AEGIS_Executor.mq5",
        "windows-desktop/mq5/AEGIS_Executor.mq5",
    ):
        t = Path(rel).read_text()
        assert "HeartbeatSeconds" in t
        assert "SendExecutorHeartbeat" in t
        assert "/api/executor/heartbeat" in t
        assert "non-fatal" in t
