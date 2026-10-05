"""Idempotent close: second release returns ALREADY_RELEASED (logic + lock path)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.position_lifecycle_service import PositionLifecycleService


def test_memory_duplicate_close():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S1", ok=True, position_ticket=10,
        order_ticket=1, deal_ticket=1, symbol="EURUSD", side="SELL",
        volume=0.1, risk_usd=5.0, idempotent=False,
    )
    life.mark_open_risk_recorded("A1", "S1", 5.0)
    r1, s1 = life.on_broker_close(account_id="A1", signal_id="S1", position_ticket=10, symbol="EURUSD")
    r2, s2 = life.on_broker_close(account_id="A1", signal_id="S1", position_ticket=10, symbol="EURUSD")
    assert r1 == 5.0 and s1 == "RISK_RELEASED"
    assert r2 is None and s2 == "ALREADY_RELEASED"


def test_for_update_query_shape_present():
    """Source must use with_for_update on close path."""
    from pathlib import Path
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "with_for_update" in src
    assert "ALREADY_RELEASED" in src
