"""Main-chart trend state engine + PROVISIONAL RSI swing detection."""
from __future__ import annotations
import numpy as np

SWING_LEFT = 2
SWING_RIGHT = 2


def classify_band_structure(i, ind):
    b17u, b34u = ind["B17_U"][i], ind["B34_U"][i]
    b17m, b34m = ind["B17_M"][i], ind["B34_M"][i]
    b17l, b34l = ind["B17_L"][i], ind["B34_L"][i]
    if any(np.isnan(v) for v in (b17u, b34u, b17m, b34m, b17l, b34l)):
        return None
    return dict(
        up_core=b17u > b34u,
        dn_core=b17l < b34l,
        mid_ret_up=(b17l < b34m) and (b17l > b34l),
        deep_up=b17l <= b34l,
        mid_ret_dn=(b17u > b34m) and (b17u < b34u),
        deep_dn=b17u >= b34u,
    )


def evolve_states(ind):
    n = len(ind["B34_M"])
    state = np.array(["INSUFFICIENT_HISTORY"] * n, dtype=object)
    for i in range(n):
        snap = classify_band_structure(i, ind)
        if snap is None:
            continue
        if snap["up_core"]:
            if snap["deep_up"]:
                state[i] = "UPTREND_DEEP_RETRACEMENT"
            elif snap["mid_ret_up"]:
                state[i] = "UPTREND_RETRACEMENT"
            else:
                state[i] = "UPTREND_ESTABLISHED"
        elif snap["dn_core"]:
            if snap["deep_dn"]:
                state[i] = "DOWNTREND_DEEP_RETRACEMENT"
            elif snap["mid_ret_dn"]:
                state[i] = "DOWNTREND_RETRACEMENT"
            else:
                state[i] = "DOWNTREND_ESTABLISHED"
        else:
            state[i] = "NEUTRAL"
    return state


def find_rsi_swings(rsi, L=SWING_LEFT, R=SWING_RIGHT):
    n = len(rsi)
    swings = []
    for i in range(L, n - R):
        if np.isnan(rsi[i]):
            continue
        wl, wr = rsi[i - L:i], rsi[i + 1:i + R + 1]
        if np.any(np.isnan(wl)) or np.any(np.isnan(wr)):
            continue
        if np.all(rsi[i] <= wl) and np.all(rsi[i] < wr):
            swings.append((i, i + R, "low"))
        elif np.all(rsi[i] >= wl) and np.all(rsi[i] > wr):
            swings.append((i, i + R, "high"))
    return swings


def early_rsi_reversal_events(ind, states, lookback_excursion=50):
    rsi = ind["RSI9"]
    n = len(rsi)
    events = []
    for ext, conf, kind in find_rsi_swings(rsi):
        if conf >= n:
            continue
        rbb_u, rbb_m, rbb_l = ind["RBB_U"][ext], ind["RBB_M"][ext], ind["RBB_L"][ext]
        rsi_e = rsi[ext]
        if any(np.isnan(v) for v in (rsi_e, rbb_u, rbb_m, rbb_l)):
            continue
        start = max(0, ext - lookback_excursion)
        st = str(states[conf]) if conf < len(states) else "NEUTRAL"
        if kind == "low":
            prior_exc = any(
                (not np.isnan(rsi[j]) and not np.isnan(ind["RBB_U"][j]) and rsi[j] > ind["RBB_U"][j])
                for j in range(start, ext)
            )
            in_zone = rbb_m < rsi_e < rbb_u
            eligible = prior_exc and in_zone and st.startswith("UP")
            reason = "ok" if eligible else (
                "no_prior_excursion" if not prior_exc else
                "rsi_not_in_zone" if not in_zone else "not_in_uptrend"
            )
            events.append(dict(
                kind="EARLY_BEARISH_REVERSAL", extreme_idx=ext, confirm_idx=conf,
                rsi_extreme=float(rsi_e), rbb_u=float(rbb_u), rbb_m=float(rbb_m), rbb_l=float(rbb_l),
                prior_band_excursion=prior_exc, main_state=st, eligible=eligible, reason=reason,
                rsi_ma7=None if np.isnan(ind["RSI_MA7"][ext]) else float(ind["RSI_MA7"][ext]),
                wpr60=None if np.isnan(ind["WPR60"][ext]) else float(ind["WPR60"][ext]),
            ))
        else:
            prior_exc = any(
                (not np.isnan(rsi[j]) and not np.isnan(ind["RBB_L"][j]) and rsi[j] < ind["RBB_L"][j])
                for j in range(start, ext)
            )
            in_zone = rbb_l < rsi_e < rbb_m
            eligible = prior_exc and in_zone and st.startswith("DOWN")
            reason = "ok" if eligible else (
                "no_prior_excursion" if not prior_exc else
                "rsi_not_in_zone" if not in_zone else "not_in_downtrend"
            )
            events.append(dict(
                kind="EARLY_BULLISH_REVERSAL", extreme_idx=ext, confirm_idx=conf,
                rsi_extreme=float(rsi_e), rbb_u=float(rbb_u), rbb_m=float(rbb_m), rbb_l=float(rbb_l),
                prior_band_excursion=prior_exc, main_state=st, eligible=eligible, reason=reason,
                rsi_ma7=None if np.isnan(ind["RSI_MA7"][ext]) else float(ind["RSI_MA7"][ext]),
                wpr60=None if np.isnan(ind["WPR60"][ext]) else float(ind["WPR60"][ext]),
            ))
    return events
