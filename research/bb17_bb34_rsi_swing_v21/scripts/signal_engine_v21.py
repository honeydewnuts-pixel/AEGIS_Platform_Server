"""v2.1 signal engine — early RSI reversal + target state (no cash model)."""
from __future__ import annotations
import numpy as np

SWING_L, SWING_R = 2, 2  # PROVISIONAL unless full doc overrides


def context_from_bands(i, ind):
    if any(np.isnan(ind[k][i]) for k in ("B17_U", "B34_U", "B17_L", "B34_L")):
        return "NONE"
    if ind["B17_U"][i] > ind["B34_U"][i]:
        return "BULLISH"
    if ind["B17_L"][i] < ind["B34_L"][i]:
        return "BEARISH"
    return "NEUTRAL"


def find_rsi_swings(rsi, L=SWING_L, R=SWING_R):
    n = len(rsi)
    out = []
    for i in range(L, n - R):
        if np.isnan(rsi[i]):
            continue
        wl, wr = rsi[i - L:i], rsi[i + 1:i + R + 1]
        if np.any(np.isnan(wl)) or np.any(np.isnan(wr)):
            continue
        # strict: plateaus do not form swings
        if np.all(rsi[i] < wl) and np.all(rsi[i] < wr):
            out.append((i, i + R, "low"))
        elif np.all(rsi[i] > wl) and np.all(rsi[i] > wr):
            out.append((i, i + R, "high"))
    return out


def generate_events(ind, lookback=50):
    """Early reversals only using RBB on SMA7; diagnostic WPR not a gate."""
    rsi = ind["RSI9"]
    n = len(rsi)
    events = []
    for ext, conf, kind in find_rsi_swings(rsi):
        if conf >= n:
            continue
        # band values at extreme (preferred) on RBB from SMA7
        ru, rm, rl = ind["RBB_U"][ext], ind["RBB_M"][ext], ind["RBB_L"][ext]
        rsi_e = rsi[ext]
        if any(np.isnan(v) for v in (rsi_e, ru, rm, rl)):
            continue
        ctx = context_from_bands(conf, ind)
        start = max(0, ext - lookback)
        if kind == "low":
            prior = any(
                not np.isnan(rsi[j]) and not np.isnan(ind["RBB_U"][j]) and rsi[j] > ind["RBB_U"][j]
                for j in range(start, ext)
            )
            # zone: between mid and upper of RBB (on SMA7 scale — compare RSI to those levels as frozen)
            in_zone = rm < rsi_e < ru
            eligible = prior and in_zone and ctx == "BULLISH"
            reason = "ok" if eligible else (
                "no_prior_excursion" if not prior else "not_in_zone" if not in_zone else "no_bullish_context"
            )
            action = "EARLY_BEARISH_REVERSAL" if eligible else "REJECTED"
        else:
            prior = any(
                not np.isnan(rsi[j]) and not np.isnan(ind["RBB_L"][j]) and rsi[j] < ind["RBB_L"][j]
                for j in range(start, ext)
            )
            in_zone = rl < rsi_e < rm
            eligible = prior and in_zone and ctx == "BEARISH"
            reason = "ok" if eligible else (
                "no_prior_excursion" if not prior else "not_in_zone" if not in_zone else "no_bearish_context"
            )
            action = "EARLY_BULLISH_REVERSAL" if eligible else "REJECTED"
        events.append(dict(
            extreme_idx=ext, confirm_idx=conf, kind=kind,
            action=action, eligible=eligible, reason=reason,
            context=ctx, rsi_extreme=float(rsi_e),
            rbb_u=float(ru), rbb_m=float(rm), rbb_l=float(rl),
            wpr=None if np.isnan(ind["WPR60"][ext]) else float(ind["WPR60"][ext]),
            next_open_idx=conf + 1 if conf + 1 < n else None,  # execution reference
        ))
    return events


def target_state_machine(events, n_bars):
    """
    Single target direction; opposing simultaneous = HOLD (conflict).
    Context alone does not reverse. Repeated same-direction does not pyramid.
    """
    # map confirm_idx -> list of eligible actions
    by_conf = {}
    for e in events:
        if not e["eligible"]:
            continue
        by_conf.setdefault(e["confirm_idx"], []).append(e)
    target = np.array(["FLAT"] * n_bars, dtype=object)
    pos = "FLAT"
    conflict_count = 0
    changes = []
    for i in range(n_bars):
        if i in by_conf:
            acts = {e["action"] for e in by_conf[i]}
            has_bear = "EARLY_BEARISH_REVERSAL" in acts
            has_bull = "EARLY_BULLISH_REVERSAL" in acts
            if has_bear and has_bull:
                conflict_count += 1
                # hold current
            elif has_bear:
                if pos != "SHORT":
                    changes.append((i, pos, "SHORT", "EARLY_BEARISH_REVERSAL"))
                    pos = "SHORT"
            elif has_bull:
                if pos != "LONG":
                    changes.append((i, pos, "LONG", "EARLY_BULLISH_REVERSAL"))
                    pos = "LONG"
        target[i] = pos
    return target, changes, conflict_count
