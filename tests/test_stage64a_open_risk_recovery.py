"""Stage 6.4A — idempotent open-risk recovery on reconcile (mocked + static)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
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


@pytest.mark.asyncio
async def test_reconcile_recovers_missing_open_risk_once():
    """B: lifecycle has risk_usd, ticket live, open_risk_applied=False → recover."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False, state="BROKER_CONFIRMED_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(
            session, "ACC-1", [{"position_ticket": 1001, "ticket": 1001}]
        )
    assert summary["open_risk_recovered"] == 25.0
    assert row.open_risk_applied is True
    assert "sig-1" in summary["recovered_signal_ids"]


@pytest.mark.asyncio
async def test_reconcile_second_pass_no_double_record():
    """C: already applied → zero recovery."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=True, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(
            session, "ACC-1", [{"position_ticket": 1001}]
        )
    assert summary["open_risk_recovered"] == 0.0


@pytest.mark.asyncio
async def test_reconcile_closed_position_no_restore():
    """F: ticket absent → release path; no recovery increment."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=True, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [])  # no live tickets
    assert summary["open_risk_recovered"] == 0.0
    assert summary["stale_risk_released"] == 25.0
    assert row.state == "RISK_RELEASED"


@pytest.mark.asyncio
async def test_reconcile_never_applied_absent_no_false_release():
    """Absent ticket + never applied → no portfolio release amount."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(session, "ACC-1", [])
    assert summary["stale_risk_released"] == 0.0
    assert row.state == "RISK_RELEASED"


@pytest.mark.asyncio
async def test_reconcile_missing_risk_amount_no_invent():
    """H: no risk_usd_at_open → no recovery amount."""
    svc = DurableLifecycleService()
    row = _row(risk_usd_at_open=None, open_risk_applied=False, state="BROKER_CONFIRMED_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[row])):
        summary = await svc.reconcile(
            session, "ACC-1", [{"position_ticket": 1001}]
        )
    assert summary["open_risk_recovered"] == 0.0


@pytest.mark.asyncio
async def test_reconcile_unknown_ticket_no_invent():
    """G: broker ticket with no durable row → unknown list, no recovery."""
    svc = DurableLifecycleService()
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    with patch.object(svc, "list_open_for_update", new=AsyncMock(return_value=[])):
        summary = await svc.reconcile(
            session, "ACC-1", [{"position_ticket": 9999}]
        )
    assert 9999 in summary["unknown_broker_tickets"]
    assert summary["open_risk_recovered"] == 0.0


@pytest.mark.asyncio
async def test_on_close_no_release_if_never_applied():
    """I: close without prior portfolio apply → amount None."""
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False, risk_usd_at_open=40.0, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    amount, status = await svc.on_close(
        session, account_id="ACC-1", signal_id="sig-1", position_ticket=1001, symbol="EURUSD", close_reason="test"
    )
    assert amount is None
    assert status == "RISK_RELEASED"
    assert row.state == "RISK_RELEASED"


@pytest.mark.asyncio
async def test_on_close_releases_when_applied():
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=True, risk_usd_at_open=40.0, state="POSITION_OPEN")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    amount, status = await svc.on_close(
        session, account_id="ACC-1", signal_id="sig-1", position_ticket=1001, symbol="EURUSD", close_reason="test"
    )
    assert amount == 40.0
    assert status == "RISK_RELEASED"


@pytest.mark.asyncio
async def test_mark_risk_recorded_sets_flag():
    svc = DurableLifecycleService()
    row = _row(open_risk_applied=False, state="ORDER_SENT", risk_usd_at_open=None)
    session = MagicMock()
    session.flush = AsyncMock()
    with patch.object(svc, "_get", new=AsyncMock(return_value=row)):
        await svc.mark_risk_recorded(session, account_id="ACC-1", signal_id="sig-1", risk_usd=12.5)
    assert row.open_risk_applied is True
    assert row.state == "POSITION_OPEN"
    assert row.risk_usd_at_open == 12.5


def test_production_authorized_false():
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_migration_0023_exists():
    from pathlib import Path

    p = Path("backend/alembic/versions/0023_lifecycle_open_risk_applied.py")
    assert p.is_file()
    assert "open_risk_applied" in p.read_text()
    assert "0022_aegis_executor_presence" in p.read_text()


def test_no_claim_on_deliver_in_this_phase():
    """Stage 6.4A must not wire claim()."""
    from pathlib import Path

    router = Path("backend/app/api/executor_router.py").read_text()
    assert ".claim(" not in router
