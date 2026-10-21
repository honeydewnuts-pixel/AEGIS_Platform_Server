"""V7 Fixed Squeeze — research engine from frozen rule text.
Baseline parameters; Class A uses Bid/Ask; Class B OHLC proxy.
production_authorized=false. No live execution.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict

@dataclass
class V7Params:
    bb_period: int = 20
    bb_dev: float = 2.0
    squeeze_lookback: int = 10
    squeeze_pct: float = 0.40
    atr_period: int = 14
    atr_sma: int = 50
    atr_mult: float = 1.10
    breakout_lookback: int = 5
    pullback_lookback: int = 3
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    # research cost assumptions (pips/price units) — documented
    cost_pips: float = 1.5  # round-trip proxy; Class A can use spread+this
    session_start: int = 7   # UTC hour inclusive
    session_end: int = 20    # exclusive 07:00-19:59
    chandelier_mult: float = 3.0
    initial_stop_atr: float = 1.5
    candidate_id: str = "BASELINE"

def ema(x, period):
    out = np.full(len(x), np.nan)
    if len(x) < period:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = np.mean(x[:period])
    for i in range(period, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out

def sma(x, period):
    out = np.full(len(x), np.nan)
    c = np.cumsum(np.where(np.isnan(x), 0, x))
    for i in range(period - 1, len(x)):
        if i >= period - 1:
            out[i] = (c[i] - (c[i - period] if i >= period else 0)) / period
    return out

def atr_wilder(h, l, c, period=14):
    n = len(c)
    tr = np.full(n, np.nan)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    if n < period:
        return out
    out[period - 1] = np.nanmean(tr[:period])
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out

def bollinger(c, period=20, dev=2.0):
    mid = sma(c, period)
    sd = np.full(len(c), np.nan)
    for i in range(period - 1, len(c)):
        w = c[i - period + 1:i + 1]
        sd[i] = np.std(w, ddof=0)
    return mid + dev * sd, mid, mid - dev * sd

def bandwidth_pct_rank(bw, lookback):
    """Percentile rank of prior `lookback` bars excluding current."""
    n = len(bw)
    out = np.full(n, np.nan)
    for i in range(lookback, n):
        window = bw[i - lookback:i]  # excludes i
        if np.any(np.isnan(window)) or np.isnan(bw[i - 1]):
            continue
        # rank of most recent completed bar's bw among prior lookback
        ref = bw[i - 1]
        out[i] = np.mean(window <= ref)
    return out

def load_bars(path: str, data_class: str):
    df = pd.read_csv(path)
    # timestamp
    ts_col = None
    for c in df.columns:
        if "time" in c.lower() or c.lower() == "date":
            ts_col = c
            break
    if ts_col is None:
        ts_col = df.columns[0]
    df["datetime"] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    cols = {c.lower(): c for c in df.columns}
    if data_class == "A_BIDASK":
        # prefer bid for indicators; keep ask for long entry
        def col(*names):
            for n in names:
                if n in cols:
                    return df[cols[n]].astype(float).to_numpy()
            raise KeyError(names)
        bid_c = col("bid_close", "bidclose")
        bid_h = col("bid_high", "bidhigh")
        bid_l = col("bid_low", "bidlow")
        bid_o = col("bid_open", "bidopen")
        ask_o = col("ask_open", "askopen")
        ask_c = col("ask_close", "askclose")
        spread = ask_c - bid_c
        return dict(
            dt=df["datetime"], close=bid_c, high=bid_h, low=bid_l, open=bid_o,
            ask_open=ask_o, bid_open=bid_o, spread=spread, data_class=data_class,
        )
    else:
        def col(*names):
            for n in names:
                if n in cols:
                    return df[cols[n]].astype(float).to_numpy()
            raise KeyError(names)
        c = col("close")
        h = col("high")
        l = col("low")
        o = col("open")
        return dict(
            dt=df["datetime"], close=c, high=h, low=l, open=o,
            ask_open=o, bid_open=o, spread=np.zeros(len(c)), data_class=data_class,
        )

def run_v7(bars, params: V7Params, direction: str = "BOTH"):
    """direction: LONG, SHORT, or BOTH. Returns trades + funnel counts."""
    c, h, l = bars["close"], bars["high"], bars["low"]
    n = len(c)
    bu, bm, bl = bollinger(c, params.bb_period, params.bb_dev)
    bw = (bu - bl) / np.where(bm == 0, np.nan, bm)
    sq = bandwidth_pct_rank(bw, params.squeeze_lookback)
    atr = atr_wilder(h, l, c, params.atr_period)
    atr_sma = sma(atr, params.atr_sma)
    e20 = ema(c, params.ema_fast)
    e50 = ema(c, params.ema_mid)
    e200 = ema(c, params.ema_slow)
    hour = bars["dt"].dt.hour.to_numpy()

    funnel = dict(
        warmup=0, squeeze=0, vol_exp=0, breakout=0, pullback=0,
        trend=0, session=0, direction=0, position_open=0, entered=0,
    )
    trades = []
    pos = None  # dict
    i0 = max(params.ema_slow, params.atr_sma, params.bb_period, params.squeeze_lookback) + 2

    for i in range(i0, n):
        # manage open position
        if pos is not None:
            exit_px = None
            reason = None
            # initial stop / chandelier (simplified research semantics)
            if pos["side"] == "LONG":
                # stop if low <= stop
                if l[i] <= pos["stop"]:
                    exit_px = min(bars["bid_open"][i] if i > pos["entry_i"] else pos["stop"], pos["stop"])
                    # Class A long exit on bid
                    exit_px = bars["close"][i] if bars["data_class"] == "B_OHLC" else min(c[i], pos["stop"])
                    reason = "STOP"
                else:
                    # update chandelier outside? task notes session interaction — research: update always
                    trail = h[i] - params.chandelier_mult * atr[i]
                    if not np.isnan(trail):
                        pos["stop"] = max(pos["stop"], trail)
            else:  # SHORT
                if h[i] >= pos["stop"]:
                    exit_px = bars["close"][i] if bars["data_class"] == "B_OHLC" else max(c[i], pos["stop"])
                    reason = "STOP"
                else:
                    trail = l[i] + params.chandelier_mult * atr[i]
                    if not np.isnan(trail):
                        pos["stop"] = min(pos["stop"], trail)
            if exit_px is not None:
                entry = pos["entry"]
                if pos["side"] == "LONG":
                    gross = exit_px - entry
                else:
                    gross = entry - exit_px
                cost = params.cost_pips * (1e-4 if entry < 50 else 0.01 if entry < 500 else 0.1)
                # crude pip scaling by price level
                if bars["data_class"] == "A_BIDASK":
                    cost = float(np.nanmedian(bars["spread"][max(0, i - 100):i + 1])) + params.cost_pips * 1e-4
                net = gross - cost
                trades.append(dict(
                    side=pos["side"], entry_i=pos["entry_i"], exit_i=i,
                    entry=entry, exit=exit_px, gross=gross, cost=cost, net=net,
                    reason=reason, candidate=params.candidate_id,
                ))
                pos = None

        if pos is not None:
            funnel["position_open"] += 1
            continue

        # session
        if not (params.session_start <= hour[i] < params.session_end):
            funnel["session"] += 1
            continue

        # warmup NaNs
        if any(np.isnan(x) for x in (sq[i], atr[i], atr_sma[i], e20[i], e50[i], e200[i], bu[i])):
            funnel["warmup"] += 1
            continue

        # squeeze: prior percentile < threshold
        if not (sq[i] < params.squeeze_pct):
            funnel["squeeze"] += 1
            continue

        # vol expansion
        if not (atr[i] > params.atr_mult * atr_sma[i]):
            funnel["vol_exp"] += 1
            continue

        # breakout: close beyond BB in prior lookback excluding current
        broke_up = any(c[j] > bu[j] for j in range(i - params.breakout_lookback, i) if j >= 0 and not np.isnan(bu[j]))
        broke_dn = any(c[j] < bl[j] for j in range(i - params.breakout_lookback, i) if j >= 0 and not np.isnan(bl[j]))
        if not (broke_up or broke_dn):
            funnel["breakout"] += 1
            continue

        # EMA20 pullback touch in prior pullback_lookback excluding current
        touched = any(
            (l[j] <= e20[j] <= h[j]) for j in range(i - params.pullback_lookback, i)
            if j >= 0 and not np.isnan(e20[j])
        )
        if not touched:
            funnel["pullback"] += 1
            continue

        # trend
        long_ok = c[i] > e20[i] > e50[i] > e200[i]
        short_ok = c[i] < e20[i] < e50[i] < e200[i]
        if direction == "LONG":
            short_ok = False
        if direction == "SHORT":
            long_ok = False
        if not (long_ok or short_ok):
            funnel["trend"] += 1
            continue
        if long_ok and short_ok:
            funnel["direction"] += 1
            continue

        side = "LONG" if long_ok else "SHORT"
        # entry next bar open conceptually — research uses current close+next as proxy: fill at next open
        if i + 1 >= n:
            continue
        if side == "LONG":
            entry = bars["ask_open"][i + 1]
            stop = entry - params.initial_stop_atr * atr[i]
        else:
            entry = bars["bid_open"][i + 1]
            stop = entry + params.initial_stop_atr * atr[i]
        pos = dict(side=side, entry=entry, entry_i=i + 1, stop=stop)
        funnel["entered"] += 1

    # close open at end
    if pos is not None:
        i = n - 1
        exit_px = c[i]
        entry = pos["entry"]
        gross = (exit_px - entry) if pos["side"] == "LONG" else (entry - exit_px)
        cost = params.cost_pips * 1e-4
        trades.append(dict(
            side=pos["side"], entry_i=pos["entry_i"], exit_i=i,
            entry=entry, exit=exit_px, gross=gross, cost=cost, net=gross - cost,
            reason="EOD", candidate=params.candidate_id,
        ))
    return trades, funnel

def split_60_20_20(n):
    a = int(n * 0.60)
    b = int(n * 0.80)
    return (0, a), (a, b), (b, n)

def pf(nets):
    gains = sum(x for x in nets if x > 0)
    losses = -sum(x for x in nets if x < 0)
    if losses <= 0:
        return float("inf") if gains > 0 else None
    return gains / losses

def six_block_pf(trades, start_i, end_i):
    """Six equal-duration blocks by entry index within [start_i, end_i)."""
    span = end_i - start_i
    if span <= 0:
        return [None] * 6
    block = span / 6.0
    pfs = []
    for k in range(6):
        lo = start_i + int(k * block)
        hi = start_i + int((k + 1) * block)
        nets = [t["net"] for t in trades if lo <= t["entry_i"] < hi and t["exit_i"] < end_i]
        pfs.append(pf(nets) if nets else None)
    return pfs
