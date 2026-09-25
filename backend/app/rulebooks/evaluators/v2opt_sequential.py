"""Research-safe sequential V2-OPT rule evaluation from OHLC bars.

Interprets entry_spec / exit_spec from AEGIS-RB-V2OPT-* rulebook JSON.
Never sets production_authorized. Fail-closed on insufficient history.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def _rsi(closes: np.ndarray, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    d = np.diff(closes[-(period + 1) :])
    gains = np.clip(d, 0, None)
    losses = np.clip(-d, 0, None)
    ag = gains.mean()
    al = losses.mean()
    if al <= 1e-12:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return float(100 - (100 / (1 + rs)))


def _sma(x: np.ndarray, n: int) -> float | None:
    if len(x) < n:
        return None
    return float(np.mean(x[-n:]))


def evaluate_v2opt_from_bars(
    bars: list[dict[str, Any]],
    rulebook: dict[str, Any],
) -> dict[str, Any]:
    """
    bars: list of {open,high,low,close} oldest→newest
    Returns signal HOLD/BUY/SELL with research confidence only.
    """
    base = {
        "signal": "HOLD",
        "confidence": 0.0,
        "rule_name": rulebook.get("rulebook_id", "v2opt"),
        "production_authorized": False,
        "details": "",
    }
    if not isinstance(bars, list) or len(bars) < 30:
        base["details"] = "Insufficient OHLC history for V2-OPT evaluation."
        base["rule_name"] = "v2opt_insufficient_history"
        return base

    try:
        closes = np.array([float(b.get("close", b.get("c"))) for b in bars], dtype=float)
        highs = np.array([float(b.get("high", b.get("h", b.get("close")))) for b in bars], dtype=float)
        lows = np.array([float(b.get("low", b.get("l", b.get("close")))) for b in bars], dtype=float)
    except (TypeError, ValueError):
        base["details"] = "Unparseable OHLC bars."
        base["rule_name"] = "v2opt_bad_bars"
        return base

    rsi = _rsi(closes, 14)
    sma10 = _sma(closes, 10)
    sma20 = _sma(closes, 20)
    if rsi is None or sma10 is None or sma20 is None:
        base["details"] = "Feature warm-up incomplete."
        base["rule_name"] = "v2opt_warmup"
        return base

    trend = 1 if sma10 > sma20 else -1
    entry = rulebook.get("entry_spec") or {}
    direction = (rulebook.get("direction") or "LONG").upper()
    hit = True
    reasons = []

    if "rsi14_lt" in entry:
        thr = float(entry["rsi14_lt"])
        ok = rsi < thr
        hit = hit and ok
        reasons.append(f"rsi14={rsi:.1f}<{thr}:{ok}")
    if "rsi14_gt" in entry:
        thr = float(entry["rsi14_gt"])
        ok = rsi > thr
        hit = hit and ok
        reasons.append(f"rsi14={rsi:.1f}>{thr}:{ok}")
    if entry.get("trend_non_negative"):
        ok = trend >= 0
        hit = hit and ok
        reasons.append(f"trend>={0}:{ok}")
    if entry.get("trend_non_positive"):
        ok = trend <= 0
        hit = hit and ok
        reasons.append(f"trend<=0:{ok}")

    # Optional BB% / zscore need longer window — soft skip if not computable
    if "bb_pct_lt" in entry or "bb_pct_gt" in entry or "z60_lt" in entry:
        if len(closes) >= 20:
            mid = closes[-20:].mean()
            sd = closes[-20:].std()
            if sd > 1e-12:
                bb_pct = (closes[-1] - (mid - 2 * sd)) / (4 * sd)
                if "bb_pct_lt" in entry:
                    ok = bb_pct < float(entry["bb_pct_lt"])
                    hit = hit and ok
                    reasons.append(f"bb_pct={bb_pct:.3f}:{ok}")
                if "bb_pct_gt" in entry:
                    ok = bb_pct > float(entry["bb_pct_gt"])
                    hit = hit and ok
                    reasons.append(f"bb_pct={bb_pct:.3f}:{ok}")
        if "z60_lt" in entry and len(closes) >= 60:
            m60 = closes[-60:].mean()
            s60 = closes[-60:].std()
            if s60 > 1e-12:
                z = (closes[-1] - m60) / s60
                ok = z < float(entry["z60_lt"])
                hit = hit and ok
                reasons.append(f"z60={z:.2f}:{ok}")

    if not hit:
        base["details"] = "Entry conditions not met. " + "; ".join(reasons)
        base["rule_name"] = rulebook.get("winner_rule_id") or rulebook.get("rulebook_id")
        return base

    # Research signal only
    signal = "BUY" if direction == "LONG" else "SELL"
    # Confidence from distance to threshold (capped research scale)
    conf = 0.55
    if "rsi14_lt" in entry:
        conf = min(0.85, 0.55 + (float(entry["rsi14_lt"]) - rsi) / 40.0)
    if "rsi14_gt" in entry:
        conf = min(0.85, 0.55 + (rsi - float(entry["rsi14_gt"])) / 40.0)

    exit_spec = rulebook.get("exit_spec") or {}
    base.update(
        {
            "signal": signal,
            "demo_actionable": True,
            "production_authorized": False,
            "confidence": float(max(0.0, min(conf, 0.85))),
            "rule_name": rulebook.get("winner_rule_id") or rulebook.get("rulebook_id"),
            "details": (
                f"V2-OPT research signal {signal}. "
                + "; ".join(reasons)
                + f". exit={exit_spec}. production_authorized=false."
            ),
            "exit_spec": exit_spec,
            "analysis_path": "v2opt_research_ohlc",
        }
    )
    return base
