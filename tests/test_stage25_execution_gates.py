"""Stage 2.5 gates: closed-bar isolation, production authorization."""
from __future__ import annotations

from app.services.ohlc_bar_utils import closed_bars_only
from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService
from app.rulebooks.evaluators.common import (
    resolve_cost_deduction_r,
    COST_MODE_LEGACY,
    COST_MODE_BID_ASK,
    LEGACY_FIXED_COST_R,
)


def test_closed_bars_strip_forming():
    bars = [{"time": 1, "close": 1.0}, {"time": 2, "close": 1.1}, {"time": 3, "close": 1.2}]
    out = closed_bars_only(bars, current_bar={"time": 3, "close": 1.2})
    assert len(out) == 2
    assert out[-1]["time"] == 2


def test_auth_blocks_rsi9_research():
    svc = AutonomousOhlcSignalService()
    ok, reason = svc._execution_authorization({
        "production_authorized": False,
        "methodology": "rsi9_transfer",
    })
    assert ok is False


def test_auth_blocks_native():
    svc = AutonomousOhlcSignalService()
    ok, _ = svc._execution_authorization({
        "production_authorized": False,
        "methodology": "native_discovery",
    })
    assert ok is False


def test_legacy_cost_separated_from_bid_ask():
    assert resolve_cost_deduction_r(COST_MODE_BID_ASK)[0] == 0.0
    assert resolve_cost_deduction_r(COST_MODE_LEGACY)[0] == LEGACY_FIXED_COST_R
