"""Autonomous per-trade risk assessment — client sets tolerance, AEGIS sets trade risk %."""
import pytest

from app.services.risk_assessment import (
    BASE_DIVISOR,
    PLATFORM_MAX_TRADE_RISK_PCT,
    assess_per_trade_risk,
)


def test_client_tolerance_is_not_per_trade_risk():
    a = assess_per_trade_risk(
        client_tolerance_pct=10.0,
        equity=10_000,
        max_concurrent_slots=10,
        open_positions=0,
    )
    assert a.allow
    # Base = 10/10 = 1.0, not 10%
    assert a.per_trade_risk_pct == pytest.approx(10.0 / BASE_DIVISOR)
    assert a.per_trade_risk_pct < a.client_tolerance_pct


def test_risk_varies_with_open_positions():
    base = assess_per_trade_risk(
        client_tolerance_pct=20.0,
        equity=10_000,
        max_concurrent_slots=8,
        open_positions=0,
    )
    busy = assess_per_trade_risk(
        client_tolerance_pct=20.0,
        equity=10_000,
        max_concurrent_slots=8,
        open_positions=6,
    )
    assert base.allow and busy.allow
    assert busy.per_trade_risk_pct < base.per_trade_risk_pct


def test_drawdown_reduces_or_blocks():
    ok = assess_per_trade_risk(
        client_tolerance_pct=10.0,
        equity=10_000,
        peak_equity=10_000,
        max_concurrent_slots=5,
        open_positions=0,
    )
    # dd = 1000, tol budget = 1000 → ratio 1.0 hard
    blocked = assess_per_trade_risk(
        client_tolerance_pct=10.0,
        equity=9_000,
        peak_equity=10_000,
        max_concurrent_slots=5,
        open_positions=0,
    )
    assert ok.allow
    assert not blocked.allow
    assert blocked.reason == "drawdown_limit_reached"


def test_wide_stop_vs_atr_blocks():
    a = assess_per_trade_risk(
        client_tolerance_pct=10.0,
        equity=10_000,
        max_concurrent_slots=5,
        open_positions=0,
        stop_distance=0.005,
        atr14=0.001,  # ratio 5 > hard 4
    )
    assert not a.allow
    assert a.reason == "stop_too_wide_vs_atr"


def test_platform_cap():
    # tolerance 50 → base 5 → capped at PLATFORM_MAX
    a = assess_per_trade_risk(
        client_tolerance_pct=50.0,
        equity=10_000,
        max_concurrent_slots=1,
        open_positions=0,
    )
    assert a.allow
    assert a.per_trade_risk_pct <= PLATFORM_MAX_TRADE_RISK_PCT + 1e-9


def test_halted_rejects():
    a = assess_per_trade_risk(
        client_tolerance_pct=10.0,
        equity=10_000,
        trading_halted=True,
    )
    assert not a.allow
