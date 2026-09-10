from datetime import datetime, timedelta, timezone

import pytest

from app.safety.execution_guard import (
    Decision, ExecutionState, ExecutionStateMachine, MarketState, OrderIntent,
    PositionState, SafetyConfig, V42SafetyGate,
)


def market(now, spread=0.0001):
    return MarketState("AUDUSD", "M5", 0.6500, 0.6500 + spread, 0.0010,
                       now - timedelta(seconds=60), now)


def intent(now, mode="PAPER", stop=0.6485):
    return OrderIntent("abc-1", "AUDUSD", "M5", "BUY", 0.6500, stop, 0.0010,
                       now - timedelta(seconds=60), mode)


def test_paper_order_passes_and_live_fails_closed():
    now = datetime.now(timezone.utc)
    gate = V42SafetyGate()
    paper = gate.validate_order(intent(now), market(now), [], qualified_rulebook=True, now=now)
    assert paper.decision == Decision.ALLOW_PAPER

    live = gate.validate_order(intent(now, mode="LIVE"), market(now), [], qualified_rulebook=True, now=now)
    assert live.decision == Decision.REJECT
    assert "PRODUCTION_AUTHORIZATION_REQUIRED" in live.reasons
    assert "LIVE_EXECUTION_DISABLED" in live.reasons


def test_stale_spread_and_position_guards():
    now = datetime.now(timezone.utc)
    gate = V42SafetyGate(SafetyConfig(max_spread_atr=0.20, max_signal_age_seconds=120))
    stale_market = MarketState("AUDUSD", "M5", .65, .6505, .001,
                                now - timedelta(seconds=500), now)
    result = gate.validate_order(intent(now), stale_market,
                                 [PositionState("AUDUSD", "BUY", .65, .6485)],
                                 qualified_rulebook=True, now=now)
    assert result.decision == Decision.REJECT
    assert "STALE_OR_FUTURE_BAR" in result.reasons
    assert "SPREAD_ATR_LIMIT" in result.reasons
    assert "ONE_POSITION_PER_SYMBOL" in result.reasons
    assert "TOTAL_POSITION_LIMIT" in result.reasons


def test_state_machine_rejects_illegal_skip():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.SIGNAL_ACCEPTED)
    with pytest.raises(ValueError):
        sm.transition(ExecutionState.FILLED)
    sm.transition(ExecutionState.ORDER_QUEUED)
    sm.transition(ExecutionState.FILLED)


def test_kill_switch_blocks_even_valid_paper_order():
    now = datetime.now(timezone.utc)
    gate = V42SafetyGate()
    gate.kill_switch.activate("manual emergency stop")
    result = gate.validate_order(intent(now), market(now), [], qualified_rulebook=True, now=now)
    assert result.decision == Decision.KILL_SWITCH
