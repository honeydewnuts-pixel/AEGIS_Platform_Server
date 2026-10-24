"""Variant B-V corrected causal engine (research-only).

Versions:
  LEGACY_LOOKAHEAD — mirrors source entry-at-signal-bar-open (not for qualification)
  CAUSAL_V1 — next-bar entry/exit; corrected downtrend; 48h wall-clock time stop
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass

COST_GBPUSD_REF = 0.00019  # SOURCE_REPORTED 1.9 pip RT label for GBPUSD

def load_ohlc(path: str, prefer_bid: bool = True) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {str(k).lower().strip(): k for k in df.columns}
    def col(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None
    t = col("time", "timestamp", "date", "datetime")
    if prefer_bid and col("bid_open", "bidopen"):
        o, h, l, c = col("bid_open", "bidopen"), col("bid_high", "bidhigh"), col("bid_low", "bidlow"), col("bid_close", "bidclose")
        ao, ah, al, ac = col("ask_open", "askopen"), col("ask_high", "askhigh"), col("ask_low", "asklow"), col("ask_close", "askclose")
    else:
        o, h, l, c = col("open"), col("high"), col("low"), col("close")
        ao = ah = al = ac = None
    out = pd.DataFrame({
        "time": pd.to_datetime(df[t], utc=True, errors="coerce"),
        "open": pd.to_numeric(df[o], errors="coerce"),
        "high": pd.to_numeric(df[h], errors="coerce"),
        "low": pd.to_numeric(df[l], errors="coerce"),
        "close": pd.to_numeric(df[c], errors="coerce"),
    })
    if ao:
        out["ask_open"] = pd.to_numeric(df[ao], errors="coerce")
        out["ask_high"] = pd.to_numeric(df[ah], errors="coerce") if ah else out["high"]
        out["ask_low"] = pd.to_numeric(df[al], errors="coerce") if al else out["low"]
        out["ask_close"] = pd.to_numeric(df[ac], errors="coerce") if ac else out["close"]
    else:
        out["ask_open"] = out["open"]
        out["ask_high"] = out["high"]
        out["ask_low"] = out["low"]
        out["ask_close"] = out["close"]
    out = out.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time")
    out = out.drop_duplicates("time").reset_index(drop=True)
    return out

def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {
        "open": "first", "high": "max", "low": "min", "close": "last",
        "ask_open": "first", "ask_high": "max", "ask_low": "min", "ask_close": "last",
    }
    z = df.set_index("time")
    r = z.resample(rule).agg(agg).dropna(subset=["open", "high", "low", "close"]).reset_index()
    return r

def rsi(close, n=9):
    diff = close.diff()
    gain = diff.clip(lower=0)
    loss = (-diff).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(avg_loss != 0, 100.0)
    out = out.where((avg_gain != 0) | (avg_loss != 0), 50.0)
    return out

def williams_r(high, low, close, n=60):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    denom = (hh - ll).replace(0, np.nan)
    return -100 * (hh - close) / denom

def atr_sma(high, low, close, n=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def bollinger(s, n, k):
    mid = s.rolling(n).mean()
    sd = s.rolling(n).std(ddof=0)
    return mid + k * sd, mid, mid - k * sd

@dataclass
class EngineConfig:
    version: str = "CAUSAL_V1"
    cost: float = COST_GBPUSD_REF
    risk: float = 0.01
    time_stop_hours: float = 48.0
    cooldown_bars: int = 30
    break_window: int = 30
    downtrend_mode: str = "CORRECTED"  # or LEGACY
    force_close_eod: bool = True
    use_bid_ask: bool = True


def run_variant_bv(d: pd.DataFrame, cfg: EngineConfig | None = None):
    cfg = cfg or EngineConfig()
    c, h, l = d["close"], d["high"], d["low"]
    rsi9 = rsi(c, 9)
    ma7 = rsi9.rolling(7).mean()
    bb_u, bb_m, bb_l = bollinger(ma7, 34, 1.618)
    wpr = williams_r(h, l, c, 60)
    atr14 = atr_sma(h, l, c, 14)
    atr_median = atr14.rolling(100).median()

    m17 = c.rolling(17).mean(); sd17 = c.rolling(17).std(ddof=0)
    m34 = c.rolling(34).mean(); sd34 = c.rolling(34).std(ddof=0)
    b17u, b17l = m17 + sd17, m17 - sd17
    b34u, b34l = m34 + sd34, m34 - sd34
    uptrend = (b17u > b34u) & (b17l > b34l)
    if cfg.downtrend_mode == "LEGACY":
        downtrend = (b17u < b34l) & (b17u < b34l)
    else:
        downtrend = (b17u < b34u) & (b17l < b34l)

    n = len(d)
    cash = 10000.0
    trades = []
    equity_cash = []
    equity_mtm = []
    up_break_i = dn_break_i = -10**9
    cooldown = -10**9
    pull_short = pull_long = False
    pos = 0
    direction = entry = entry_i = units = sl = highest = lowest = 0

    def long_entry_px(i):
        return float(d["ask_open"].iloc[i]) if cfg.use_bid_ask else float(d["open"].iloc[i])

    def short_entry_px(i):
        return float(d["open"].iloc[i])  # bid open

    def long_exit_px_open(i):
        return float(d["open"].iloc[i])  # bid

    def short_exit_px_open(i):
        return float(d["ask_open"].iloc[i]) if cfg.use_bid_ask else float(d["open"].iloc[i])

    pending_entry = None  # ('long'|'short', signal_bar_index)
    pending_exit = None

    for t in range(200, n):
        # Manage open position with bar t data (stops use intrabar high/low of t)
        if pos != 0:
            hours = (d["time"].iloc[t] - d["time"].iloc[entry_i]).total_seconds() / 3600.0
            if hours >= cfg.time_stop_hours:
                if direction == 1:
                    xp = long_exit_px_open(t)
                    pnl = (xp - entry) * units - cfg.cost * units
                else:
                    xp = short_exit_px_open(t)
                    pnl = (entry - xp) * units - cfg.cost * units
                cash += pnl
                trades.append(dict(dir="long" if direction == 1 else "short",
                                   entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                                   entry=entry, exit=xp, pnl=pnl, reason="time"))
                pos = 0; cooldown = t
            elif pos == 1:
                highest = max(highest, float(h.iloc[t - 1]) if t > entry_i else float(h.iloc[t]))
                if highest - entry >= float(atr14.iloc[t - 1]):
                    sl = max(sl, highest - 2.5 * float(atr14.iloc[t - 1]))
                if float(l.iloc[t]) <= sl:
                    pnl = (sl - entry) * units - cfg.cost * units
                    cash += pnl
                    trades.append(dict(dir="long", entry_time=d["time"].iloc[entry_i],
                                       exit_time=d["time"].iloc[t], entry=entry, exit=sl, pnl=pnl, reason="trail"))
                    pos = 0; cooldown = t
            else:
                lowest = min(lowest, float(l.iloc[t - 1]) if t > entry_i else float(l.iloc[t]))
                if entry - lowest >= float(atr14.iloc[t - 1]):
                    sl = min(sl, lowest + 2.5 * float(atr14.iloc[t - 1]))
                if float(h.iloc[t]) >= sl:
                    pnl = (entry - sl) * units - cfg.cost * units
                    cash += pnl
                    trades.append(dict(dir="short", entry_time=d["time"].iloc[entry_i],
                                       exit_time=d["time"].iloc[t], entry=entry, exit=sl, pnl=pnl, reason="trail"))
                    pos = 0; cooldown = t

        # Execute pending entry at open of t (signal was on t-1)
        if pending_entry and pos == 0 and t - cooldown >= cfg.cooldown_bars:
            side, _ = pending_entry
            if side == "short":
                pos = -1; direction = -1; entry_i = t
                entry = short_entry_px(t); lowest = float(l.iloc[t])
                sl = max(entry + 1.5 * float(atr14.iloc[t - 1]), entry)
                units = (cash * cfg.risk) / max(sl - entry, 1e-9)
            else:
                pos = 1; direction = 1; entry_i = t
                entry = long_entry_px(t); highest = float(h.iloc[t])
                sl = min(entry - 1.5 * float(atr14.iloc[t - 1]), entry)
                units = (cash * cfg.risk) / max(entry - sl, 1e-9)
            pending_entry = None

        # Signals from completed bar t (close-based)
        r = float(rsi9.iloc[t]); m = float(ma7.iloc[t]); M = float(bb_m.iloc[t])
        U = float(bb_u.iloc[t]); L = float(bb_l.iloc[t]); w = float(wpr.iloc[t])
        r_prev = float(rsi9.iloc[t - 1]); m_prev = float(ma7.iloc[t - 1]); M_prev = float(bb_m.iloc[t - 1])
        w_prev = float(wpr.iloc[t - 1])
        vol_ok = float(atr14.iloc[t]) > float(atr_median.iloc[t]) if not np.isnan(atr_median.iloc[t]) else False

        if (m_prev >= M_prev and m < M) and (r_prev >= M_prev and r < M):
            dn_break_i = t
        if (m_prev <= M_prev and m > M) and (r_prev <= M_prev and r > M):
            up_break_i = t

        if not np.isnan(M) and not np.isnan(m):
            if ((r_prev <= M_prev and r > M) or (w_prev <= M_prev and w > M)) and t - dn_break_i <= cfg.break_window:
                pull_short = True
            if ((r_prev >= M_prev and r < M) or (w_prev >= M_prev and w < M)) and t - up_break_i <= cfg.break_window:
                pull_long = True

        sig_short = (
            pull_short and ((r_prev > M and r < M) or (r_prev > m and r < m)) and (L <= m <= M)
            and (not bool(uptrend.iloc[t])) and vol_ok
        )
        sig_long = (
            pull_long and ((r_prev < M and r > M) or (r_prev < m and r > m)) and (M <= m <= U)
            and (not bool(downtrend.iloc[t])) and vol_ok
        )

        # Opposite signal → schedule exit next bar (causal); simplified: exit at next open via pending
        if pos == 1 and sig_short:
            xp = long_exit_px_open(min(t + 1, n - 1)) if t + 1 < n else long_exit_px_open(t)
            # Use next bar if available
            exit_i = t + 1 if t + 1 < n else t
            xp = long_exit_px_open(exit_i)
            pnl = (xp - entry) * units - cfg.cost * units
            cash += pnl
            trades.append(dict(dir="long", entry_time=d["time"].iloc[entry_i],
                               exit_time=d["time"].iloc[exit_i], entry=entry, exit=xp, pnl=pnl, reason="reverse"))
            pos = 0; cooldown = exit_i; pull_short = False
        elif pos == -1 and sig_long:
            exit_i = t + 1 if t + 1 < n else t
            xp = short_exit_px_open(exit_i)
            pnl = (entry - xp) * units - cfg.cost * units
            cash += pnl
            trades.append(dict(dir="short", entry_time=d["time"].iloc[entry_i],
                               exit_time=d["time"].iloc[exit_i], entry=entry, exit=xp, pnl=pnl, reason="reverse"))
            pos = 0; cooldown = exit_i; pull_long = False

        if pos == 0 and t - cooldown >= cfg.cooldown_bars:
            if sig_short:
                pending_entry = ("short", t)
                pull_short = False
            elif sig_long:
                pending_entry = ("long", t)
                pull_long = False

        # MTM
        mtm = cash
        if pos == 1:
            mtm += (float(c.iloc[t]) - entry) * units
        elif pos == -1:
            mtm += (entry - float(c.iloc[t])) * units
        equity_cash.append((d["time"].iloc[t], cash))
        equity_mtm.append((d["time"].iloc[t], mtm))

    if pos != 0 and cfg.force_close_eod:
        t = n - 1
        if direction == 1:
            xp = long_exit_px_open(t)
            pnl = (xp - entry) * units - cfg.cost * units
        else:
            xp = short_exit_px_open(t)
            pnl = (entry - xp) * units - cfg.cost * units
        cash += pnl
        trades.append(dict(dir="long" if direction == 1 else "short",
                           entry_time=d["time"].iloc[entry_i], exit_time=d["time"].iloc[t],
                           entry=entry, exit=xp, pnl=pnl, reason="eod_force_close"))

    td = pd.DataFrame(trades)
    eq = pd.DataFrame(equity_cash, columns=["time", "cash"])
    eq["mtm"] = [x[1] for x in equity_mtm]
    return td, eq

def summary_stats(trades: pd.DataFrame, start_cash=10000.0):
    if trades is None or len(trades) == 0:
        return dict(trades=0, pf=None, net=0, win_pct=None, final=start_cash)
    pnl = trades["pnl"].astype(float)
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = float(gp / gl) if gl > 0 else None
    return dict(
        trades=int(len(trades)),
        pf=round(pf, 4) if pf is not None else None,
        net=round(float(pnl.sum()), 2),
        win_pct=round(100 * float((pnl > 0).mean()), 2),
        final=round(start_cash + float(pnl.sum()), 2),
    )
