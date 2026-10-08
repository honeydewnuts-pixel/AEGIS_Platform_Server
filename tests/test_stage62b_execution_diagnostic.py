"""Stage 6.2B — read-only execution-queue diagnostic endpoint.

Uses FastAPI router isolation where possible so tests do not require full
app stack (OpenCV / OTEL / etc.) in minimal environments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.security import AuthContext, verify_api_key


def _admin_auth() -> AuthContext:
    return AuthContext(account_id=None, is_admin=True, label="test-admin")


def _account_auth() -> AuthContext:
    return AuthContext(account_id="ACC-1", is_admin=False, label="test-acct")


@pytest.fixture
def diag_app():
    from app.api.admin_ops_router import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def admin_client(diag_app):
    diag_app.dependency_overrides[verify_api_key] = _admin_auth
    return TestClient(diag_app)


def _fake_row(**overrides):
    row = MagicMock()
    row.signal_id = "9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
    row.status = "PENDING"
    row.account_id = "ACC-1987D3D2E6"
    row.symbol = "EURUSD"
    row.side = "SELL"
    row.volume = 0.01
    row.methodology = "controlled_demo_test"
    row.rule_name = "controlled_demo_test"
    row.production_authorized = False
    row.controlled_demo_authorized = True
    row.created_at = datetime(2026, 10, 8, 8, 0, 0, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 10, 8, 8, 0, 0, tzinfo=timezone.utc)
    row.claimed_at = None
    row.attempt_count = 0
    row.claim_token = None
    row.ack_ok = None
    row.ack_message = None
    row.position_ticket = None
    row.order_ticket = None
    row.deal_ticket = None
    row.stop_loss = None
    row.take_profit = None
    row.confidence = 0.0
    row.details = "controlled_demo_test"
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


def _mock_session(row):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = MagicMock()
    mock_session.flush = MagicMock()
    return mock_session


def test_admin_can_read_existing_signal(admin_client):
    row = _fake_row()
    session = _mock_session(row)
    with patch("app.db.base.async_session_factory", return_value=session):
        r = admin_client.get(
            "/api/admin/ops/execution-diagnostic/9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["exists"] is True
    assert body["signal_id"] == "9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
    assert body["status"] == "PENDING"
    assert body["account_id"] == "ACC-1987D3D2E6"
    assert body["symbol"] == "EURUSD"
    assert body["side"] == "SELL"
    assert body["volume"] == 0.01
    assert body["attempt_count"] == 0
    assert body["claimed_at"] is None
    assert body["production_authorized"] is False
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_unknown_signal_not_found(admin_client):
    session = _mock_session(None)
    with patch("app.db.base.async_session_factory", return_value=session):
        r = admin_client.get("/api/admin/ops/execution-diagnostic/does-not-exist-0000")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["exists"] is False
    assert body["signal_id"] == "does-not-exist-0000"
    session.commit.assert_not_called()


def test_unauthorized_account_key_rejected(diag_app):
    diag_app.dependency_overrides[verify_api_key] = _account_auth
    client = TestClient(diag_app)
    r = client.get(
        "/api/admin/ops/execution-diagnostic/9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
    )
    assert r.status_code == 403


def test_no_api_key_rejected(diag_app):
    # No override — verify_api_key will demand header
    client = TestClient(diag_app)
    r = client.get(
        "/api/admin/ops/execution-diagnostic/9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
    )
    assert r.status_code in (401, 403, 422)


def test_production_authorized_still_false():
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_diagnostic_does_not_mutate_status_fields(admin_client):
    row = _fake_row(status="PENDING", attempt_count=0)
    session = _mock_session(row)
    with patch("app.db.base.async_session_factory", return_value=session):
        r1 = admin_client.get(
            "/api/admin/ops/execution-diagnostic/9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
        )
        r2 = admin_client.get(
            "/api/admin/ops/execution-diagnostic/9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b"
        )
    assert r1.json()["status"] == r2.json()["status"] == "PENDING"
    assert r1.json()["attempt_count"] == r2.json()["attempt_count"] == 0
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_endpoint_source_is_read_only():
    """Static check: diagnostic handler must not call mutating queue methods."""
    from pathlib import Path

    src = Path("backend/app/api/admin_ops_router.py").read_text()
    # Isolate the diagnostic function body
    assert "execution-diagnostic" in src
    start = src.index("async def execution_diagnostic")
    end = src.find("@router.", start + 1)
    body = src[start : end if end > 0 else len(src)]
    for forbidden in (
        ".enqueue(",
        ".claim(",
        ".ack(",
        ".reject(",
        "OrderSend",
        "release_open_risk",
        "session.commit(",
        "session.flush(",
    ):
        assert forbidden not in body, f"mutating call found: {forbidden}"
