"""Provisional indicator chain for Visual Swing-Trend V1.0 — research only.
OBB input default O1 = RSI9 (operator decision D1 open).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def bollinger(close: pd.Series, n: int, k: float, ddof: int = 0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=ddof)
    return mid + k * sd, mid, mid - k * sd


def rsi(close: pd.Series, n: int = 9) -> pd.Series:
    """Research RSI. Uses Wilder RMA; pure monotonic series may yield 100/0."""
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    au = up.copy(); ad = dn.copy()
    au.iloc[:n] = np.nan; ad.iloc[:n] = np.nan
    if len(up) >= n:
        au.iloc[n-1] = up.iloc[1:n].mean()
        ad.iloc[n-1] = dn.iloc[1:n].mean()
        for i in range(n, len(up)):
            au.iloc[i] = (au.iloc[i-1] * (n-1) + up.iloc[i]) / n
            ad.iloc[i] = (ad.iloc[i-1] * (n-1) + dn.iloc[i]) / n
    rs = au / ad.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # if ad==0 and au>0 -> 100
    out = out.where(~((ad == 0) & (au > 0)), 100.0)
    out = out.where(~((au == 0) & (ad > 0)), 0.0)
    return out


def atr_wilder(high, low, close, n=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.copy()
    atr[:] = np.nan
    if len(tr) >= n:
        atr.iloc[n - 1] = tr.iloc[:n].mean()
        for i in range(n, len(tr)):
            atr.iloc[i] = (atr.iloc[i - 1] * (n - 1) + tr.iloc[i]) / n
    return atr


def compute_all(df: pd.DataFrame, obb_on: str = "rsi") -> pd.DataFrame:
    """obb_on: 'rsi' (O1) or 'ma7' (O2)."""
    c = df["close"]
    h = df["high"]
    l = df["low"]
    out = df.copy()
    out["BB17_U"], out["BB17_M"], out["BB17_L"] = bollinger(c, 17, 1.0)
    out["BB34_U"], out["BB34_M"], out["BB34_L"] = bollinger(c, 34, 1.0)
    out["RSI9"] = rsi(c, 9)
    out["MA7"] = out["RSI9"].rolling(7).mean()
    base = out["RSI9"] if obb_on == "rsi" else out["MA7"]
    out["OBB_U"], out["OBB_M"], out["OBB_L"] = bollinger(base, 34, 1.618)
    out["ATR14"] = atr_wilder(h, l, c, 14)
    # band relations
    out["bb17u_inside"] = (out["BB34_L"] < out["BB17_U"]) & (out["BB17_U"] < out["BB34_U"])
    out["bb17u_outside_above"] = out["BB17_U"] > out["BB34_U"]
    out["bb34u_exposed"] = out["BB34_U"] > out["BB17_U"]
    out["bb17l_outside_below"] = out["BB17_L"] < out["BB34_L"]
    out["bb34l_exposed"] = out["BB34_L"] < out["BB17_L"]
    return out


def confirm_swings(high: pd.Series, low: pd.Series):
    """Causal 2-bar confirmation. Returns series of confirmed swing high/low prices (ffill)."""
    n = len(high)
    sh = np.full(n, np.nan)
    sl = np.full(n, np.nan)
    for p in range(2, n - 2):
        if high.iloc[p] > high.iloc[p - 1] and high.iloc[p] > high.iloc[p - 2] and high.iloc[p] >= high.iloc[p + 1] and high.iloc[p] >= high.iloc[p + 2]:
            sh[p + 2] = float(high.iloc[p])
        if low.iloc[p] < low.iloc[p - 1] and low.iloc[p] < low.iloc[p - 2] and low.iloc[p] <= low.iloc[p + 1] and low.iloc[p] <= low.iloc[p + 2]:
            sl[p + 2] = float(low.iloc[p])
    return pd.Series(sh).ffill(), pd.Series(sl).ffill()
