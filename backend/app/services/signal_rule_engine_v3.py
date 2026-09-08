"""AEGIS RULEBOOK_V3 v2.3.6.6 deterministic engine.

Only active production rule engine.  It uses pixel geometry inside each
panel; lower-panel comparisons are made only between lower-panel values and
price-panel comparisons only between price-panel values.  No legacy v1/v2
rules, CCI, WPR, or hidden indicators are referenced.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Side = Literal["above", "below"]
LOOKBACK = 20
TOUCH_PX = 3.0


def side_of(value_y: float, level_y: float) -> Side:
    return "above" if value_y < level_y else "below"


def crossed(prev_value_y: float, prev_level_y: float, cur_value_y: float, cur_level_y: float) -> Side | None:
    a = side_of(prev_value_y, prev_level_y)
    b = side_of(cur_value_y, cur_level_y)
    return None if a == b else b


def touched(value_y: float, level_y: float, tolerance: float = TOUCH_PX) -> bool:
    return abs(float(value_y) - float(level_y)) <= tolerance


def _valid(history: list[dict[str, Any]], key: str, band_key: str) -> bool:
    return bool(history and all(isinstance(f.get(band_key), dict) and f[band_key].get(key) is not None for f in history))


def _series(history: list[dict[str, Any]], value_key: str) -> list[float]:
    return [float(f[value_key]) for f in history if f.get(value_key) is not None]


def _band_series(history: list[dict[str, Any]], band: str, level: str) -> list[float]:
    return [float(f[band][level]) for f in history if isinstance(f.get(band), dict) and f[band].get(level) is not None]


def _pivots(values: list[float], kind: str) -> list[int]:
    if len(values) < 3:
        return []
    out: list[int] = []
    for i in range(1, len(values) - 1):
        if kind == "low" and values[i] <= values[i-1] and values[i] <= values[i+1]:
            out.append(i)
        if kind == "high" and values[i] >= values[i-1] and values[i] >= values[i+1]:
            out.append(i)
    return out


def _higher_low_pair(values: list[float]) -> bool:
    piv = _pivots(values, "low")
    if len(piv) < 2:
        return False
    a, b = piv[-2], piv[-1]
    return values[b] < values[a]  # smaller pixel y = numerically higher low


def _lower_high_pair(values: list[float]) -> bool:
    piv = _pivots(values, "high")
    if len(piv) < 2:
        return False
    a, b = piv[-2], piv[-1]
    return values[b] > values[a]  # larger pixel y = numerically lower high


def _sequential_cross(history: list[dict[str, Any]], value_key: str, band_key: str, levels: list[str], direction: str) -> bool:
    """Find ordered crosses through levels within the last 20 frames."""
    hs = history[-LOOKBACK:]
    pos = 0
    for level in levels:
        found = False
        for i in range(pos + 1, len(hs)):
            prev, cur = hs[i-1], hs[i]
            if prev.get(value_key) is None or cur.get(value_key) is None:
                continue
            pb, cb = prev.get(band_key), cur.get(band_key)
            if not isinstance(pb, dict) or not isinstance(cb, dict):
                continue
            if crossed(float(prev[value_key]), float(pb[level]), float(cur[value_key]), float(cb[level])) == direction:
                pos = i
                found = True
                break
        if not found:
            return False
    return True


def _touch_count(history: list[dict[str, Any]], value_key: str, band_key: str, level: str) -> int:
    count = 0
    for f in history[-LOOKBACK:]:
        b = f.get(band_key)
        if f.get(value_key) is not None and isinstance(b, dict) and b.get(level) is not None:
            if touched(float(f[value_key]), float(b[level])):
                count += 1
    return count


def _recent_touch_or_cross_from_side(history: list[dict[str, Any]], value_key: str, band_key: str, level: str, from_side: str) -> bool:
    hs = history[-2:]
    if len(hs) < 2:
        return False
    p, c = hs
    pb, cb = p.get(band_key), c.get(band_key)
    if not isinstance(pb, dict) or not isinstance(cb, dict) or p.get(value_key) is None or c.get(value_key) is None:
        return False
    prev_side = side_of(float(p[value_key]), float(pb[level]))
    cr = crossed(float(p[value_key]), float(pb[level]), float(c[value_key]), float(cb[level]))
    return prev_side == from_side and (touched(float(c[value_key]), float(cb[level])) or cr is not None)


def _failed_cross(history: list[dict[str, Any]], value_key: str, band_key: str, level: str, attempted_from: str) -> bool:
    hs = history[-LOOKBACK:]
    if len(hs) < 3:
        return False
    # An attempt comes within TOUCH_PX of the level while staying on the
    # requested starting side, followed by a return to that same side.
    for i in range(1, len(hs)-1):
        p, c, n = hs[i-1], hs[i], hs[i+1]
        try:
            pb, cb, nb = p[band_key], c[band_key], n[band_key]
            pv, cv, nv = float(p[value_key]), float(c[value_key]), float(n[value_key])
            if not all(isinstance(x, dict) for x in (pb, cb, nb)):
                continue
            if side_of(pv, float(pb[level])) != attempted_from:
                continue
            if not touched(cv, float(cb[level])):
                continue
            if crossed(pv, float(pb[level]), cv, float(cb[level])) is not None:
                continue
            if side_of(nv, float(nb[level])) == attempted_from:
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False


@dataclass
class RuleResult:
    fired: bool
    signal: str
    rule_name: str
    reason: str
    rule_flags: dict[str, int]
    contraction: int
    expansion: int


class SignalRuleEngineV3:
    def __init__(self, lookback: int = LOOKBACK) -> None:
        self.lookback = lookback

    def evaluate(self, history: list[dict[str, Any]]) -> RuleResult:
        if not history:
            return self._result(False, "HOLD", "warming_up", "No frame history.", {}, 0, 0)
        cur = history[-1]
        p7, p8 = cur.get("price_band7"), cur.get("price_band8")
        b1 = cur.get("band1")
        if not isinstance(p7, dict) or not isinstance(p8, dict) or not isinstance(b1, dict):
            return self._result(False, "HOLD", "indicators_not_detected", "Required v3 visible indicators not detected.", {}, 0, 0)

        # Formal rulebook operators are screen-Y operators (smaller y = higher on chart).
        # CONTRACTION: f4 < f1 AND f6 > f3  →  BB17 nested inside BB34 in Y-space.
        contraction = int(float(p8["U"]) < float(p7["U"]) and float(p8["L"]) > float(p7["L"]))
        # EXPANSION: f4 > f1 AND f6 < f3
        expansion = int(float(p8["U"]) > float(p7["U"]) and float(p8["L"]) < float(p7["L"]))

        flags = {k: 0 for k in ("RULE_A", "RULE_B", "RULE_C", "RULE_F", "EXPANSION_BUY", "EXPANSION_SELL")}
        if len(history) < 2:
            return self._result(False, "HOLD", "warming_up", "Insufficient temporal history.", flags, contraction, expansion)

        if contraction:
            flags["RULE_A"] = int(self._rule_a_buy(history) or self._rule_a_sell(history))
            flags["RULE_B"] = int(self._rule_b_buy(history) or self._rule_b_sell(history))
            flags["RULE_C"] = int(self._rule_c_buy(history) or self._rule_c_sell(history))
        flags["RULE_F"] = int(self._rule_f_buy(history) or self._rule_f_sell(history))
        if expansion:
            flags["EXPANSION_BUY"] = int(self._expansion_buy(cur))
            flags["EXPANSION_SELL"] = int(self._expansion_sell(cur))

        buys = ["RULE_A", "RULE_B", "RULE_C", "RULE_F", "EXPANSION_BUY"]
        sells = ["RULE_A", "RULE_B", "RULE_C", "RULE_F", "EXPANSION_SELL"]
        buy = any(flags[k] and getattr(self, f"_{k.lower()}_buy")(history) if k in ("RULE_A","RULE_B","RULE_C","RULE_F") else flags[k] for k in buys)
        sell = any(flags[k] and getattr(self, f"_{k.lower()}_sell")(history) if k in ("RULE_A","RULE_B","RULE_C","RULE_F") else flags[k] for k in sells)
        if buy and sell:
            return self._result(False, "HOLD", "conflicting_v3_rules", "BUY and SELL conditions fired simultaneously.", flags, contraction, expansion)
        if buy:
            fired = next(k for k in ("RULE_A","RULE_B","RULE_C","RULE_F","EXPANSION_BUY") if flags[k])
            return self._result(True, "BUY", fired, f"RULEBOOK_V3 {fired} fired.", flags, contraction, expansion)
        if sell:
            fired = next(k for k in ("RULE_A","RULE_B","RULE_C","RULE_F","EXPANSION_SELL") if flags[k])
            return self._result(True, "SELL", fired, f"RULEBOOK_V3 {fired} fired.", flags, contraction, expansion)
        return self._result(False, "HOLD", "no_rule_matched", "No v2.3.6.6 condition fired.", flags, contraction, expansion)

    def _rule_a_buy(self, h):
        """A_BUY (Y-coords as formal rulebook): f7 < f11 AND higher-lows AND
        sequential cross UP L→M→U; then f7 cross DOWN from above M while f8 > f10.
        """
        c = h[-1]
        b1 = c.get("band1")
        if not isinstance(b1, dict) or c.get("rsi6") is None or c.get("ma4") is None:
            return False
        # formal f7 < f11 (screen Y): RSI above lower band
        if float(c["rsi6"]) >= float(b1["L"]):
            return False
        f7 = [x.get("rsi6") for x in h[-LOOKBACK:]]
        f8 = [x.get("ma4") for x in h[-LOOKBACK:]]
        if any(v is None for v in f7 + f8):
            return False
        # formal f8 > f10 (screen Y) — do NOT invert relative to rulebook text
        if float(c["ma4"]) <= float(b1["M"]):
            return False
        return (
            _higher_low_pair([float(v) for v in f7])
            and _higher_low_pair([float(v) for v in f8])
            and _sequential_cross(h, "rsi6", "band1", ["L", "M", "U"], "above")
            and _recent_touch_or_cross_from_side(h, "rsi6", "band1", "M", "above")
        )

    def _rule_a_sell(self, h):
        """A_SELL (Y-coords): f7 > f9 AND lower-highs AND sequential cross DOWN U→M→L;
        then f7 cross UP from below M while f8 < f10.
        """
        c = h[-1]
        b1 = c.get("band1")
        if not isinstance(b1, dict) or c.get("rsi6") is None or c.get("ma4") is None:
            return False
        # formal f7 > f9 (screen Y): RSI below upper band
        if float(c["rsi6"]) <= float(b1["U"]):
            return False
        f7 = [x.get("rsi6") for x in h[-LOOKBACK:]]
        f8 = [x.get("ma4") for x in h[-LOOKBACK:]]
        if any(v is None for v in f7 + f8):
            return False
        # formal f8 < f10 (screen Y)
        if float(c["ma4"]) >= float(b1["M"]):
            return False
        return (
            _lower_high_pair([float(v) for v in f7])
            and _lower_high_pair([float(v) for v in f8])
            and _sequential_cross(h, "rsi6", "band1", ["U", "M", "L"], "below")
            and _recent_touch_or_cross_from_side(h, "rsi6", "band1", "M", "below")
        )

    def _rule_b_buy(self, h):
        # f7 touches f10 OR f11 >=2 AND f8 just touched/crossed f10 from above
        return (
            (_touch_count(h, "rsi6", "band1", "M") >= 2 or _touch_count(h, "rsi6", "band1", "L") >= 2)
            and _recent_touch_or_cross_from_side(h, "ma4", "band1", "M", "above")
        )

    def _rule_b_sell(self, h):
        return (
            (_touch_count(h, "rsi6", "band1", "M") >= 2 or _touch_count(h, "rsi6", "band1", "U") >= 2)
            and _recent_touch_or_cross_from_side(h, "ma4", "band1", "M", "below")
        )

    def _rule_c_buy(self, h):
        # formal: f7 < f11 AND fail cross f10; then f7 touches f11 >=2
        c = h[-1]
        b1 = c.get("band1")
        if not isinstance(b1, dict) or c.get("rsi6") is None:
            return False
        if float(c["rsi6"]) >= float(b1["L"]):  # need f7 < f11 (Y)
            return False
        return (
            _failed_cross(h, "rsi6", "band1", "M", "below")
            and _failed_cross(h, "ma4", "band1", "M", "below")
            and _touch_count(h, "rsi6", "band1", "L") >= 2
        )

    def _rule_c_sell(self, h):
        # formal: f7 > f9 AND fail cross f10; then f7 touches f9 >=2
        c = h[-1]
        b1 = c.get("band1")
        if not isinstance(b1, dict) or c.get("rsi6") is None:
            return False
        if float(c["rsi6"]) <= float(b1["U"]):  # need f7 > f9 (Y)
            return False
        return (
            _failed_cross(h, "rsi6", "band1", "M", "above")
            and _failed_cross(h, "ma4", "band1", "M", "above")
            and _touch_count(h, "rsi6", "band1", "U") >= 2
        )

    def _rule_f_buy(self, h):
        # formal: f4 < f1 AND f4 < f2 AND f4 crosses UP f2 AND (f7 cross DOWN f10 OR f7 < f11)
        if len(h) < 2:
            return False
        c, p = h[-1], h[-2]
        p7, p8 = c.get("price_band7"), c.get("price_band8")
        pp7, pp8 = p.get("price_band7"), p.get("price_band8")
        b1 = c.get("band1")
        if not all(isinstance(x, dict) for x in (p7, p8, pp7, pp8, b1)):
            return False
        cond = float(p8["U"]) < float(p7["U"]) and float(p8["U"]) < float(p7["M"])
        cross = crossed(float(pp8["U"]), float(pp7["M"]), float(p8["U"]), float(p7["M"])) == "above"
        f7 = float(c.get("rsi6", 999))
        rsi_cross = crossed(
            float(p.get("rsi6", 999)), float(p.get("band1")["M"]),
            f7, float(b1["M"]),
        ) == "below"
        return cond and cross and (rsi_cross or f7 < float(b1["L"]))

    def _rule_f_sell(self, h):
        # formal: f6 > f3 AND f6 > f2 AND f6 crosses DOWN f2 AND (f7 cross UP f10 OR f7 > f9)
        if len(h) < 2:
            return False
        c, p = h[-1], h[-2]
        p7, p8 = c.get("price_band7"), c.get("price_band8")
        pp7, pp8 = p.get("price_band7"), p.get("price_band8")
        b1 = c.get("band1")
        if not all(isinstance(x, dict) for x in (p7, p8, pp7, pp8, b1)):
            return False
        cond = float(p8["L"]) > float(p7["L"]) and float(p8["L"]) > float(p7["M"])
        cross = crossed(float(pp8["L"]), float(pp7["M"]), float(p8["L"]), float(p7["M"])) == "below"
        f7 = float(c.get("rsi6", -999))
        rsi_cross = crossed(
            float(p.get("rsi6", -999)), float(p.get("band1")["M"]),
            f7, float(b1["M"]),
        ) == "above"
        return cond and cross and (rsi_cross or f7 > float(b1["U"]))

    def _expansion_buy(self, c):
        # formal EXPANSION AND (f7 < f11 OR f8 < f11) — screen Y, not inverted
        b1 = c.get("band1")
        if not isinstance(b1, dict):
            return False
        r = c.get("rsi6")
        m = c.get("ma4")
        return (r is not None and float(r) < float(b1["L"])) or (m is not None and float(m) < float(b1["L"]))

    def _expansion_sell(self, c):
        # formal EXPANSION AND (f7 > f9 OR f8 > f9)
        b1 = c.get("band1")
        if not isinstance(b1, dict):
            return False
        r = c.get("rsi6")
        m = c.get("ma4")
        return (r is not None and float(r) > float(b1["U"])) or (m is not None and float(m) > float(b1["U"]))

    @staticmethod
    def _result(fired, signal, name, reason, flags, contraction, expansion):
        return RuleResult(fired, signal, name, reason, flags, contraction, expansion)
