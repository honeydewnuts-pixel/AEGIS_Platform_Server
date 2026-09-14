"""Causal feature construction from OHLC history (server-side, never from screenshots)."""

from __future__ import annotations

from typing import Any
import math


def _closes(bars: list[dict[str, Any]]) -> list[float]:
    return [float(b["close"]) for b in bars]


def _typical(bars: list[dict[str, Any]]) -> list[float]:
    out = []
    for b in bars:
        h, l, c = float(b["high"]), float(b["low"]), float(b["close"])
        out.append((h + l + c) / 3.0)
    return out


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    window = values[-period:]
    return sum(window) / period


def stdev(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 1:
        return None
    window = values[-period:]
    m = sum(window) / period
    var = sum((x - m) ** 2 for x in window) / period
    return math.sqrt(var)


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(bars: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])
        prev_c = float(bars[i - 1]["close"])
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs) / period


def cci(bars: list[dict[str, Any]], period: int = 20) -> float | None:
    if len(bars) < period:
        return None
    tp = _typical(bars)
    window = tp[-period:]
    m = sum(window) / period
    mad = sum(abs(x - m) for x in window) / period
    if mad == 0:
        return 0.0
    return (window[-1] - m) / (0.015 * mad)


def bollinger(values: list[float], period: int = 20, k: float = 2.0) -> dict[str, float | None]:
    mid = sma(values, period)
    sd = stdev(values, period)
    if mid is None or sd is None:
        return {"mid": None, "upper": None, "lower": None, "pct_b": None}
    upper = mid + k * sd
    lower = mid - k * sd
    last = values[-1]
    width = upper - lower
    pct_b = ((last - lower) / width) if width else None
    return {"mid": mid, "upper": upper, "lower": lower, "pct_b": pct_b}


def compute_features(bars: list[dict[str, Any]]) -> dict[str, Any]:
    if not bars or len(bars) < 5:
        return {"ready": False, "reason": "insufficient_bars", "bar_count": len(bars or [])}
    c = _closes(bars)
    bb = bollinger(c, 20, 2.0)
    out: dict[str, Any] = {
        "ready": True,
        "bar_count": len(bars),
        "close": c[-1],
        "sma_20": sma(c, 20),
        "sma_50": sma(c, min(50, len(c))),
        "rsi_14": rsi(c, 14),
        "atr_14": atr(bars, 14),
        "cci_20": cci(bars, 20),
        "bb_mid": bb["mid"],
        "bb_upper": bb["upper"],
        "bb_lower": bb["lower"],
        "bb_pct_b": bb["pct_b"],
        "return_1": (c[-1] / c[-2] - 1.0) if len(c) >= 2 and c[-2] else None,
        "return_5": (c[-1] / c[-6] - 1.0) if len(c) >= 6 and c[-6] else None,
    }
    if out["rsi_14"] is not None and out["sma_20"] is not None:
        out["bias"] = (
            "bullish"
            if c[-1] > out["sma_20"] and out["rsi_14"] > 50
            else ("bearish" if c[-1] < out["sma_20"] and out["rsi_14"] < 50 else "neutral")
        )
    else:
        out["bias"] = "neutral"
    return out
