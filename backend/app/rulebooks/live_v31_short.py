"""
Live (streaming OHLC) evaluation of frozen V31 SHORT entry logic.

Source of truth: backend/app/rulebooks/evaluators/v31_gbpusd_5m.py
+ registry/v53_6/*/rulebook.json execution block (SHORT only).

Does NOT implement confidence-flip, BUY entries, or demo_ohlc_structure.
Exit management (BE / trail / max hold) is defined in cash-test simulate_short;
live Executor currently receives initial SL only — see restoration report.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.rulebooks.evaluators.common import wilder_atr14

L = 12  # frozen structural window


def _bars_to_arrays(bars: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Use OHLC as Bid proxy when broker Bid/Ask series is not in the stream."""
    h, l, c = [], [], []
    for b in bars:
        if not isinstance(b, dict):
            continue
        try:
            hi = float(b.get("high") if b.get("high") is not None else b.get("BidHigh"))
            lo = float(b.get("low") if b.get("low") is not None else b.get("BidLow"))
            cl = float(b.get("close") if b.get("close") is not None else b.get("BidClose"))
        except (TypeError, ValueError):
            continue
        h.append(hi)
        l.append(lo)
        c.append(cl)
    return np.asarray(h, float), np.asarray(l, float), np.asarray(c, float)


def v31_short_signal_at_index(
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    atr: np.ndarray,
    i: int,
    last_down_i: int,
) -> tuple[bool, int, str]:
    """
    Exact V31 entry filters at bar index i.
    Returns (is_signal, new_last_down_i, reason).
    Throttle advances before exhaustion/compression filters (frozen behavior).
    """
    n = len(c)
    if i < L + 1 or i >= n:
        return False, last_down_i, "index_out_of_range"
    window_h = h[i - L : i]
    window_l = l[i - L : i]
    sh = float(np.max(window_h))
    sl = float(np.min(window_l))
    if not np.isfinite(atr[i]) or sh <= sl:
        return False, last_down_i, "atr_or_structure_invalid"
    if c[i] >= sl:
        return False, last_down_i, "no_down_break"
    if i - last_down_i < 12:
        return False, last_down_i, "event_throttle"
    # Frozen: advance throttle even if later filters fail
    new_last = i
    consumed = (c[i - L] - c[i - 1]) / (sh - sl)
    if not (consumed < 0.5):
        return False, new_last, "exhaustion_fail"
    prev_ranges = h[i - L : i] - l[i - L : i]
    prev_atr = atr[i - L : i]
    if not np.all(np.isfinite(prev_atr)):
        return False, new_last, "prev_atr_nan"
    if float(np.mean(prev_ranges / prev_atr)) >= 1.0:
        return False, new_last, "compression_fail"
    return True, new_last, "v31_short_entry"


def evaluate_live_v31_short(
    bars: list[dict[str, Any]],
    *,
    rulebook_id: str,
    instrument: str,
) -> dict[str, Any]:
    """
    Evaluate whether the latest *closed* bar is a V31 SHORT signal.
    Expects chronological bars (oldest→newest) including history for ATR.
    """
    h, l, c = _bars_to_arrays(bars)
    n = len(c)
    if n < L + 20:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": rulebook_id,
            "details": f"Insufficient bars for V31 SHORT ({n} < {L + 20}).",
            "direction": "SHORT",
            "methodology": "v31_short_baseline",
            "demo_actionable": False,
            "production_authorized": False,
            "initial_stop_atr_mult": 1.5,
            "max_hold_bars": 72,
        }
    atr = wilder_atr14(h, l, c)
    # Walk history to maintain throttle state through last bar
    last_down = -10**9
    fired = False
    reason = "no_signal"
    for i in range(L + 1, n):
        ok, last_down, reason = v31_short_signal_at_index(h, l, c, atr, i, last_down)
        if ok and i == n - 1:
            fired = True
    if not fired:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": rulebook_id,
            "details": f"V31 SHORT baseline: no entry on latest closed bar ({reason}).",
            "direction": "SHORT",
            "methodology": "v31_short_baseline",
            "demo_actionable": False,
            "production_authorized": False,
            "initial_stop_atr_mult": 1.5,
            "max_hold_bars": 72,
            "atr14": float(atr[-1]) if np.isfinite(atr[-1]) else None,
        }
    atr_i = float(atr[-1])
    return {
        "signal": "SELL",  # SHORT only
        "confidence": 1.0,  # binary rule fire; not demo slope confidence
        "rule_name": rulebook_id,
        "details": (
            f"V31 SHORT entry (frozen filters) on {instrument}: "
            "12-bar compression + low exhaustion + down-break. "
            "Cash-test exits: 1.5*ATR SL, BE at +1R, trail 0.75*ATR, max 72 bars."
        ),
        "direction": "SHORT",
        "methodology": "v31_short_baseline",
        "demo_actionable": False,
        "production_authorized": False,
        "initial_stop_atr_mult": 1.5,
        "break_even_r": 1.0,
        "trail_atr_mult": 0.75,
        "max_hold_bars": 72,
        "atr14": atr_i,
        "entry_side": "AskOpen_next_bar",  # cash-test semantics
        "stop_trigger": "BidHigh",
    }
