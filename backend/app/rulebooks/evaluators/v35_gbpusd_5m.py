from __future__ import annotations
import numpy as np
import pandas as pd
from .common import ReplayResult, trade_metrics, wilder_atr14, simulate_short

RULEBOOK_ID = "AEGIS-RB-V35-GBPUSD-5M"


def evaluate(df):
    h = df["BidHigh"].to_numpy(float); l = df["BidLow"].to_numpy(float); c = df["BidClose"].to_numpy(float)
    atr = wilder_atr14(h, l, c)
    n = len(df); L = 12
    compression = pd.Series((h-l) / atr).shift(1).rolling(L).mean().to_numpy()
    trend = c - np.r_[np.full(48, np.nan), c[:-48]]
    events = []; last = -10**9
    for i in range(L + 1, n - 1):
        if not np.isfinite(atr[i]) or not np.isfinite(compression[i]) or not np.isfinite(trend[i]):
            continue
        expansion = (h[i] - l[i]) / atr[i]
        net24 = c[i] - c[i-24] if i >= 24 else np.nan
        if compression[i] < 1.0 and expansion >= 1.5 and net24 < 0 and trend[i] < 0 and i-last >= 12:
            events.append(i); last = i
    signal_arr = np.asarray(events, dtype=int)
    trades = simulate_short(df, atr, signal_arr)
    return ReplayResult(signal_arr, trades, trade_metrics(trades))
