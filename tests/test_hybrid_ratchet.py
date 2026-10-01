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


def test_lean_cap_ceiling_scales_with_start_equity():
    from app.services.hybrid_ratchet import resolve_lean_cap_ceiling, resolve_lean_cap_multiple
    assert abs(resolve_lean_cap_multiple(0.5) - 83.286) < 1e-6
    assert abs(resolve_lean_cap_ceiling(0.5, 1000.0) - 83_286.0) < 0.02
    assert abs(resolve_lean_cap_ceiling(1.0, 1000.0) - 783_300.0) < 0.02
    # Half start equity → half ceiling
    assert abs(resolve_lean_cap_ceiling(0.5, 500.0) - 41_643.0) < 0.02
    # Double start equity → double ceiling
    assert abs(resolve_lean_cap_ceiling(1.0, 2000.0) - 1_566_600.0) < 0.05


def test_lean_cap_locks_and_sweeps_overflow(eng):
    """When CAP would exceed lean ceiling, overflow goes to eligible and CAP stays at ceiling."""
    from app.services.hybrid_ratchet import HybridRatchetEngine, RatchetConfig
    # Small ceiling for unit test
    eng2 = HybridRatchetEngine(RatchetConfig(lean_cap_ceiling=2500.0))
    st = eng2.seed("A", 1000.0, risk_per_trade_pct=0.5)
    eng2.apply_realized_trade(st, trade_id="arm", realized_pnl=1000.0)  # equity 2000, cap 2000
    assert st.armed and st.cap == 2000.0
    # Big profit: equity 3000, excess 1000 → 700 eligible, 300 to CAP → cap 2300
    eng2.apply_realized_trade(st, trade_id="grow", realized_pnl=1000.0)
    assert st.cap == 2300.0
    assert abs(st.eligible_balance - 700.0) < 1e-6
    # Another profit that pushes CAP past 2500
    # equity was 3000; +500 → 3500; excess 1200 → 840 elig, 360 cap → tent 2660 → overflow 160
    eng2.apply_realized_trade(st, trade_id="lock", realized_pnl=500.0)
    assert abs(st.cap - 2500.0) < 1e-6
    assert st.lean_locked is True
    # Further profits: 100% to eligible, CAP stays 2500
    elig_before = st.eligible_balance
    eng2.apply_realized_trade(st, trade_id="sweep", realized_pnl=100.0)
    assert abs(st.cap - 2500.0) < 1e-6
    assert st.eligible_balance > elig_before


def test_lean_cap_does_not_treat_sweep_as_trading_loss(eng):
    from app.services.hybrid_ratchet import HybridRatchetEngine, RatchetConfig
    eng2 = HybridRatchetEngine(RatchetConfig(lean_cap_ceiling=2100.0))
    st = eng2.seed("A", 1000.0)
    eng2.apply_realized_trade(st, trade_id="a", realized_pnl=1000.0)
    trading = st.realized_trading_pnl
    eng2.apply_realized_trade(st, trade_id="b", realized_pnl=200.0)
    # trading pnl still sum of realized; withdrawal entitlement separate
    assert abs(st.realized_trading_pnl - (trading + 200.0)) < 1e-6
    assert st.cap <= 2100.0 + 1e-6
