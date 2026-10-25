"""Preregistered Stage 3 signal adapters — causal completed-bar signals."""
from __future__ import annotations
import numpy as np
import pandas as pd


def signal_inside_break(df: pd.DataFrame) -> pd.Series:
    """Inside bar then break beyond parent extremes. Uses bid OHLC for structure."""
    h = df["bid_high"].values
    l = df["bid_low"].values
    c = df["bid_close"].values
    n = len(df)
    s = np.zeros(n)
    for t in range(2, n):
        # t-1 inside t-2
        if h[t - 1] <= h[t - 2] and l[t - 1] >= l[t - 2]:
            if c[t] > h[t - 2]:
                s[t] = 1
            elif c[t] < l[t - 2]:
                s[t] = -1
    return pd.Series(s)


def signal_range20_break(df: pd.DataFrame) -> pd.Series:
    h = df["bid_high"]
    l = df["bid_low"]
    c = df["bid_close"]
    prior_high = h.shift(1).rolling(20).max()
    prior_low = l.shift(1).rolling(20).min()
    s = pd.Series(0.0, index=df.index)
    s = s.mask(c > prior_high, 1.0)
    s = s.mask(c < prior_low, -1.0)
    s = s.fillna(0.0)
    # if both (shouldn't), zero
    both = (c > prior_high) & (c < prior_low)
    s = s.mask(both, 0.0)
    return s
