"""Stage 5 — durable execution queue: authorization boundary + service logic."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.durable_execution_queue import DurableExecutionQueueService
from app.services.executor_signal_service import ExecutorSignalService


def test_research_not_execution_authorized():
    for meth in ("rsi9_transfer", "native_discovery", "v53_6", "v31_short", "generation3_x", "transfer_y"):
        row = {
            "methodology": meth,
            "production_authorized": True,
            "controlled_demo_authorized": True,
            "rule_name": meth,
        }
        assert ExecutorSignalService.is_execution_authorized(row) is False, meth


def test_controlled_demo_authorized():
    row = {
        "methodology": "controlled_demo_test",
        "rule_name": "controlled_demo_test",
        "production_authorized": False,
        "controlled_demo_authorized": True,
    }
    assert ExecutorSignalService.is_execution_authorized(row) is True


def test_production_flag_alone_does_not_authorize_research():
    row = {
        "methodology": "rsi9_transfer",
        "production_authorized": True,
        "controlled_demo_authorized": False,
    }
    assert ExecutorSignalService.is_execution_authorized(row) is False


def test_settings_production_authorized_false():
    from app.config import settings
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


@pytest.mark.asyncio
async def test_enqueue_rejects_unauthorized():
    dq = DurableExecutionQueueService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    out = await dq.enqueue(
        session,
        {
            "signal_id": "s1",
            "account_id": "ACC",
            "symbol": "EURUSD",
            "side": "SELL",
            "methodology": "rsi9_transfer",
            "production_authorized": True,
            "controlled_demo_authorized": True,
        },
    )
    assert out is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_accepts_controlled_demo():
    dq = DurableExecutionQueueService()
    session = MagicMock()
    # no prior pending
    res = MagicMock()
    res.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    session.flush = AsyncMock()
    out = await dq.enqueue(
        session,
        {
            "signal_id": "s-demo-1",
            "account_id": "ACC-S5",
            "symbol": "EURUSD",
            "side": "BUY",
            "methodology": "controlled_demo_test",
            "rule_name": "controlled_demo_test",
            "production_authorized": False,
            "controlled_demo_authorized": True,
            "volume": 0.01,
        },
    )
    assert out is not None
    session.add.assert_called_once()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_ack_idempotent_when_already_terminal():
    dq = DurableExecutionQueueService()
    session = MagicMock()
    row = MagicMock()
    row.status = "ACKED"
    res = MagicMock()
    res.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=res)
    session.flush = AsyncMock()
    r = await dq.ack(session, account_id="ACC", signal_id="s1", ok=True, position_ticket=1)
    assert r["idempotent"] is True
    session.flush.assert_not_awaited()


def test_memory_ack_idempotent_still():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-S5",
        symbol="EURUSD",
        side="SELL",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        controlled_demo_authorized=True,
        production_authorized=False,
    )
    assert sid
    a1 = svc.ack("ACC-S5", sid, ok=True, position_ticket=5)
    a2 = svc.ack("ACC-S5", sid, ok=True, position_ticket=5)
    assert a2.get("idempotent") is True
    assert svc.get_pending("ACC-S5", "EURUSD") is None


def test_migration_file_exists():
    from pathlib import Path
    p = Path("backend/alembic/versions/0020_aegis_execution_queue.py")
    assert p.is_file()
    text = p.read_text()
    assert "aegis_execution_queue" in text
    assert "upgrade" in text


def test_model_exists():
    from app.db.models import AegisExecutionQueue
    assert AegisExecutionQueue.__tablename__ == "aegis_execution_queue"


def test_unknown_broker_still_quarantined_stage4():
    from pathlib import Path
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "unknown_broker_tickets" in src
