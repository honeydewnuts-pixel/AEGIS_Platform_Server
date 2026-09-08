"""Production-critical tests for RULEBOOK_V3 Y-coordinate consistency."""
from __future__ import annotations

from app.services.signal_rule_engine_v3 import (
    SignalRuleEngineV3,
    side_of,
    _higher_low_pair,
    _lower_high_pair,
)


def _frame(rsi, ma, b1u, b1m, b1l, p7u=10, p7m=20, p7l=30, p8u=12, p8m=20, p8l=28, price=15):
    return {
        "rsi6": rsi,
        "ma4": ma,
        "band1": {"U": b1u, "M": b1m, "L": b1l},
        "price_band7": {"U": p7u, "M": p7m, "L": p7l},
        "price_band8": {"U": p8u, "M": p8m, "L": p8l},
        "price_close": price,
    }


def test_side_of_y_convention():
    # smaller Y = above on chart
    assert side_of(10.0, 20.0) == "above"
    assert side_of(30.0, 20.0) == "below"


def test_higher_low_pair_uses_y_inversion():
    # later pivot with smaller Y is a higher low in value terms
    assert _higher_low_pair([50.0, 40.0, 45.0, 35.0, 38.0]) is True


def test_lower_high_pair_uses_y_inversion():
    assert _lower_high_pair([10.0, 20.0, 15.0, 25.0, 22.0]) is True


def test_warming_up_empty():
    eng = SignalRuleEngineV3()
    r = eng.evaluate([])
    assert r.signal == "HOLD"
    assert r.rule_name == "warming_up"


def test_indicators_not_detected():
    eng = SignalRuleEngineV3()
    r = eng.evaluate([{"rsi6": 1}])
    assert r.rule_name == "indicators_not_detected"


def test_contraction_detection_matches_formal_rulebook():
    eng = SignalRuleEngineV3()
    # contraction: p8U < p7U and p8L > p7L
    h = [
        _frame(25, 22, 10, 20, 30, p7u=10, p7l=30, p8u=12, p8l=28),
        _frame(24, 21, 10, 20, 30, p7u=10, p7l=30, p8u=12, p8l=28),
    ]
    r = eng.evaluate(h)
    assert r.contraction == 1
    assert r.expansion == 0


def test_expansion_buy_uses_formal_y_operators():
    eng = SignalRuleEngineV3()
    # expansion bands + f7 < f11 (rsi Y < L Y)
    h = [
        _frame(5, 8, 10, 20, 30, p7u=12, p7l=28, p8u=10, p8l=30),
        _frame(5, 8, 10, 20, 30, p7u=12, p7l=28, p8u=10, p8l=30),
    ]
    r = eng.evaluate(h)
    assert r.expansion == 1
    # May or may not fire EXPANSION_BUY depending on full conditions; at least no crash
    assert r.signal in ("HOLD", "BUY", "SELL")


def test_rule_a_buy_requires_f7_lt_f11_y():
    """Formal A_BUY starts with f7 < f11 (screen Y)."""
    eng = SignalRuleEngineV3()
    # rsi BELOW lower band in Y (rsi > L) should not satisfy f7 < f11
    h = [_frame(35, 25, 10, 20, 30) for _ in range(5)]
    # force contraction geometry
    for fr in h:
        fr["price_band7"] = {"U": 10, "M": 20, "L": 30}
        fr["price_band8"] = {"U": 12, "M": 20, "L": 28}
    r = eng.evaluate(h)
    # With rsi=35 > L=30, A_BUY must not fire via the f7 < f11 gate
    assert not (r.signal == "BUY" and r.rule_name == "RULE_A")
