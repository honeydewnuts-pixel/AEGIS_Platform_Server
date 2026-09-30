"""Hybrid Ratchet 70/30 — pure engine tests (no DB, module default disabled)."""
from __future__ import annotations

import pytest

from app.services.hybrid_ratchet import HybridRatchetEngine, RatchetConfig


@pytest.fixture
def eng():
    return HybridRatchetEngine(RatchetConfig(withdraw_pct=0.70, retain_pct=0.30, arm_multiple=2.0, pause_dd_from_cap=0.20))


def test_compounds_before_2x(eng):
    st = eng.seed("A", 1000.0)
    r = eng.apply_realized_trade(st, trade_id="t1", realized_pnl=100.0)
    assert r.applied is False
    assert r.reason == "still_compounding"
    assert st.equity == 1100.0
    assert st.armed is False
    assert st.eligible_balance == 0.0


def test_arms_at_2x_and_allocates(eng):
    st = eng.seed("A", 1000.0)
    # Jump to exactly 2000
    eng.apply_realized_trade(st, trade_id="t1", realized_pnl=1000.0)
    assert st.armed is True
    assert st.cap == 2000.0
    # Profit to 2100
    r = eng.apply_realized_trade(st, trade_id="t2", realized_pnl=100.0)
    assert r.applied is True
    assert abs(r.excess - 100.0) < 1e-6
    assert abs(r.to_eligible - 70.0) < 1e-6
    assert abs(r.to_cap - 30.0) < 1e-6
    assert abs(st.cap - 2030.0) < 1e-6
    assert abs(st.eligible_balance - 70.0) < 1e-6
    # Equity not clamped (separate from withdrawal entitlement)
    assert abs(st.equity - 2100.0) < 1e-6


def test_duplicate_trade_id(eng):
    st = eng.seed("A", 1000.0)
    eng.apply_realized_trade(st, trade_id="t1", realized_pnl=1000.0)
    eng.apply_realized_trade(st, trade_id="t2", realized_pnl=100.0)
    elig = st.eligible_balance
    r = eng.apply_realized_trade(st, trade_id="t2", realized_pnl=100.0)
    assert r.applied is False
    assert r.reason == "duplicate_trade_id"
    assert st.eligible_balance == elig


def test_cap_does_not_fall_on_loss(eng):
    st = eng.seed("A", 1000.0)
    eng.apply_realized_trade(st, trade_id="t1", realized_pnl=1000.0)
    eng.apply_realized_trade(st, trade_id="t2", realized_pnl=100.0)
    cap = st.cap
    eng.apply_realized_trade(st, trade_id="t3", realized_pnl=-50.0)
    assert st.cap == cap
    assert st.equity == 2050.0


def test_pause_at_20pct_from_cap_and_resume(eng):
    st = eng.seed("A", 1000.0)
    eng.apply_realized_trade(st, trade_id="t1", realized_pnl=1000.0)  # equity 2000, armed, cap 2000
    eng.apply_realized_trade(st, trade_id="t2", realized_pnl=100.0)  # cap 2030, equity 2100
    # Drop equity below 80% of CAP: 2030 * 0.8 = 1624
    eng.apply_realized_trade(st, trade_id="t3", realized_pnl=-(2100 - 1600))
    assert st.equity == 1600.0
    assert st.paused is True
    # Profit while paused — no new allocation
    r = eng.apply_realized_trade(st, trade_id="t4", realized_pnl=100.0)
    assert r.applied is False
    assert r.reason == "withdrawals_paused_drawdown"
    # Recover to CAP
    need = st.cap - st.equity
    eng.apply_realized_trade(st, trade_id="t5", realized_pnl=need)
    assert st.paused is False


def test_withdrawal_request_reduces_eligible_not_trading_pnl(eng):
    st = eng.seed("A", 1000.0)
    eng.apply_realized_trade(st, trade_id="t1", realized_pnl=1000.0)
    eng.apply_realized_trade(st, trade_id="t2", realized_pnl=100.0)
    trading = st.realized_trading_pnl
    r = eng.request_withdrawal(st, 70.0)
    assert r.applied is True
    assert st.eligible_balance == 0.0
    assert st.cumulative_withdrawn == 70.0
    assert st.realized_trading_pnl == trading  # withdrawals do not rewrite trading PnL
    assert abs(st.equity - 2030.0) < 1e-6  # 2100 - 70


def test_starting_equities_matrix_smoke(eng):
    for start in (50.0, 100.0, 250.0, 500.0, 1000.0, 10000.0):
        st = eng.seed("A", start, risk_per_trade_pct=1.0)
        eng.apply_realized_trade(st, trade_id=f"{start}-1", realized_pnl=start)  # to 2x
        assert st.armed
        eng.apply_realized_trade(st, trade_id=f"{start}-2", realized_pnl=start * 0.1)
        assert st.eligible_balance > 0
