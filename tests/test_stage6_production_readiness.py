"""Stage 6 — production readiness, governance, emergency stop (no strategy promotion)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.services.executor_signal_service import ExecutorSignalService
from app.services.operational_control_service import OperationalControlService, KEY_EMERGENCY_STOP


def test_production_authorized_always_false_by_default():
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_research_cannot_execute():
    for meth in ("v53_6", "rsi9_transfer", "native_discovery", "generation3_x"):
        assert ExecutorSignalService.is_execution_authorized({
            "methodology": meth,
            "production_authorized": True,
            "controlled_demo_authorized": True,
            "rule_name": meth,
        }) is False


def test_controlled_demo_buy_sell_authorized():
    for side in ("BUY", "SELL"):
        row = {
            "methodology": "controlled_demo_test",
            "rule_name": "controlled_demo_test",
            "controlled_demo_authorized": True,
            "production_authorized": False,
            "side": side,
        }
        assert ExecutorSignalService.is_execution_authorized(row) is True


@pytest.mark.asyncio
async def test_emergency_stop_set_and_read():
    svc = OperationalControlService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    # get: no row
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    session.execute.return_value = res
    assert await svc.is_emergency_stop_on(session) is False
    out = await svc.set_emergency_stop(session, enabled=True, actor="test")
    assert out["emergency_stop"] is True
    assert out["production_authorized"] is False
    session.add.assert_called()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_emergency_stop_does_not_set_production():
    svc = OperationalControlService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    session.execute.return_value = res
    out = await svc.set_emergency_stop(session, enabled=False, actor="test")
    assert out["production_authorized"] is False


def test_migration_0021_exists():
    from pathlib import Path
    p = Path("backend/alembic/versions/0021_aegis_operational_control.py")
    assert p.is_file()
    assert "aegis_operational_control" in p.read_text()


def test_model_operational_control():
    from app.db.models import AegisOperationalControl
    assert AegisOperationalControl.__tablename__ == "aegis_operational_control"


def test_stage5_durable_still_present():
    from pathlib import Path
    assert Path("backend/app/services/durable_execution_queue.py").is_file()
    assert Path("backend/alembic/versions/0020_aegis_execution_queue.py").is_file()


def test_unknown_ticket_quarantine_preserved():
    from pathlib import Path
    assert "unknown_broker_tickets" in Path("backend/app/services/durable_lifecycle_service.py").read_text()


def test_no_auto_flip_gate_still_present():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService
    auto = AutonomousOhlcSignalService()
    auto.set_side("ACC-S6", "EURUSD", "SELL")
    allow, reason = auto.gate_signal("ACC-S6", "EURUSD", "BUY", 0.9, methodology="v53_6")
    assert allow is False
