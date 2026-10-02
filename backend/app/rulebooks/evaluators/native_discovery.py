"""
Native discovery live evaluator (pair-specific LONG/SHORT research rules).

Loads registry/v40/rulebooks_native/{INSTRUMENT}.json and evaluates the
entry.name family on closed OHLC bars.

Supported entry names (from 2026-10-01 native discovery):
  - long_ema_pullback
  - long_rsi9_lt30 / long_rsi9_lt25 / long_rsi9_lt20
  - long_z60_lt-1.5 / long_z60_lt-2.0 / long_z60_lt-2.5
  - long_bb20_lower / short_bb20_upper
  - long_failed_breakout20 / short_failed_breakout20
  - short_rsi9_gt70 / short_rsi9_gt75 (if present)

Separate strategy_id: native_discovery — must not override V53.6 or RSI9 transfer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app.rulebooks.evaluators.rsi9_short_transfer import _atr_wilder, _bars_to_arrays, _rsi_wilder


def load_native_rulebook(instrument: str, repo_root: Path | None = None) -> dict[str, Any] | None:
    root = repo_root or Path(__file__).resolve().parents[4]
    path = root / "registry" / "v40" / "rulebooks_native" / f"{instrument.upper()}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not data.get("qualified_with_test") and data.get("status") not in (
        "RESEARCH_QUALIFIED_NOT_PRODUCTION",
        "QUALIFIED_RESEARCH_CANDIDATE",
    ):
        if data.get("status") == "DISCOVERY_NO_QUALIFIED":
            return None
    return data


def _ema(x: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def _sma(x: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(x, np.nan)
    if len(x) < period:
        return out
    c = np.cumsum(x)
    out[period - 1 :] = (c[period - 1 :] - np.concatenate([[0.0], c[:-period]])) / period
    return out


def evaluate_native_from_bars(
    bars: list[dict[str, Any]],
    *,
    instrument: str,
    rulebook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rb = rulebook or load_native_rulebook(instrument)
    rid = (rb or {}).get("rulebook_id") or f"AEGIS-RB-NATIVE-{instrument.upper()}"
    if rb is None:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "native_rulebook_missing",
            "details": f"No native discovery rulebook for {instrument}.",
            "methodology": "native_discovery",
            "strategy_id": "native_discovery",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    entry = rb.get("entry") or {}
    name = str(entry.get("name") or "")
    side = str(entry.get("side") or "long").lower()
    exit_cfg = rb.get("exit") or {}
    stop_atr = float(exit_cfg.get("initial_stop_atr") or 1.0)
    trail_atr = float(exit_cfg.get("trailing_stop_atr") or 0.5)
    max_hold = int(exit_cfg.get("max_hold_bars") or 72)

    if not isinstance(bars, list) or len(bars) < 60:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "native_insufficient_bars",
            "details": f"Need >=60 closed bars for native rule {name}; got {len(bars) if isinstance(bars, list) else 0}.",
            "methodology": "native_discovery",
            "strategy_id": "native_discovery",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    _o, h, l, c = _bars_to_arrays(bars)
    if len(c) < 60:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "native_insufficient_bars",
            "details": "Parsed bars too short.",
            "methodology": "native_discovery",
            "strategy_id": "native_discovery",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    i = len(c) - 1
    atr = _atr_wilder(h, l, c, 14)
    atr_i = float(atr[i]) if not np.isnan(atr[i]) else None
    fired = False
    detail = name

    if name.startswith("long_rsi9_lt") or name.startswith("short_rsi9_gt"):
        rsi = _rsi_wilder(c, 9)
        rsi_i = float(rsi[i]) if not np.isnan(rsi[i]) else None
        if rsi_i is None:
            fired = False
        elif "lt30" in name:
            fired = rsi_i < 30
            detail = f"RSI9={rsi_i:.2f}<30"
        elif "lt25" in name:
            fired = rsi_i < 25
            detail = f"RSI9={rsi_i:.2f}<25"
        elif "lt20" in name:
            fired = rsi_i < 20
            detail = f"RSI9={rsi_i:.2f}<20"
        elif "gt70" in name:
            fired = rsi_i > 70
            detail = f"RSI9={rsi_i:.2f}>70"
        elif "gt75" in name:
            fired = rsi_i > 75
            detail = f"RSI9={rsi_i:.2f}>75"
        else:
            fired = False
    elif name == "long_ema_pullback":
        e20 = _ema(c, 20)
        e50 = _ema(c, 50)
        prev = c[i - 1]
        fired = bool(e20[i] > e50[i] and prev > e20[i - 1] and c[i] <= e20[i])
        detail = f"EMA pullback long e20={e20[i]:.5g} e50={e50[i]:.5g}"
    elif name == "short_ema_pullback":
        e20 = _ema(c, 20)
        e50 = _ema(c, 50)
        prev = c[i - 1]
        fired = bool(e20[i] < e50[i] and prev < e20[i - 1] and c[i] >= e20[i])
        detail = f"EMA pullback short e20={e20[i]:.5g} e50={e50[i]:.5g}"
    elif "z60_lt" in name or "z60_gt" in name:
        mu = _sma(c, 60)
        # rolling std
        std = np.full_like(c, np.nan)
        for j in range(59, len(c)):
            std[j] = np.std(c[j - 59 : j + 1], ddof=0)
        z = (c[i] - mu[i]) / std[i] if std[i] and std[i] > 1e-12 else np.nan
        if np.isnan(z):
            fired = False
        elif "lt-1.5" in name or "lt_-1.5" in name or "lt-1.5" in name.replace("_", ""):
            fired = z < -1.5
            detail = f"z60={z:.3f}<-1.5"
        elif "lt-2.0" in name or "lt-2" in name:
            fired = z < -2.0
            detail = f"z60={z:.3f}<-2.0"
        elif "gt1.5" in name or "gt_1.5" in name:
            fired = z > 1.5
            detail = f"z60={z:.3f}>1.5"
        else:
            # parse number after lt-
            fired = False
            detail = f"z60={z:.3f}"
    elif name == "long_bb20_lower":
        mid = _sma(c, 20)
        std = np.full_like(c, np.nan)
        for j in range(19, len(c)):
            std[j] = np.std(c[j - 19 : j + 1], ddof=0)
        bb_l = mid[i] - 2 * std[i] if not np.isnan(mid[i]) and not np.isnan(std[i]) else np.nan
        fired = bool(not np.isnan(bb_l) and c[i] < bb_l)
        detail = f"close={c[i]:.5g} bb_lower={bb_l:.5g}"
    elif name == "short_bb20_upper":
        mid = _sma(c, 20)
        std = np.full_like(c, np.nan)
        for j in range(19, len(c)):
            std[j] = np.std(c[j - 19 : j + 1], ddof=0)
        bb_u = mid[i] + 2 * std[i] if not np.isnan(mid[i]) and not np.isnan(std[i]) else np.nan
        fired = bool(not np.isnan(bb_u) and c[i] > bb_u)
        detail = f"close={c[i]:.5g} bb_upper={bb_u:.5g}"
    elif "failed_breakout20" in name:
        # Donchian 20 prior high/low
        if i < 21:
            fired = False
        else:
            prev_dh = float(np.max(h[i - 20 : i]))
            prev_dl = float(np.min(l[i - 20 : i]))
            if "long" in name:
                fired = bool(l[i] < prev_dl and c[i] > prev_dl)
                detail = f"failed breakdown recover close={c[i]:.5g} dl={prev_dl:.5g}"
            else:
                fired = bool(h[i] > prev_dh and c[i] < prev_dh)
                detail = f"failed breakout fade close={c[i]:.5g} dh={prev_dh:.5g}"
    else:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": "native_entry_unsupported",
            "details": f"Entry name '{name}' not implemented in native live evaluator.",
            "methodology": "native_discovery",
            "strategy_id": "native_discovery",
            "rulebook_id": rid,
            "production_authorized": False,
        }

    direction = "LONG" if side == "long" else "SHORT"
    signal = "BUY" if side == "long" else "SELL"
    base = {
        "methodology": "native_discovery",
        "strategy_id": "native_discovery",
        "rulebook_id": rid,
        "production_authorized": bool(rb.get("production_authorized")),
        "exit_params": {
            "stop_atr": stop_atr,
            "trail_atr": trail_atr,
            "max_hold_bars": max_hold,
            "break_even_at_r": 1.0,
            "direction": direction,
        },
        "indicators": {"atr14": atr_i},
    }
    if not fired:
        return {
            **base,
            "signal": "HOLD",
            "confidence": 0.0,
            "rule_name": rid,
            "details": f"Native {name}: no entry on closed bar ({detail}).",
        }
    return {
        **base,
        "signal": signal,
        "confidence": 1.0,
        "rule_name": rid,
        "details": f"Native discovery {direction} entry ({name}): {detail}. Stop {stop_atr}*ATR.",
        "side": signal,
    }
