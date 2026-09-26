"""Live short PM must match simulate_short order of operations."""
from app.rulebooks.live_short_position_manager import (
    BarOHLC,
    ShortPositionState,
    completed_bars_since_entry,
    initial_stop_from_entry,
    should_time_exit,
    step_short_bar,
)


def test_initial_stop_from_entry():
    stop = initial_stop_from_entry(1.1000, 0.0010, 1.5)
    assert abs(stop - 1.1015) < 1e-9


def test_be_at_one_r():
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0,
    )
    bar = BarOHLC(high=1.1002, low=1.0980, close=1.0985, atr=0.0010)
    st2 = step_short_bar(st, bar, 0)
    assert st2.be_active is True
    assert abs(st2.current_stop - 1.09925) < 1e-9
    assert not st2.closed


def test_stop_hit_before_be():
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0,
    )
    bar = BarOHLC(high=1.1020, low=1.0990, close=1.1010, atr=0.0010)
    st2 = step_short_bar(st, bar, 0)
    assert st2.closed and st2.close_reason == "STOP"


def test_trail_only_tightens():
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0, be_active=True, current_stop=1.1000,
    )
    bar = BarOHLC(high=1.0995, low=1.0970, close=1.0975, atr=0.0010)
    st2 = step_short_bar(st, bar, 1)
    assert st2.current_stop < 1.1000
    assert st2.current_stop <= 1.09825 + 1e-9


def test_trail_never_widens():
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0, be_active=True, current_stop=1.0980,
    )
    bar = BarOHLC(high=1.0990, low=1.0975, close=1.0988, atr=0.0010)
    st2 = step_short_bar(st, bar, 2)
    assert abs(st2.current_stop - 1.0980) < 1e-9


def test_max_hold_time_exit():
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0, max_hold_bars=3,
    )
    bars = [
        BarOHLC(1.1001, 1.0990, 1.0995, 0.001),
        BarOHLC(1.1002, 1.0991, 1.0996, 0.001),
        BarOHLC(1.1001, 1.0990, 1.0994, 0.001),
        BarOHLC(1.1000, 1.0988, 1.0992, 0.001),
    ]
    st2 = st
    for j, b in enumerate(bars):
        st2 = step_short_bar(st2, b, j)
        if st2.closed:
            break
    assert st2.closed and st2.close_reason == "TIME"


def test_bar_count_not_wall_clock():
    # 72 wall-clock minutes is irrelevant — only bar indices matter
    assert completed_bars_since_entry(100, 100) == 0
    assert completed_bars_since_entry(100, 172) == 72
    assert should_time_exit(100, 171, 72) is False  # 71 bars
    assert should_time_exit(100, 172, 72) is True   # 72 bars


def test_no_buy_in_baseline_gate():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService
    svc = AutonomousOhlcSignalService()
    allow, _ = svc.gate_signal("A", "AUDUSD", "BUY", 1.0, methodology="v31_short_baseline")
    assert allow is False
