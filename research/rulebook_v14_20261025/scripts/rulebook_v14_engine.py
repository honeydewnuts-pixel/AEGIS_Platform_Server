"""Rulebook V1.4 causal engine — research only.

BB17/BB34 band transition + swing reversal on M15.
production_authorized=false; execution_authorized=false
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Any


def load_bid_ask(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {str(c).lower().strip(): c for c in df.columns}
    def col(*ns):
        for n in ns:
            if n in cols:
                return cols[n]
        return None
    t = col("time", "timestamp", "date")
    bo, bh, bl, bc = col("bid_open", "bidopen"), col("bid_high", "bidhigh"), col("bid_low", "bidlow"), col("bid_close", "bidclose")
    ao, ah, al, ac = col("ask_open", "askopen"), col("ask_high", "askhigh"), col("ask_low", "asklow"), col("ask_close", "askclose")
    if not all([t, bo, bh, bl, bc, ao, ah, al, ac]):
        raise ValueError("INSUFFICIENT_DATA: need paired Bid/Ask OHLC + time")
    out = pd.DataFrame({
        "time": pd.to_datetime(df[t], utc=True, errors="coerce"),
        "bid_open": pd.to_numeric(df[bo], errors="coerce"),
        "bid_high": pd.to_numeric(df[bh], errors="coerce"),
        "bid_low": pd.to_numeric(df[bl], errors="coerce"),
        "bid_close": pd.to_numeric(df[bc], errors="coerce"),
        "ask_open": pd.to_numeric(df[ao], errors="coerce"),
        "ask_high": pd.to_numeric(df[ah], errors="coerce"),
        "ask_low": pd.to_numeric(df[al], errors="coerce"),
        "ask_close": pd.to_numeric(df[ac], errors="coerce"),
    }).dropna().sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return out


def resample_m15(df: pd.DataFrame) -> pd.DataFrame:
    z = df.set_index("time")
    agg = {
        "bid_open": "first", "bid_high": "max", "bid_low": "min", "bid_close": "last",
        "ask_open": "first", "ask_high": "max", "ask_low": "min", "ask_close": "last",
    }
    return z.resample("15min").agg(agg).dropna().reset_index()


def bollinger(close: pd.Series, n: int, k: float = 1.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)  # population — frozen
    return mid + k * sd, mid, mid - k * sd


def atr_wilder(high, low, close, n=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    # Wilder: first SMA then RMA
    atr = tr.copy()
    atr.iloc[:n] = np.nan
    if len(tr) >= n:
        atr.iloc[n - 1] = tr.iloc[:n].mean()
        for i in range(n, len(tr)):
            atr.iloc[i] = (atr.iloc[i - 1] * (n - 1) + tr.iloc[i]) / n
    return atr


@dataclass
class Config:
    tick_size: float = 0.00001  # FX default; JPY 0.001 override by caller
    risk_frac: float = 0.005
    start_equity: float = 10000.0
    stop_atr_mult: float = 2.0
    trail_atr_mult: float = 2.5
    trail_activate_r: float = 1.0
    max_hold_hours: float = 48.0


def compute_signals(d: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Return dataframe with signal columns; signal at t means entry at t+1."""
    c = d["bid_close"]
    h = d["bid_high"]
    l = d["bid_low"]
    u17, m17, l17 = bollinger(c, 17, 1.0)
    u34, m34, l34 = bollinger(c, 34, 1.0)
    atr = atr_wilder(h, l, c, 14)
    eps = np.maximum(0.1 * atr, 2 * cfg.tick_size)

    n = len(d)
    # Swing highs/lows confirmed at p+2
    swing_high = np.full(n, np.nan)
    swing_low = np.full(n, np.nan)
    swing_high_conf_i = np.full(n, -1, dtype=int)
    swing_low_conf_i = np.full(n, -1, dtype=int)
    last_sh = np.nan
    last_sl = np.nan
    for p in range(2, n - 2):
        if h.iloc[p] > h.iloc[p - 1] and h.iloc[p] > h.iloc[p - 2] and h.iloc[p] >= h.iloc[p + 1] and h.iloc[p] >= h.iloc[p + 2]:
            conf = p + 2
            last_sh = float(h.iloc[p])
            swing_high[conf] = last_sh
            swing_high_conf_i[conf] = conf
        if l.iloc[p] < l.iloc[p - 1] and l.iloc[p] < l.iloc[p - 2] and l.iloc[p] <= l.iloc[p + 1] and l.iloc[p] <= l.iloc[p + 2]:
            conf = p + 2
            last_sl = float(l.iloc[p])
            swing_low[conf] = last_sl
            swing_low_conf_i[conf] = conf
    # forward-fill last confirmed swings
    sh_series = pd.Series(swing_high).ffill()
    sl_series = pd.Series(swing_low).ffill()

    # BB34 progression flags
    up_prog = (u34 - u34.shift(6) > eps) & (l34 - l34.shift(6) > eps)
    dn_prog = (u34 - u34.shift(6) < -eps) & (l34 - l34.shift(6) < -eps)
    flat = (u34 - u34.shift(3).abs() <= eps) & ((l34 - l34.shift(3)).abs() <= eps)
    # fix flat formula
    flat = ((u34 - u34.shift(3)).abs() <= eps) & ((l34 - l34.shift(3)).abs() <= eps)
    turn_dn = (u34 - u34.shift(3) < -eps) & (l34 - l34.shift(3) < -eps)
    turn_up = (u34 - u34.shift(3) > eps) & (l34 - l34.shift(3) > eps)

    # State machine for setups
    sig = np.zeros(n, dtype=int)
    # Track whether prior progression was seen recently
    had_up = False
    had_dn = False
    inside_u_count = 0  # U17 inside for SELL path
    outside_l_count = 0
    inside_l_count = 0  # L17 inside for BUY path
    outside_u_count = 0

    for t in range(40, n):
        e = float(eps.iloc[t]) if not np.isnan(eps.iloc[t]) else np.nan
        if np.isnan(e) or np.isnan(u17.iloc[t]) or np.isnan(u34.iloc[t]):
            continue
        if bool(up_prog.iloc[t]):
            had_up = True
            had_dn = False  # renewed opposite invalidates opposite pending — simplified
            inside_l_count = outside_u_count = 0  # invalidate BUY path
        if bool(dn_prog.iloc[t]):
            had_dn = True
            had_up = False
            inside_u_count = outside_l_count = 0  # invalidate SELL path

        # SELL path: prior up, then flat/turn_dn, U17 inside 2, L17 outside 2, C < swing high
        if had_up and (bool(flat.iloc[t]) or bool(turn_dn.iloc[t])):
            u17_in = float(l34.iloc[t]) < float(u17.iloc[t]) < float(u34.iloc[t])
            if u17_in:
                inside_u_count += 1
            else:
                inside_u_count = 0
            l17_out = float(l17.iloc[t]) < float(l34.iloc[t])
            if inside_u_count >= 2 and l17_out:
                outside_l_count += 1
            else:
                if not l17_out:
                    outside_l_count = 0
            sh = sh_series.iloc[t]
            if inside_u_count >= 2 and outside_l_count >= 2 and not np.isnan(sh) and float(c.iloc[t]) < sh:
                sig[t] = -1
                # reset after signal
                had_up = False
                inside_u_count = outside_l_count = 0

        # BUY path
        if had_dn and (bool(flat.iloc[t]) or bool(turn_up.iloc[t])):
            l17_in = float(l34.iloc[t]) < float(l17.iloc[t]) < float(u34.iloc[t])
            if l17_in:
                inside_l_count += 1
            else:
                inside_l_count = 0
            u17_out = float(u17.iloc[t]) > float(u34.iloc[t])
            if inside_l_count >= 2 and u17_out:
                outside_u_count += 1
            else:
                if not u17_out:
                    outside_u_count = 0
            slv = sl_series.iloc[t]
            if inside_l_count >= 2 and outside_u_count >= 2 and not np.isnan(slv) and float(c.iloc[t]) > slv:
                sig[t] = 1
                had_dn = False
                inside_l_count = outside_u_count = 0

    out = d.copy()
    out["signal"] = sig
    out["atr"] = atr
    out["eps"] = eps
    return out


def simulate(d: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, dict]:
    """Causal simulation: signal at t → entry at t+1 open."""
    n = len(d)
    cash = cfg.start_equity
    equity_mtm = []
    trades = []
    pos = 0
    direction = entry = entry_i = units = sl = atr_sig = highest = lowest = 0.0

    for t in range(1, n):
        # manage open
        if pos != 0:
            hours = (d["time"].iloc[t] - d["time"].iloc[entry_i]).total_seconds() / 3600.0
            atr_c = float(d["atr"].iloc[t - 1]) if not np.isnan(d["atr"].iloc[t - 1]) else atr_sig
            if direction == 1:
                highest = max(highest, float(d["bid_high"].iloc[t - 1]))
                if highest - entry >= cfg.trail_activate_r * (cfg.stop_atr_mult * atr_sig):
                    cand = highest - cfg.trail_atr_mult * atr_c
                    sl = max(sl, cand)
                # exits
                open_bid = float(d["bid_open"].iloc[t])
                hit = False
                xp = reason = None
                if open_bid <= sl:
                    xp, reason, hit = open_bid, "gap_stop", True
                elif float(d["bid_low"].iloc[t]) <= sl:
                    xp, reason, hit = sl, "stop", True
                if hours >= cfg.max_hold_hours and not hit:
                    xp, reason, hit = open_bid, "time", True
                if hit:
                    pnl = (xp - entry) * units
                    cash += pnl
                    trades.append(dict(dir="BUY", entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                                       entry=entry, exit=xp, pnl=pnl, reason=reason, units=units))
                    pos = 0
            else:
                lowest = min(lowest, float(d["bid_low"].iloc[t - 1]))
                if entry - lowest >= cfg.trail_activate_r * (cfg.stop_atr_mult * atr_sig):
                    cand = lowest + cfg.trail_atr_mult * atr_c
                    sl = min(sl, cand)
                open_ask = float(d["ask_open"].iloc[t])
                hit = False
                xp = reason = None
                if open_ask >= sl:
                    xp, reason, hit = open_ask, "gap_stop", True
                elif float(d["ask_high"].iloc[t]) >= sl:
                    xp, reason, hit = sl, "stop", True
                if hours >= cfg.max_hold_hours and not hit:
                    xp, reason, hit = open_ask, "time", True
                if hit:
                    pnl = (entry - xp) * units
                    cash += pnl
                    trades.append(dict(dir="SELL", entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                                       entry=entry, exit=xp, pnl=pnl, reason=reason, units=units))
                    pos = 0

            # opposite transition exit
            if pos != 0:
                sig = int(d["signal"].iloc[t - 1])
                if direction == 1 and sig == -1:
                    xp = float(d["bid_open"].iloc[t])
                    pnl = (xp - entry) * units
                    cash += pnl
                    trades.append(dict(dir="BUY", entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                                       entry=entry, exit=xp, pnl=pnl, reason="opposite", units=units))
                    pos = 0
                elif direction == -1 and sig == 1:
                    xp = float(d["ask_open"].iloc[t])
                    pnl = (entry - xp) * units
                    cash += pnl
                    trades.append(dict(dir="SELL", entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                                       entry=entry, exit=xp, pnl=pnl, reason="opposite", units=units))
                    pos = 0

        # entry from prior signal
        if pos == 0:
            sig = int(d["signal"].iloc[t - 1])
            atr_s = float(d["atr"].iloc[t - 1]) if not np.isnan(d["atr"].iloc[t - 1]) else None
            if sig == 1 and atr_s and atr_s > 0:
                entry = float(d["ask_open"].iloc[t])
                entry_i = t
                direction = 1
                pos = 1
                atr_sig = atr_s
                sl = entry - cfg.stop_atr_mult * atr_sig
                stop_dist = entry - sl
                risk_budget = cash * cfg.risk_frac
                units = risk_budget / max(stop_dist, 1e-12)
                highest = float(d["bid_high"].iloc[t])
            elif sig == -1 and atr_s and atr_s > 0:
                entry = float(d["bid_open"].iloc[t])
                entry_i = t
                direction = -1
                pos = -1
                atr_sig = atr_s
                sl = entry + cfg.stop_atr_mult * atr_sig
                stop_dist = sl - entry
                risk_budget = cash * cfg.risk_frac
                units = risk_budget / max(stop_dist, 1e-12)
                lowest = float(d["bid_low"].iloc[t])

        mtm = cash
        if pos == 1:
            mtm += (float(d["bid_close"].iloc[t]) - entry) * units
        elif pos == -1:
            mtm += (entry - float(d["ask_close"].iloc[t])) * units
        equity_mtm.append((d["time"].iloc[t], cash, mtm))

    if pos != 0:
        t = n - 1
        if direction == 1:
            xp = float(d["bid_open"].iloc[t])
            pnl = (xp - entry) * units
        else:
            xp = float(d["ask_open"].iloc[t])
            pnl = (entry - xp) * units
        cash += pnl
        trades.append(dict(dir="BUY" if direction == 1 else "SELL",
                           entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                           entry=entry, exit=xp, pnl=pnl, reason="eod", units=units))

    td = pd.DataFrame(trades)
    eq = pd.DataFrame(equity_mtm, columns=["time", "cash", "mtm"])
    return td, {"final_cash": cash, "start": cfg.start_equity, "equity": eq}


def metrics(trades: pd.DataFrame) -> dict[str, Any]:
    if trades is None or len(trades) == 0:
        return dict(trades=0, pf=None, net=0.0, win_rate=None)
    pnl = trades["pnl"].astype(float)
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    pf = (gp / gl) if gl > 0 else None
    return dict(
        trades=int(len(trades)),
        pf=round(pf, 4) if pf else None,
        net=round(float(pnl.sum()), 2),
        win_rate=round(float((pnl > 0).mean()), 4),
        buy_trades=int((trades["dir"] == "BUY").sum()) if "dir" in trades.columns else None,
        sell_trades=int((trades["dir"] == "SELL").sum()) if "dir" in trades.columns else None,
    )


def walk_forward(d: pd.DataFrame, cfg: Config) -> dict:
    n = len(d)
    t1, t2 = int(n * 0.6), int(n * 0.8)
    parts = {}
    for name, a, b in (("train", 0, t1), ("val", t1, t2), ("test", t2, n)):
        sub = d.iloc[a:b].reset_index(drop=True)
        if len(sub) < 50:
            parts[name] = dict(status="INSUFFICIENT_DATA")
            continue
        # recompute signals on full then slice — avoid look-ahead across folds by computing on sub only
        sub_s = compute_signals(sub, cfg)
        tr, _ = simulate(sub_s, cfg)
        m = metrics(tr)
        m["n_bars"] = len(sub)
        parts[name] = m
    return parts
