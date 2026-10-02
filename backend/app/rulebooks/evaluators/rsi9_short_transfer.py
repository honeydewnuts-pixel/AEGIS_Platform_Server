"""
Live RSI9 SHORT transfer evaluator (research-qualified rulebooks).

Matches discovery / transfer research:
  - Signal: RSI(9) > threshold on closed bar i (mid close)
  - Entry timing: next bar (caller supplies CLOSED bar context; we signal on bar i for
    next-bar execution by the Executor)
  - Direction: SHORT only → signal SELL
  - Stop / BE / trail metadata attached for position manager (not filled here)

Does not modify V31/V53.6 evaluators.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _rsi_wilder(close: np.ndarray, period: int = 9) -> np.ndarray:
    d = np.diff(close, prepend=close[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    n = len(close)
    avg_up = np.zeros(n)
    avg_dn = np.zeros(n)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    avg_up[period] = up[1 : period + 1].mean()
    avg_dn[period] = dn[1 : period + 1].mean()
    for i in range(period + 1, n):
        avg_up[i] = (avg_up[i - 1] * (period - 1) + up[i]) / period
        avg_dn[i] = (avg_dn[i - 1] * (period - 1) + dn[i]) / period
    rs = np.divide(avg_up, avg_dn, out=np.zeros(n), where=avg_dn > 1e-12)
    out = 100.0 - (100.0 / (1.0 + rs))
    out[:period] = np.nan
    return out


def _atr_wilder(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 14) -> np.ndarray:
    prev = np.roll(c, 1)
    prev[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    n = len(c)
    out = np.zeros(n)
    out[:period] = np.nan
    if n <= period:
        return out
    out[period] = tr[1 : period + 1].mean()
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def _bars_to_arrays(bars: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    o, h, l, c = [], [], [], []
    for b in bars:
        if not isinstance(b, dict):
            continue
        try:
            # Prefer mid; fall back to close-only fields
            cl = b.get("close")
            hi = b.get("high", cl)
            lo = b.get("low", cl)
            op = b.get("open", cl)
            c.append(float(cl))
            h.append(float(hi))
            l.append(float(lo))
            o.append(float(op))
        except (TypeError, ValueError):
            continue
    return (
        np.asarray(o, dtype=float),
        np.asarray(h, dtype=float),
        np.asarray(l, dtype=float),
        np.asarray(c, dtype=float),
    )


def load_rsi9_rulebook(instrument: str, repo_root: Path | None = None) -> dict[str, Any] | None:
    root = repo_root or Path(__file__).resolve().parents[4]
    path = root / "registry" / "v40" / "rulebooks_rsi9_short" / f"{instrument.upper()}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("status") == "TRANSFER_REJECTED":
        return None
    if data.get("production_authorized") is True:
        # Still research path unless explicitly authorized elsewhere
        pass
    return data


def evaluate_rsi9_short_from_bars(
    bars: list[dict[str, Any]],
    *,
    instrument: str,
    rulebook: dict[str, Any] | None = None,
    rsi_period: int = 9,
    rsi_threshold: float = 70.0,
) -> dict[str, Any]:
    """
    Evaluate latest CLOSED bar for RSI9 SHORT entry signal.

    Returns signal HOLD or SELL with methodology=rsi9_transfer.
    Incomplete history → HOLD fail-closed.
    """
    rb = rulebook or load_rsi9_rulebook(instrument)
    rid = (rb or {}).get("rulebook_id") or f"AEGIS-RB-TRANSFER-RSI9-SHORT-M5-{instrument.upper()}"
    if rb is None:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "rsi9_rulebook_missing",
            "details": f"No RSI9 SHORT rulebook for {instrument}.",
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    # Parse threshold from entry.logic if present
    thr = rsi_threshold
    entry = rb.get("entry") or {}
    logic = str(entry.get("logic") or "")
    if "RSI(9)" in logic and ">" in logic:
        try:
            thr = float(logic.split(">")[-1].strip().split()[0])
        except Exception:
            thr = 70.0

    exit_cfg = rb.get("exit") or {}
    stop_atr = 1.0
    trail_atr = 0.5
    max_hold = 72
    try:
        # "entry+1.0*ATR(14)"
        stop_s = str(exit_cfg.get("initial_stop") or "1.0")
        if "ATR" in stop_s:
            stop_atr = float(stop_s.split("+")[-1].split("*")[0].strip() or "1.0")
        else:
            stop_atr = float(stop_s)
    except Exception:
        stop_atr = 1.0
    try:
        trail_s = str(exit_cfg.get("trailing_stop") or "0.5")
        trail_atr = float(trail_s.split("*")[0].replace("ATR", "").strip().split()[0] or "0.5")
    except Exception:
        trail_atr = 0.5
    try:
        max_hold = int(exit_cfg.get("max_hold_bars") or 72)
    except Exception:
        max_hold = 72

    if not isinstance(bars, list) or len(bars) < max(rsi_period + 2, 20):
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "rsi9_insufficient_bars",
            "details": f"Need closed OHLC history for RSI9; got {len(bars) if isinstance(bars, list) else 0}.",
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    _o, h, l, c = _bars_to_arrays(bars)
    if len(c) < rsi_period + 2:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "rsi9_insufficient_bars",
            "details": "Parsed bars too short for RSI9.",
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    rsi = _rsi_wilder(c, rsi_period)
    atr = _atr_wilder(h, l, c, 14)
    i = len(c) - 1  # latest closed bar
    rsi_i = float(rsi[i]) if not np.isnan(rsi[i]) else None
    atr_i = float(atr[i]) if not np.isnan(atr[i]) else None

    if rsi_i is None or atr_i is None or atr_i <= 0:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "rsi9_indicator_unavailable",
            "details": "RSI/ATR not available on latest closed bar.",
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    fired = rsi_i > thr
    if not fired:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": rid,
            "details": (
                f"RSI9 transfer SHORT: RSI({rsi_period})={rsi_i:.2f} <= {thr} on closed bar. "
                f"No entry. ATR14={atr_i:.6g}."
            ),
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "rulebook_id": rid,
            "production_authorized": bool(rb.get("production_authorized")),
            "indicators": {"rsi9": rsi_i, "atr14": atr_i},
            "exit_params": {
                "stop_atr": stop_atr,
                "trail_atr": trail_atr,
                "max_hold_bars": max_hold,
                "break_even_at_r": 1.0,
                "direction": "SHORT",
            },
        }

    # Binary research rule: full confidence when condition met
    return {
        "signal": "SELL",
        "confidence": 1.0,
        "rule_name": rid,
        "details": (
            f"RSI9 transfer SHORT entry: RSI({rsi_period})={rsi_i:.2f} > {thr}. "
            f"Stop {stop_atr}*ATR14, BE +1R, trail {trail_atr}*ATR, max hold {max_hold}. "
            f"Executor enters next bar / current market per EA."
        ),
        "methodology": "rsi9_transfer",
        "strategy_id": "rsi9_transfer",
        "rulebook_id": rid,
        "production_authorized": bool(rb.get("production_authorized")),
        "indicators": {"rsi9": rsi_i, "atr14": atr_i},
        "exit_params": {
            "stop_atr": stop_atr,
            "trail_atr": trail_atr,
            "max_hold_bars": max_hold,
            "break_even_at_r": 1.0,
            "direction": "SHORT",
        },
        "side": "SELL",
    }
