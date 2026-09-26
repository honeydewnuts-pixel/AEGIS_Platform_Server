"""Live short PM aligned with simulate_short 72-bar holding window."""
from app.rulebooks.live_short_position_manager import (
    BarOHLC,
    ShortPositionState,
    holding_bars_inclusive,
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


def test_max_hold_time_exit_on_72nd_holding_bar():
    """entry index 0; TIME on bar_index 71 (72nd holding bar), not 72."""
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0, max_hold_bars=72,
    )
    quiet = BarOHLC(1.1001, 1.0990, 1.0995, 0.001)
    # Bars 0..70 should not TIME
    st2 = st
    for j in range(0, 71):
        st2 = step_short_bar(st2, quiet, j)
        assert not st2.closed, f"early TIME at bar {j}"
    # Bar 71 = 72nd holding bar
    st2 = step_short_bar(st2, quiet, 71)
    assert st2.closed and st2.close_reason == "TIME"
    assert st2.exit_bar_index == 71


def test_max_hold_small_window():
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0, max_hold_bars=3,
    )
    bars = [
        BarOHLC(1.1001, 1.0990, 1.0995, 0.001),  # 0
        BarOHLC(1.1002, 1.0991, 1.0996, 0.001),  # 1
        BarOHLC(1.1001, 1.0990, 1.0994, 0.001),  # 2 → TIME
    ]
    st2 = st
    for j, b in enumerate(bars):
        st2 = step_short_bar(st2, b, j)
        if st2.closed:
            assert j == 2 and st2.close_reason == "TIME"
            break
    else:
        raise AssertionError("expected TIME on bar 2")


def test_stop_on_time_bar_takes_precedence():
    """On the TIME bar, stop check runs first (simulate_short order)."""
    st = ShortPositionState(
        signal_id="s1", symbol="X", entry_price=1.1000, initial_risk=0.0015,
        atr_at_signal=0.0010, entry_bar_index=0, max_hold_bars=3,
    )
    # bars 0,1 quiet; bar 2 would be TIME but stop hits
    st = step_short_bar(st, BarOHLC(1.1001, 1.0990, 1.0995, 0.001), 0)
    st = step_short_bar(st, BarOHLC(1.1001, 1.0990, 1.0995, 0.001), 1)
    st = step_short_bar(st, BarOHLC(1.1020, 1.0990, 1.1010, 0.001), 2)
    assert st.closed and st.close_reason == "STOP"


def test_holding_bar_count_matches_simulate_short():
    # entry at relative 0 ↔ absolute i+1; TIME at relative 71 ↔ absolute i+72
    assert holding_bars_inclusive(0, 0) == 1
    assert holding_bars_inclusive(0, 71) == 72
    assert should_time_exit(0, 70, 72) is False
    assert should_time_exit(0, 71, 72) is True
    assert should_time_exit(100, 170, 72) is False  # 71 holding bars
    assert should_time_exit(100, 171, 72) is True   # 72 holding bars


def test_no_buy_in_baseline_gate():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService
    svc = AutonomousOhlcSignalService()
    allow, _ = svc.gate_signal("A", "AUDUSD", "BUY", 1.0, methodology="v31_short_baseline")
    assert allow is False
