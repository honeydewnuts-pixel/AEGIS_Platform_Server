"""
Tests for app/services/signal_rule_engine_v3.py - pure logic, no DB/Redis
needed. Mirrors the structure of test_signal_rule_engine.py.
"""
from app.services.signal_rule_engine_v3 import (
    SignalRuleEngineV3,
    touches,
    find_pivots,
    higher_low_pattern,
    lower_high_pattern,
)


def frame(p7u, p7m, p7l, p8u, p8m, p8l, rsi, ma, b1u, b1m, b1l):
    return {
        "price_band7": {"U": p7u, "M": p7m, "L": p7l},
        "price_band8": {"U": p8u, "M": p8m, "L": p8l},
        "rsi6": rsi,
        "ma4": ma,
        "band1": {"U": b1u, "M": b1m, "L": b1l},
    }


class TestPrimitives:

    def test_touches_counts_close_frames(self):
        a = [10, 20, 30, 40]
        b = [12, 25, 30.5, 60]
        assert touches(a, b, tol_px=3) == 2  # frames 0 and 2

    def test_find_pivots_basic(self):
        series = [50, 40, 30, 40, 50, 60, 50]
        lows_y, highs_y = find_pivots(series)
        assert 2 in lows_y   # value 30 is the smallest -> local Y minimum
        assert 5 in highs_y  # value 60 is the largest -> local Y maximum

    def test_higher_low_pattern_true(self):
        # value-troughs (local Y maxima) at idx2 (80) then idx5 (60): 60 < 80 -> higher low
        series = [40, 60, 80, 60, 40, 60, 40]
        assert higher_low_pattern(series) is True

    def test_lower_high_pattern_true(self):
        # value-peaks (local Y minima) at idx2 (10) then idx5 (30): 30 > 10 -> lower high
        series = [50, 30, 10, 30, 50, 30, 50]
        assert lower_high_pattern(series) is True


class TestRegime:

    def test_contraction_detected(self):
        eng = SignalRuleEngineV3()
        # #8 band Y-range nested inside #7 band Y-range
        f = frame(10, 50, 90, 20, 50, 80, 60, 60, 40, 60, 80)
        assert eng._contraction(f) is True
        assert eng._expansion(f) is False

    def test_expansion_detected(self):
        eng = SignalRuleEngineV3()
        # #8 band Y-range wider than #7 band Y-range
        f = frame(20, 50, 80, 10, 50, 90, 60, 60, 40, 60, 80)
        assert eng._expansion(f) is True
        assert eng._contraction(f) is False


class TestWarmupAndMissingData:

    def test_warming_up_with_one_frame(self):
        eng = SignalRuleEngineV3()
        f = frame(10, 50, 90, 20, 50, 80, 60, 60, 40, 60, 80)
        result = eng.evaluate([f])
        assert result.signal == "HOLD"
        assert result.rule_name == "warming_up"

    def test_missing_indicators_soft_holds(self):
        eng = SignalRuleEngineV3()
        bad = {"price_band7": None, "price_band8": None, "rsi6": None, "ma4": None, "band1": None}
        result = eng.evaluate([bad, bad])
        assert result.signal == "HOLD"
        assert result.rule_name == "indicators_not_detected"


class TestRuleB:

    def test_rule_b_buy_fires_on_touches_plus_cross(self):
        eng = SignalRuleEngineV3(touch_tolerance_px=6.0)
        # f7 (rsi6) touching f10/f11 repeatedly, f8 (ma4) crossing down through f10
        f_prev = frame(10, 50, 90, 20, 50, 80, 58, 55, 40, 60, 80)  # ma4=55 above band1.M=60 (Y smaller=above)
        f_cur = frame(10, 50, 90, 20, 50, 80, 60, 62, 40, 60, 80)   # ma4=62, now below band1.M=60
        window = [f_prev, f_cur] * 10  # ensure >=2 touches within the window
        result = eng.evaluate(window)
        assert result.rule_name == "rule_b_buy"
        assert result.signal == "BUY"


class TestNoFire:

    def test_neutral_frame_holds(self):
        eng = SignalRuleEngineV3()
        # No contraction, no expansion -> only "no_rule_matched" HOLD possible
        f = frame(10, 50, 90, 10, 50, 90, 60, 60, 40, 60, 80)
        result = eng.evaluate([f, f])
        assert result.signal == "HOLD"
        assert result.rule_name == "no_rule_matched"
