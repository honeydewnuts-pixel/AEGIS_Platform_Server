"""
====================================================================
Project : AEGIS
Company : Honeydewnuts Nigerian Limited

File    : signal_rule_engine_v3.py

Purpose
-------
Evaluates AEGIS Rulebook v3 (v2.3.6.6) against a frame history and
returns a signal. This is a NEW, separate engine class - it does not
touch or replace the v1/v2 `SignalRuleEngine` in signal_rule_engine.py,
so activating v3 (via TemplateProfileService) is opt-in and v1/v2
behaviour is unaffected until BrainCVService is told to switch.

Indicator stack (see indicator_stack_v3.json):
  #7 BB34, White,  Period 34, price panel, Apply to Close
  #8 BB17, Cyan,   Period 17, price panel, Apply to Close
  #6 RSI9, Cyan,   Period 9,  lower panel, Apply to Close
  #4 MA7,  Magenta,SMA Period 7, lower panel, Apply to RSI9(#6)
  #1 Bands34, White, Period 34, lower panel, Apply to MA7(#4)

Coordinate convention
----------------------
Same as v1/v2: all positions are pixel Y-coordinates. Smaller Y is
higher on the chart / a higher indicator value. "Above" = smaller Y.

Frame state shape (one entry per historical frame):
{
    "price_band7": {"U": y, "M": y, "L": y},  # #7 BB34 white, price panel
    "price_band8": {"U": y, "M": y, "L": y},  # #8 BB17 cyan, price panel
    "rsi6":  y,                                # #6 RSI9  -> rulebook f7
    "ma4":   y,                                # #4 MA7 (on RSI9) -> f8
    "band1": {"U": y, "M": y, "L": y},         # #1 Bands34 (on MA7) -> f9/f10/f11
    "_ts": float,
}

Rulebook feature-name cross-reference (value terms, for readability):
    f1=price_band7.U  f2=price_band7.M  f3=price_band7.L
    f4=price_band8.U  f5=price_band8.M  f6=price_band8.L
    f7=rsi6  f8=ma4  f9=band1.U  f10=band1.M  f11=band1.L

WHAT'S IMPLEMENTED VS. FLAGGED
-------------------------------
Implemented with confidence:
  - CONTRACTION / EXPANSION regime detection
  - RULE B (BUY/SELL) - touch-count + confirming cross, both terms are
    unambiguous as written.
  - RULE C (BUY/SELL) - failed cross of the mid-band followed by
    repeated touches of the outer band.
  - RULE F (BUY/SELL) - #8 vs #1/#2-band relation with RSI confirmation.
  - EXPANSION BUY/SELL - simple, unambiguous comparison.

Flagged (implemented as best-effort, NOT confirmed against a labeled
example - see RULEBOOK_V3_TODO at the bottom):
  - RULE A (BUY/SELL). The rulebook text ("f7 & f8 make Higher Low",
    "cross UP f11->f10->f9", "then f7 cross DOWN f10/f11 while f8 >
    f10") requires three judgment calls that aren't pinned down by the
    text: (a) what counts as a pivot for "Higher Low" on a possibly
    noisy oscillator, (b) whether the three sequential crosses must
    happen on consecutive frames or just in order within a window,
    and (c) how large a window "then" implies before the reversal
    cross must occur. The implementation below uses a 3-frame pivot
    detector and a 20-frame sequencing window - both configurable -
    but this is a documented guess, not a confirmed spec. Recommend
    watching `rule_a_buy` / `rule_a_sell` in signal telemetry
    separately before trusting them at the same confidence as B/C/F.
====================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.signal_rule_engine import RuleResult, crossed, is_between, side_of

TOUCH_TOLERANCE_PX_DEFAULT = 6.0   # pixels; "touch" = within this many px on the RSI-scale panel
TOUCH_WINDOW_DEFAULT = 20          # frames; matches rulebook's "within 20 bars"
PIVOT_HALF_WIDTH_DEFAULT = 1       # frames each side for a local min/max pivot


# ------------------------------------------------------------------
# v3-specific primitives (touches / pivot patterns / sequenced crosses)
# ------------------------------------------------------------------

def touches(a_series: list[float], b_series: list[float], tol_px: float) -> int:
    """Count of frames where |a - b| <= tol_px, i.e. the two lines are
    close enough on screen to call it a touch rather than a clean cross."""
    n = min(len(a_series), len(b_series))
    return sum(1 for i in range(n) if abs(a_series[i] - b_series[i]) <= tol_px)


def find_pivots(series: list[float], half_width: int = PIVOT_HALF_WIDTH_DEFAULT):
    """Local minima (price-sense highs, i.e. smallest Y) and maxima
    (price-sense lows, i.e. largest Y) using a +/-half_width window."""
    lows_y, highs_y = [], []  # "lows_y" = pivot points with the SMALLEST y (highest value)
    n = len(series)
    for i in range(half_width, n - half_width):
        window = series[i - half_width:i + half_width + 1]
        if series[i] == min(window):
            lows_y.append(i)
        if series[i] == max(window):
            highs_y.append(i)
    return lows_y, highs_y


def higher_low_pattern(series: list[float]) -> bool:
    """True if the series makes a 'Higher Low' in value terms: two
    value-troughs (pivot points with the LARGEST y) where the later
    trough is higher in value (SMALLER y) than the earlier one."""
    _, highs_y_idx = find_pivots(series)  # value-troughs = local Y maxima
    if len(highs_y_idx) < 2:
        return False
    a, b = series[highs_y_idx[-2]], series[highs_y_idx[-1]]
    return b < a  # later trough has smaller y => higher value => Higher Low


def lower_high_pattern(series: list[float]) -> bool:
    """Mirror of higher_low_pattern: two value-peaks (local Y minima)
    where the later peak is lower in value (LARGER y)."""
    lows_y_idx, _ = find_pivots(series)  # value-peaks = local Y minima
    if len(lows_y_idx) < 2:
        return False
    a, b = series[lows_y_idx[-2]], series[lows_y_idx[-1]]
    return b > a  # later peak has larger y => lower value => Lower High


def any_cross_in_window(value_series: list[float], level_series: list[float], direction: str) -> bool:
    n = min(len(value_series), len(level_series))
    for i in range(1, n):
        if crossed(value_series[i - 1], level_series[i - 1], value_series[i], level_series[i]) == direction:
            return True
    return False


# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------

class SignalRuleEngineV3:
    """
    Evaluates history (a list of v3 frame_state dicts, oldest first)
    against AEGIS Rulebook v3. Needs at least 2 frames for CONTRACTION/
    EXPANSION + Rules B/C/F; touch-count and Rule A benefit from a
    full `touch_window` of frames.
    """

    def __init__(self, touch_window: int = TOUCH_WINDOW_DEFAULT,
                 touch_tolerance_px: float = TOUCH_TOLERANCE_PX_DEFAULT,
                 enable_rule_a: bool = True) -> None:
        self.touch_window = touch_window
        self.touch_tolerance_px = touch_tolerance_px
        self.enable_rule_a = enable_rule_a

    def evaluate(self, history: list[dict[str, Any]]) -> RuleResult:
        n = len(history)
        if n < 2:
            return RuleResult(False, "HOLD", "warming_up",
                               f"Collecting frames ({n}/2). Need at least 2 for v3 rules.")

        prev, cur = history[-2], history[-1]
        if not self._frame_ok(prev) or not self._frame_ok(cur):
            return RuleResult(False, "HOLD", "indicators_not_detected",
                               "Could not read one or more v3 indicators (price_band7/8, rsi6, ma4, band1).")

        window = history[-self.touch_window:]

        contraction = self._contraction(cur)
        expansion = self._expansion(cur)

        for rule_fn in self._rules(contraction, expansion):
            try:
                result = rule_fn(prev, cur, window, history)
            except Exception:
                continue
            if result is not None and result.fired:
                return result

        regime = "contraction" if contraction else ("expansion" if expansion else "neutral")
        return RuleResult(False, "HOLD", "no_rule_matched", f"No v3 condition fully matched this frame ({regime}).")

    @staticmethod
    def _frame_ok(fr: dict) -> bool:
        if not isinstance(fr.get("price_band7"), dict) or not isinstance(fr.get("price_band8"), dict):
            return False
        if not isinstance(fr.get("band1"), dict):
            return False
        if fr.get("rsi6") is None or fr.get("ma4") is None:
            return False
        for band_key in ("price_band7", "price_band8", "band1"):
            for k in ("U", "M", "L"):
                if fr[band_key].get(k) is None:
                    return False
        return True

    # ---- regime ----

    @staticmethod
    def _contraction(cur: dict) -> bool:
        """CONTRACTION = f4 < f1 AND f6 > f3 (#8 band nested inside #7 band)."""
        p7, p8 = cur["price_band7"], cur["price_band8"]
        return side_of(p8["U"], p7["U"]) == "below" and side_of(p8["L"], p7["L"]) == "above"

    @staticmethod
    def _expansion(cur: dict) -> bool:
        """EXPANSION = f4 > f1 AND f6 < f3 (#8 band wider than #7 band)."""
        p7, p8 = cur["price_band7"], cur["price_band8"]
        return side_of(p8["U"], p7["U"]) == "above" and side_of(p8["L"], p7["L"]) == "below"

    def _rules(self, contraction: bool, expansion: bool):
        rules = []
        if expansion:
            rules += [self._rule_expansion_buy, self._rule_expansion_sell]
        if contraction:
            rules += [self._rule_b_buy, self._rule_b_sell,
                      self._rule_c_buy, self._rule_c_sell,
                      self._rule_f_buy, self._rule_f_sell]
            if self.enable_rule_a:
                rules += [self._rule_a_buy, self._rule_a_sell]
        return rules

    # ---- EXPANSION rules ----

    def _rule_expansion_buy(self, prev, cur, window, history) -> RuleResult | None:
        f7, f8, f11 = cur["rsi6"], cur["ma4"], cur["band1"]["L"]
        fired = side_of(f7, f11) == "above" or side_of(f8, f11) == "above"
        return RuleResult(fired, "BUY" if fired else None, "expansion_buy",
                           f"expansion=True, f7<f11={side_of(f7, f11) == 'above'}, f8<f11={side_of(f8, f11) == 'above'}")

    def _rule_expansion_sell(self, prev, cur, window, history) -> RuleResult | None:
        f7, f8, f9 = cur["rsi6"], cur["ma4"], cur["band1"]["U"]
        fired = side_of(f7, f9) == "below" or side_of(f8, f9) == "below"
        return RuleResult(fired, "SELL" if fired else None, "expansion_sell",
                           f"expansion=True, f7>f9={side_of(f7, f9) == 'below'}, f8>f9={side_of(f8, f9) == 'below'}")

    # ---- RULE B ----

    def _rule_b_buy(self, prev, cur, window, history) -> RuleResult | None:
        f7 = [f["rsi6"] for f in window]
        f10 = [f["band1"]["M"] for f in window]
        f11 = [f["band1"]["L"] for f in window]
        t = max(touches(f7, f10, self.touch_tolerance_px), touches(f7, f11, self.touch_tolerance_px))
        just_crossed = crossed(prev["ma4"], prev["band1"]["M"], cur["ma4"], cur["band1"]["M"]) == "below"
        near = abs(cur["ma4"] - cur["band1"]["M"]) <= self.touch_tolerance_px
        below_or_at = side_of(cur["ma4"], cur["band1"]["M"]) != "above"
        fired = t >= 2 and (just_crossed or near) and below_or_at
        return RuleResult(fired, "BUY" if fired else None, "rule_b_buy",
                           f"touches(f7,f10/f11)={t}, f8_cross_down_f10={just_crossed}, f8<=f10={below_or_at}")

    def _rule_b_sell(self, prev, cur, window, history) -> RuleResult | None:
        f7 = [f["rsi6"] for f in window]
        f9 = [f["band1"]["U"] for f in window]
        f10 = [f["band1"]["M"] for f in window]
        t = max(touches(f7, f10, self.touch_tolerance_px), touches(f7, f9, self.touch_tolerance_px))
        just_crossed = crossed(prev["ma4"], prev["band1"]["M"], cur["ma4"], cur["band1"]["M"]) == "above"
        near = abs(cur["ma4"] - cur["band1"]["M"]) <= self.touch_tolerance_px
        above_or_at = side_of(cur["ma4"], cur["band1"]["M"]) != "below"
        fired = t >= 2 and (just_crossed or near) and above_or_at
        return RuleResult(fired, "SELL" if fired else None, "rule_b_sell",
                           f"touches(f7,f10/f9)={t}, f8_cross_up_f10={just_crossed}, f8>=f10={above_or_at}")

    # ---- RULE C ----

    def _rule_c_buy(self, prev, cur, window, history) -> RuleResult | None:
        f7 = [f["rsi6"] for f in window]
        f10 = [f["band1"]["M"] for f in window]
        f11 = [f["band1"]["L"] for f in window]
        attempted = touches(f7, f10, self.touch_tolerance_px) >= 1
        confirmed_cross = any_cross_in_window(f7, f10, "above") or any_cross_in_window(f7, f10, "below")
        failed = attempted and not confirmed_cross
        below_f11 = side_of(cur["rsi6"], cur["band1"]["L"]) == "above"
        t_outer = touches(f7, f11, self.touch_tolerance_px)
        fired = below_f11 and failed and t_outer >= 2
        return RuleResult(fired, "BUY" if fired else None, "rule_c_buy",
                           f"f7<f11={below_f11}, tried_and_failed_cross_f10={failed}, touches(f7,f11)={t_outer}")

    def _rule_c_sell(self, prev, cur, window, history) -> RuleResult | None:
        f7 = [f["rsi6"] for f in window]
        f9 = [f["band1"]["U"] for f in window]
        f10 = [f["band1"]["M"] for f in window]
        attempted = touches(f7, f10, self.touch_tolerance_px) >= 1
        confirmed_cross = any_cross_in_window(f7, f10, "above") or any_cross_in_window(f7, f10, "below")
        failed = attempted and not confirmed_cross
        above_f9 = side_of(cur["rsi6"], cur["band1"]["U"]) == "below"
        t_outer = touches(f7, f9, self.touch_tolerance_px)
        fired = above_f9 and failed and t_outer >= 2
        return RuleResult(fired, "SELL" if fired else None, "rule_c_sell",
                           f"f7>f9={above_f9}, tried_and_failed_cross_f10={failed}, touches(f7,f9)={t_outer}")

    # ---- RULE F ----

    def _rule_f_buy(self, prev, cur, window, history) -> RuleResult | None:
        p7, p8 = cur["price_band7"], cur["price_band8"]
        pp8 = prev["price_band8"]
        f4_below_f1 = side_of(p8["U"], p7["U"]) == "below"
        f4_below_f2 = side_of(p8["U"], p7["M"]) == "below"
        f4_cross_up_f2 = crossed(pp8["U"], prev["price_band7"]["M"], p8["U"], p7["M"]) == "above"
        f7_cross_down_f10 = crossed(prev["rsi6"], prev["band1"]["M"], cur["rsi6"], cur["band1"]["M"]) == "below"
        f7_below_f11 = side_of(cur["rsi6"], cur["band1"]["L"]) == "above"
        fired = f4_below_f1 and f4_below_f2 and f4_cross_up_f2 and (f7_cross_down_f10 or f7_below_f11)
        return RuleResult(fired, "BUY" if fired else None, "rule_f_buy",
                           f"f4<f1={f4_below_f1}, f4<f2={f4_below_f2}, f4_x_up_f2={f4_cross_up_f2}, "
                           f"rsi_confirm={f7_cross_down_f10 or f7_below_f11}")

    def _rule_f_sell(self, prev, cur, window, history) -> RuleResult | None:
        p7, p8 = cur["price_band7"], cur["price_band8"]
        pp8 = prev["price_band8"]
        f6_above_f3 = side_of(p8["L"], p7["L"]) == "above"
        f6_above_f2 = side_of(p8["L"], p7["M"]) == "above"
        f6_cross_down_f2 = crossed(pp8["L"], prev["price_band7"]["M"], p8["L"], p7["M"]) == "below"
        f7_cross_up_f10 = crossed(prev["rsi6"], prev["band1"]["M"], cur["rsi6"], cur["band1"]["M"]) == "above"
        f7_above_f9 = side_of(cur["rsi6"], cur["band1"]["U"]) == "below"
        fired = f6_above_f3 and f6_above_f2 and f6_cross_down_f2 and (f7_cross_up_f10 or f7_above_f9)
        return RuleResult(fired, "SELL" if fired else None, "rule_f_sell",
                           f"f6>f3={f6_above_f3}, f6>f2={f6_above_f2}, f6_x_down_f2={f6_cross_down_f2}, "
                           f"rsi_confirm={f7_cross_up_f10 or f7_above_f9}")

    # ---- RULE A (flagged - see module docstring) ----

    def _rule_a_buy(self, prev, cur, window, history) -> RuleResult | None:
        f7 = [f["rsi6"] for f in window]
        f8_last = cur["ma4"]
        f9 = [f["band1"]["U"] for f in window]
        f10 = [f["band1"]["M"] for f in window]
        f11 = [f["band1"]["L"] for f in window]

        below_f11 = side_of(cur["rsi6"], cur["band1"]["L"]) == "above"
        hl = higher_low_pattern(f7)
        seq_up = (any_cross_in_window(f7, f11, "above")
                  and any_cross_in_window(f7, f10, "above")
                  and any_cross_in_window(f7, f9, "above"))
        rev_down = (crossed(prev["rsi6"], prev["band1"]["M"], cur["rsi6"], cur["band1"]["M"]) == "below"
                    or crossed(prev["rsi6"], prev["band1"]["L"], cur["rsi6"], cur["band1"]["L"]) == "below")
        f8_above_f10 = side_of(f8_last, cur["band1"]["M"]) == "above"

        fired = below_f11 and hl and seq_up and rev_down and f8_above_f10
        return RuleResult(fired, "BUY" if fired else None, "rule_a_buy_experimental",
                           f"[best-effort interpretation] f7<f11={below_f11}, higher_low={hl}, "
                           f"seq_cross_up={seq_up}, reversal_cross_down={rev_down}, f8>f10={f8_above_f10}")

    def _rule_a_sell(self, prev, cur, window, history) -> RuleResult | None:
        f7 = [f["rsi6"] for f in window]
        f8_last = cur["ma4"]
        f9 = [f["band1"]["U"] for f in window]
        f10 = [f["band1"]["M"] for f in window]
        f11 = [f["band1"]["L"] for f in window]

        above_f9 = side_of(cur["rsi6"], cur["band1"]["U"]) == "below"
        lh = lower_high_pattern(f7)
        seq_down = (any_cross_in_window(f7, f9, "below")
                    and any_cross_in_window(f7, f10, "below")
                    and any_cross_in_window(f7, f11, "below"))
        rev_up = (crossed(prev["rsi6"], prev["band1"]["M"], cur["rsi6"], cur["band1"]["M"]) == "above"
                  or crossed(prev["rsi6"], prev["band1"]["U"], cur["rsi6"], cur["band1"]["U"]) == "above")
        f8_below_f10 = side_of(f8_last, cur["band1"]["M"]) == "below"

        fired = above_f9 and lh and seq_down and rev_up and f8_below_f10
        return RuleResult(fired, "SELL" if fired else None, "rule_a_sell_experimental",
                           f"[best-effort interpretation] f7>f9={above_f9}, lower_high={lh}, "
                           f"seq_cross_down={seq_down}, reversal_cross_up={rev_up}, f8<f10={f8_below_f10}")


# ------------------------------------------------------------------
# Flagged ambiguity - see module docstring for detail.
# ------------------------------------------------------------------
RULEBOOK_V3_TODO = [
    {
        "rule": "RULE A (BUY/SELL)",
        "ambiguous_phrase": "\"f7 & f8 make Higher Low\" then \"cross UP f11->f10->f9\" then "
                             "\"f7 cross DOWN f10/f11 while f8 > f10\" - pivot definition, cross "
                             "sequencing window, and the gap before the reversal cross are all "
                             "underspecified. Implemented with a documented best-effort guess "
                             "(see class docstring); confirm against a labeled example before "
                             "trusting at the same confidence as Rules B/C/F.",
    },
    {
        "rule": "TOUCH (all rules)",
        "ambiguous_phrase": "\"2 or 3 touches within 20 bars\" doesn't specify a pixel/price "
                             "tolerance for what counts as a touch vs. a clean cross. Defaulted "
                             "to touch_tolerance_px=6.0 - tune per the actual rendered chart "
                             "resolution and confirm visually.",
    },
]
