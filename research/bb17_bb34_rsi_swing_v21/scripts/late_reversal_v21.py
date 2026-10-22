"""Frozen v2.1 late structural reversal — explicit conditions from operator task."""
from __future__ import annotations
import numpy as np


def detect_late_reversals(ind, high, low, close):
    """
    Late bearish / bullish structural reversals.
    Crossing stored on observed rows; event requires 1 <= t-c <= 6.
    Returns list of event dicts with action, decision_idx, crossing_idx.
    """
    n = len(close)
    b17m = ind["B17_M"]
    b34m = ind["B34_M"]
    b17l = ind["B17_L"]
    b17u = ind["B17_U"]
    b34l = ind["B34_L"]
    b34u = ind["B34_U"]

    events = []
    last_down_cross = None  # index c of most recent downward BB17_M vs BB34_M cross
    last_up_cross = None

    for t in range(1, n):
        # detect crossings at t (using t-1 vs t)
        if (not np.isnan(b17m[t - 1]) and not np.isnan(b34m[t - 1])
                and not np.isnan(b17m[t]) and not np.isnan(b34m[t])):
            # downward cross: prev BB17_M >= BB34_M, curr BB17_M < BB34_M
            if b17m[t - 1] >= b34m[t - 1] and b17m[t] < b34m[t]:
                last_down_cross = t
            # upward cross
            if b17m[t - 1] <= b34m[t - 1] and b17m[t] > b34m[t]:
                last_up_cross = t

        # --- late bearish at t ---
        if last_down_cross is not None:
            c = last_down_cross
            gap = t - c
            if 1 <= gap <= 6:
                ok = True
                reasons = []
                if not (b17m[t] < b34m[t]):
                    ok = False; reasons.append("b17m_not_below_b34m")
                if not (high[t] > high[t - 1]):
                    ok = False; reasons.append("no_higher_high")
                if not (low[t] <= b17m[t] <= high[t]):
                    ok = False; reasons.append("b17m_not_in_range")
                if not (close[t] > b17m[t]):
                    ok = False; reasons.append("close_not_above_b17m")
                if not (b34l[t] <= close[t] <= b34u[t]):
                    ok = False; reasons.append("close_outside_bb34")
                if not (b17l[t] < b34l[t]):
                    ok = False; reasons.append("b17l_not_below_b34l")
                if any(np.isnan(v) for v in (b17m[t], b34m[t], b17l[t], b34l[t], b34u[t], high[t], low[t], close[t])):
                    ok = False; reasons.append("nan")
                events.append(dict(
                    action="LATE_BEARISH_REVERSAL" if ok else "LATE_BEARISH_REJECTED",
                    eligible=ok,
                    decision_idx=t,
                    crossing_idx=c,
                    gap=gap,
                    reason="ok" if ok else ";".join(reasons),
                ))
                if ok:
                    # consume crossing after successful event (state machine may also track)
                    last_down_cross = None

        # --- late bullish at t ---
        if last_up_cross is not None:
            c = last_up_cross
            gap = t - c
            if 1 <= gap <= 6:
                ok = True
                reasons = []
                if not (b17m[t] > b34m[t]):
                    ok = False; reasons.append("b17m_not_above_b34m")
                if not (low[t] < low[t - 1]):
                    ok = False; reasons.append("no_lower_low")
                if not (low[t] <= b17m[t] <= high[t]):
                    ok = False; reasons.append("b17m_not_in_range")
                if not (close[t] < b17m[t]):
                    ok = False; reasons.append("close_not_below_b17m")
                if not (b34l[t] <= close[t] <= b34u[t]):
                    ok = False; reasons.append("close_outside_bb34")
                if not (b17u[t] > b34u[t]):
                    ok = False; reasons.append("b17u_not_above_b34u")
                if any(np.isnan(v) for v in (b17m[t], b34m[t], b17u[t], b34u[t], b34l[t], high[t], low[t], close[t])):
                    ok = False; reasons.append("nan")
                events.append(dict(
                    action="LATE_BULLISH_REVERSAL" if ok else "LATE_BULLISH_REJECTED",
                    eligible=ok,
                    decision_idx=t,
                    crossing_idx=c,
                    gap=gap,
                    reason="ok" if ok else ";".join(reasons),
                ))
                if ok:
                    last_up_cross = None

    return events
