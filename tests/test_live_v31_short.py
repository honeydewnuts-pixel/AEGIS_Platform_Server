"""Unit tests: live V31 SHORT evaluator mirrors frozen filter structure."""

import numpy as np

from app.rulebooks.live_v31_short import evaluate_live_v31_short, v31_short_signal_at_index
from app.rulebooks.evaluators.common import wilder_atr14


def _synthetic_down_break_bars(n=80):
    """Build bars ending with a structural down-break candidate."""
    bars = []
    price = 1.1000
    for i in range(n):
        # mostly tight range
        o = price
        h = price + 0.00015
        l = price - 0.00015
        c = price + 0.00005
        if i == n - 1:
            # close below prior 12-bar low
            l = price - 0.0008
            c = price - 0.0007
            h = price - 0.0001
        bars.append({"open": o, "high": h, "low": l, "close": c, "time": 1_700_000_000 + i * 300})
        price = c
    return bars


def test_evaluate_returns_hold_or_sell_never_buy():
    bars = _synthetic_down_break_bars()
    out = evaluate_live_v31_short(bars, rulebook_id="AEGIS-RB-V53.6-V31-AUDUSD-5M", instrument="AUDUSD")
    assert out["signal"] in ("HOLD", "SELL")
    assert out["signal"] != "BUY"
    assert out.get("methodology") == "v31_short_baseline"
    assert out.get("production_authorized") is False


def test_throttle_and_filters_callable():
    h = np.ones(40) * 1.1
    l = np.ones(40) * 1.09
    c = np.ones(40) * 1.095
    atr = wilder_atr14(h, l, c)
    ok, last, reason = v31_short_signal_at_index(h, l, c, atr, 20, -10**9)
    assert isinstance(ok, bool)
    assert isinstance(reason, str)
