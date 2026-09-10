from __future__ import annotations
import numpy as np
from .common import ReplayResult, load_v37_dataset, trade_metrics, wilder_atr14, simulate_short

RULEBOOK_ID = "AEGIS-RB-V31-GBPUSD-5M"


def evaluate(df):
    h = df["BidHigh"].to_numpy(float); l = df["BidLow"].to_numpy(float); c = df["BidClose"].to_numpy(float)
    atr = wilder_atr14(h, l, c)
    n = len(df); L = 12
    signals = []; last_down = -10**9
    for i in range(L + 1, n):
        window_h = h[i-L:i]; window_l = l[i-L:i]
        sh = np.max(window_h); sl = np.min(window_l)
        if not np.isfinite(atr[i]) or sh <= sl:
            continue
        if c[i] >= sl:
            continue
        if i - last_down < 12:
            continue
        # Frozen implementation advances the qualifying-down-break throttle
        # before the later exhaustion/compression state filters.
        last_down = i
        consumed = (c[i-L] - c[i-1]) / (sh - sl)
        if not (consumed < 0.5):
            continue
        prev_ranges = h[i-L:i] - l[i-L:i]
        prev_atr = atr[i-L:i]
        if not np.all(np.isfinite(prev_atr)):
            continue
        if float(np.mean(prev_ranges / prev_atr)) >= 1.0:
            continue
        signals.append(i)
    signal_arr = np.asarray(signals, dtype=int)
    trades = simulate_short(df, atr, signal_arr)
    return ReplayResult(signal_arr, trades, trade_metrics(trades))
