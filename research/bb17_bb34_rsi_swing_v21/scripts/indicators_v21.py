"""Frozen v2.1 indicator stack — ddof=0; RBB on SMA7(RSI9)."""
from __future__ import annotations
import numpy as np

def sma(x: np.ndarray, period: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    valid = ~np.isnan(x)
    xv = np.where(valid, x, 0.0)
    cs = np.cumsum(xv)
    cc = np.cumsum(valid.astype(int))
    for i in range(period - 1, n):
        j = i - period
        cnt = cc[i] - (cc[j] if j >= 0 else 0)
        if cnt == period:
            s = cs[i] - (cs[j] if j >= 0 else 0)
            out[i] = s / period
    return out

def stdev_pop(x: np.ndarray, period: int) -> np.ndarray:
    """Population standard deviation (ddof=0) — frozen v2.1."""
    n = len(x)
    out = np.full(n, np.nan)
    valid = ~np.isnan(x)
    xv = np.where(valid, x, 0.0)
    x2v = np.where(valid, x * x, 0.0)
    cs = np.cumsum(xv)
    cs2 = np.cumsum(x2v)
    cc = np.cumsum(valid.astype(int))
    for i in range(period - 1, n):
        j = i - period
        cnt = cc[i] - (cc[j] if j >= 0 else 0)
        if cnt == period:
            s = cs[i] - (cs[j] if j >= 0 else 0)
            s2 = cs2[i] - (cs2[j] if j >= 0 else 0)
            mean = s / period
            var = s2 / period - mean * mean  # population
            out[i] = np.sqrt(max(var, 0.0))
    return out

def bollinger(series: np.ndarray, period: int, dev: float):
    mid = sma(series, period)
    sd = stdev_pop(series, period)
    return mid + dev * sd, mid, mid - dev * sd

def rsi_wilder(close: np.ndarray, period: int = 9) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    delta = np.diff(close, prepend=np.nan)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # Wilder seed: simple mean of first `period` changes (bars 1..period)
    avg_g = np.nanmean(gain[1:period + 1])
    avg_l = np.nanmean(loss[1:period + 1])
    if avg_l == 0:
        out[period] = 100.0
    else:
        out[period] = 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    for i in range(period + 1, n):
        avg_g = (avg_g * (period - 1) + (gain[i] if not np.isnan(gain[i]) else 0.0)) / period
        avg_l = (avg_l * (period - 1) + (loss[i] if not np.isnan(loss[i]) else 0.0)) / period
        if avg_l == 0:
            out[i] = 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out

def williams_r(high, low, close, period=60):
    try:
        import pandas as pd
        hh = pd.Series(high).rolling(period).max().to_numpy()
        ll = pd.Series(low).rolling(period).min().to_numpy()
        out = np.where(hh == ll, -50.0, -100.0 * (hh - close) / (hh - ll))
        out[:period - 1] = np.nan
        return out
    except Exception:
        n = len(close)
        out = np.full(n, np.nan)
        for i in range(period - 1, n):
            hh = high[i - period + 1:i + 1].max()
            ll = low[i - period + 1:i + 1].min()
            out[i] = -50.0 if hh == ll else -100.0 * (hh - close[i]) / (hh - ll)
        return out

def compute_stack_v21(close, high, low):
    """
    Dependency chain (frozen):
      Close → BB34, BB17
      Close → RSI9 → SMA7 → BB34(1.618) on SMA7
      OHLC → WPR60
    """
    b34_u, b34_m, b34_l = bollinger(close, 34, 1.0)
    b17_u, b17_m, b17_l = bollinger(close, 17, 1.0)
    rsi9 = rsi_wilder(close, 9)
    rsi_ma7 = sma(rsi9, 7)
    # CRITICAL v2.1: bands on SMA7 of RSI, not RSI itself
    rbb_u, rbb_m, rbb_l = bollinger(rsi_ma7, 34, 1.618)
    wpr60 = williams_r(high, low, close, 60)
    wpr_chg = np.full(len(close), np.nan)
    wpr_chg[1:] = wpr60[1:] - wpr60[:-1]
    return dict(
        B34_U=b34_u, B34_M=b34_m, B34_L=b34_l,
        B17_U=b17_u, B17_M=b17_m, B17_L=b17_l,
        RSI9=rsi9, RSI_MA7=rsi_ma7,
        RBB_U=rbb_u, RBB_M=rbb_m, RBB_L=rbb_l,
        WPR60=wpr60, WPR_CHG=wpr_chg,
        ddof=0, rbb_source="SMA7_of_RSI9",
    )
