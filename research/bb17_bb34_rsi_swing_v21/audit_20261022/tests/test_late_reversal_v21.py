#!/usr/bin/env python3
"""Unit tests for frozen v2.1 late structural reversals."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from late_reversal_v21 import detect_late_reversals

P = F = 0

def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1
        print(f"[PASS] {name}")
    else:
        F += 1
        print(f"[FAIL] {name} {detail}")


def make_ind(n, **kwargs):
    """Build indicator dict with constant defaults overridden by kwargs arrays."""
    ind = {}
    for k in ("B17_M", "B34_M", "B17_L", "B17_U", "B34_L", "B34_U"):
        ind[k] = np.full(n, 50.0)
    for k, v in kwargs.items():
        ind[k] = np.asarray(v, dtype=float)
    return ind


def test_bearish_qualifying():
    """Minimal qualifying late bearish sequence."""
    n = 10
    # cross at t=3: B17_M goes from >= B34_M to <
    b17m = np.array([55, 55, 55, 45, 45, 45, 45, 45, 45, 45], float)
    b34m = np.array([50, 50, 50, 50, 50, 50, 50, 50, 50, 50], float)
    b17l = np.array([40] * n, float)  # < b34l
    b34l = np.array([42] * n, float)
    b34u = np.array([60] * n, float)
    high = np.array([50, 50, 50, 50, 52, 50, 50, 50, 50, 50], float)  # higher high at t=4
    low = np.array([44] * n, float)
    close = np.array([48] * n, float)  # > b17m(45), within bb34
    close[4] = 48
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=b17l, B34_L=b34l, B34_U=b34u)
    # at t=4: gap=1 from cross at 3
    events = detect_late_reversals(ind, high, low, close)
    elig = [e for e in events if e["eligible"] and e["action"] == "LATE_BEARISH_REVERSAL"]
    check("bearish_qualifying_exists", len(elig) >= 1, str(events[:5]))
    if elig:
        check("bearish_gap_at_least_1", elig[0]["gap"] >= 1)
        check("bearish_decision_after_cross", elig[0]["decision_idx"] > elig[0]["crossing_idx"])


def test_crossing_row_not_accepted():
    """Event on the crossing row itself must not qualify (gap>=1 required)."""
    n = 8
    b17m = np.array([55, 55, 45, 45, 45, 45, 45, 45], float)
    b34m = np.full(n, 50.0)
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    high = np.full(n, 52.0); high[2] = 53  # even on cross row
    low = np.full(n, 44.0)
    close = np.full(n, 48.0)
    events = detect_late_reversals(ind, high, low, close)
    # no eligible at decision_idx == crossing_idx
    bad = [e for e in events if e["eligible"] and e["decision_idx"] == e["crossing_idx"]]
    check("cross_row_not_eligible", len(bad) == 0, str(bad))


def test_gap_six_ok_seven_reject():
    n = 15
    # cross at t=2
    b17m = np.full(n, 45.0); b17m[0] = 55; b17m[1] = 55
    b34m = np.full(n, 50.0)
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    high = np.full(n, 50.0)
    low = np.full(n, 44.0)
    close = np.full(n, 48.0)
    # make higher high only at gap=6 (t=8) and gap=7 (t=9)
    high[8] = 55  # t=8, gap=6 from cross at 2
    high[9] = 56  # gap=7
    events = detect_late_reversals(ind, high, low, close)
    # After first success at gap=6, crossing is consumed so gap=7 may not fire
    elig = [e for e in events if e["eligible"] and e["action"] == "LATE_BEARISH_REVERSAL"]
    gaps = [e["gap"] for e in elig]
    check("gap6_accepted", 6 in gaps or any(e["gap"] == 6 for e in elig), str(gaps))
    # force no consume test: check rejection list for gap 7 attempts
    rejected_gap7 = [e for e in events if e.get("gap") == 7 and not e["eligible"]]
    # If crossing consumed at 6, gap 7 may not appear — both OK per spec
    check("gap7_not_eligible_event", all(e["gap"] != 7 or not e["eligible"] for e in events), str([(e["gap"], e["eligible"]) for e in events if e.get("gap") in (6, 7)]))


def test_bullish_qualifying():
    n = 10
    b17m = np.array([45, 45, 45, 55, 55, 55, 55, 55, 55, 55], float)
    b34m = np.full(n, 50.0)
    b17u = np.full(n, 60.0)  # > b34u
    b34u = np.full(n, 58.0)
    b34l = np.full(n, 40.0)
    low = np.array([50, 50, 50, 50, 48, 50, 50, 50, 50, 50], float)  # lower low at t=4
    high = np.full(n, 56.0)
    close = np.full(n, 52.0)  # < b17m 55, within bb34
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_U=b17u, B34_U=b34u, B34_L=b34l)
    events = detect_late_reversals(ind, high, low, close)
    elig = [e for e in events if e["eligible"] and e["action"] == "LATE_BULLISH_REVERSAL"]
    check("bullish_qualifying", len(elig) >= 1, str([e for e in events if "BULLISH" in e["action"]][:3]))


def test_no_equality_higher_high():
    """high[t] > high[t-1] is strict; equality fails."""
    n = 8
    b17m = np.array([55, 55, 45, 45, 45, 45, 45, 45], float)
    b34m = np.full(n, 50.0)
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    high = np.full(n, 52.0)  # equal highs — should not qualify
    low = np.full(n, 44.0)
    close = np.full(n, 48.0)
    events = detect_late_reversals(ind, high, low, close)
    elig = [e for e in events if e["eligible"] and e["action"] == "LATE_BEARISH_REVERSAL"]
    check("strict_higher_high_required", len(elig) == 0, str(elig))


def test_touch_includes_equality():
    """low <= BB17_M <= high includes equality."""
    n = 8
    b17m = np.array([55, 55, 45, 45, 45, 45, 45, 45], float)
    b34m = np.full(n, 50.0)
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    high = np.array([50, 50, 50, 52, 50, 50, 50, 50], float)
    low = np.array([44, 44, 44, 45, 44, 44, 44, 44], float)  # low == b17m at t=3
    close = np.full(n, 48.0)
    events = detect_late_reversals(ind, high, low, close)
    elig = [e for e in events if e["eligible"] and e["decision_idx"] == 3]
    check("equality_touch_accepted", len(elig) >= 1, str(events[:6]))


def test_newer_cross_replaces():
    n = 12
    # first cross at 2, second at 5
    b17m = np.array([55, 55, 45, 45, 55, 45, 45, 45, 45, 45, 45, 45], float)
    b34m = np.full(n, 50.0)
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    high = np.full(n, 50.0)
    high[6] = 55  # after second cross at 5, gap=1
    low = np.full(n, 44.0)
    close = np.full(n, 48.0)
    events = detect_late_reversals(ind, high, low, close)
    elig = [e for e in events if e["eligible"] and e["action"] == "LATE_BEARISH_REVERSAL"]
    if elig:
        check("uses_newer_cross", elig[0]["crossing_idx"] == 5, str(elig[0]))
    else:
        check("uses_newer_cross", False, "no eligible")


def test_nan_blocks():
    n = 8
    b17m = np.array([55, 55, 45, 45, 45, 45, 45, 45], float)
    b34m = np.full(n, 50.0)
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    ind["B17_M"][3] = np.nan
    high = np.full(n, 52.0); high[3] = 53
    low = np.full(n, 44.0)
    close = np.full(n, 48.0)
    events = detect_late_reversals(ind, high, low, close)
    elig_at_3 = [e for e in events if e["decision_idx"] == 3 and e["eligible"]]
    check("nan_blocks_event", len(elig_at_3) == 0)


def test_prefix_invariance_late():
    """Appending future bars must not change earlier eligible decisions."""
    n = 20
    rng = np.random.default_rng(0)
    close = np.cumsum(rng.normal(0, 0.5, n)) + 50
    high = close + 1
    low = close - 1
    b17m = close.copy()
    b34m = np.full(n, 50.0)
    # force a cross early
    b17m[:3] = 55
    b17m[3:] = 45
    ind = make_ind(n, B17_M=b17m, B34_M=b34m, B17_L=np.full(n, 40.), B34_L=np.full(n, 42.),
                   B34_U=np.full(n, 60.))
    high[5] = high[4] + 2
    e1 = detect_late_reversals({k: v[:12].copy() for k, v in ind.items()}, high[:12], low[:12], close[:12])
    e2 = detect_late_reversals(ind, high, low, close)
    early_elig = [(e["decision_idx"], e["action"]) for e in e1 if e["eligible"]]
    full_elig = [(e["decision_idx"], e["action"]) for e in e2 if e["eligible"] and e["decision_idx"] < 12]
    check("prefix_invariance", early_elig == full_elig, f"{early_elig} vs {full_elig}")


if __name__ == "__main__":
    test_bearish_qualifying()
    test_crossing_row_not_accepted()
    test_gap_six_ok_seven_reject()
    test_bullish_qualifying()
    test_no_equality_higher_high()
    test_touch_includes_equality()
    test_newer_cross_replaces()
    test_nan_blocks()
    test_prefix_invariance_late()
    print(f"TOTAL {P} PASS {F} FAIL")
    sys.exit(0 if F == 0 else 1)
