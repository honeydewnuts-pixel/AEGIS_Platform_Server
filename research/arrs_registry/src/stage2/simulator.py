"""Causal Bid/Ask trade simulation with explicit trade-management templates."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal
import pandas as pd
import numpy as np


@dataclass(frozen=True)
class TradeManagementTemplate:
    template_id: str
    version: str
    initial_stop_atr: float | None = 1.5
    take_profit_atr: float | None = None
    max_hold_bars: int | None = 72
    trail_atr: float | None = None
    trail_activate_atr: float | None = None
    atr_period: int = 14
    same_bar_policy: str = "stop_first"  # conservative
    gap_policy: str = "worse_open"  # fill at open if beyond stop

    def to_dict(self):
        return asdict(self)


def atr_series(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["bid_high"], df["bid_low"], df["bid_close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def simulate_trades(
    df: pd.DataFrame,
    signals: pd.Series,
    *,
    tm: TradeManagementTemplate,
    commission_per_side: float = 0.0,
    slippage: float = 0.0,
) -> pd.DataFrame:
    """
    signals: +1 long, -1 short, 0 none. Signal at index t uses completed bar t;
    entry at next bar open (Ask for long, Bid for short).
    """
    assert len(signals) == len(df)
    atr = atr_series(df, tm.atr_period)
    trades = []
    pos = 0
    entry = entry_i = units = sl = tp = highest = lowest = 0.0
    direction = 0
    n = len(df)

    for t in range(1, n):
        # Manage existing position on bar t
        if pos != 0:
            bars_held = t - entry_i
            # trail update from prior completed extremes
            if tm.trail_atr and tm.trail_activate_atr and direction == 1:
                highest = max(highest, float(df["bid_high"].iloc[t - 1]))
                if highest - entry >= tm.trail_activate_atr * float(atr.iloc[t - 1] or 0):
                    sl = max(sl, highest - tm.trail_atr * float(atr.iloc[t - 1]))
            if tm.trail_atr and tm.trail_activate_atr and direction == -1:
                lowest = min(lowest, float(df["bid_low"].iloc[t - 1]))
                if entry - lowest >= tm.trail_activate_atr * float(atr.iloc[t - 1] or 0):
                    sl = min(sl, lowest + tm.trail_atr * float(atr.iloc[t - 1]))

            hit_sl = hit_tp = False
            exit_px = None
            reason = None
            if direction == 1:
                # long stop/target on bid
                open_bid = float(df["bid_open"].iloc[t])
                if open_bid <= sl:
                    exit_px = open_bid  # gap
                    reason = "gap_stop"
                    hit_sl = True
                elif float(df["bid_low"].iloc[t]) <= sl:
                    hit_sl = True
                    exit_px = sl
                    reason = "stop"
                if tm.take_profit_atr and float(df["bid_high"].iloc[t]) >= tp:
                    hit_tp = True
                if hit_sl and hit_tp:
                    # conservative stop first
                    exit_px = sl
                    reason = "stop_first_collision"
                elif hit_tp and not hit_sl:
                    exit_px = tp
                    reason = "tp"
            else:
                open_ask = float(df["ask_open"].iloc[t])
                if open_ask >= sl:
                    exit_px = open_ask
                    reason = "gap_stop"
                    hit_sl = True
                elif float(df["ask_high"].iloc[t]) >= sl:
                    hit_sl = True
                    exit_px = sl
                    reason = "stop"
                if tm.take_profit_atr and float(df["ask_low"].iloc[t]) <= tp:
                    hit_tp = True
                if hit_sl and hit_tp:
                    exit_px = sl
                    reason = "stop_first_collision"
                elif hit_tp and not hit_sl:
                    exit_px = tp
                    reason = "tp"

            if tm.max_hold_bars and bars_held >= tm.max_hold_bars and exit_px is None:
                exit_px = float(df["bid_open"].iloc[t]) if direction == 1 else float(df["ask_open"].iloc[t])
                reason = "max_hold"

            if exit_px is not None:
                # unit size 1 price unit for research; costs explicit
                if direction == 1:
                    pnl = (exit_px - entry) - 2 * commission_per_side - 2 * slippage
                else:
                    pnl = (entry - exit_px) - 2 * commission_per_side - 2 * slippage
                trades.append({
                    "dir": "long" if direction == 1 else "short",
                    "entry_i": entry_i, "exit_i": t,
                    "entry_time": str(df["time"].iloc[entry_i]),
                    "exit_time": str(df["time"].iloc[t]),
                    "entry": entry, "exit": exit_px, "pnl": pnl, "reason": reason,
                })
                pos = 0

        # New entry: signal from previous completed bar t-1 → enter at open of t
        if pos == 0:
            sig = int(signals.iloc[t - 1]) if not pd.isna(signals.iloc[t - 1]) else 0
            a = float(atr.iloc[t - 1]) if not pd.isna(atr.iloc[t - 1]) else None
            if sig == 1 and a and a > 0:
                entry = float(df["ask_open"].iloc[t]) + slippage
                entry_i = t
                direction = 1
                pos = 1
                highest = float(df["bid_high"].iloc[t])
                sl = entry - (tm.initial_stop_atr or 1.5) * a
                tp = entry + tm.take_profit_atr * a if tm.take_profit_atr else None
            elif sig == -1 and a and a > 0:
                entry = float(df["bid_open"].iloc[t]) - slippage
                entry_i = t
                direction = -1
                pos = -1
                lowest = float(df["bid_low"].iloc[t])
                sl = entry + (tm.initial_stop_atr or 1.5) * a
                tp = entry - tm.take_profit_atr * a if tm.take_profit_atr else None

    # EOD force close
    if pos != 0:
        t = n - 1
        exit_px = float(df["bid_open"].iloc[t]) if direction == 1 else float(df["ask_open"].iloc[t])
        if direction == 1:
            pnl = (exit_px - entry) - 2 * commission_per_side - 2 * slippage
        else:
            pnl = (entry - exit_px) - 2 * commission_per_side - 2 * slippage
        trades.append({
            "dir": "long" if direction == 1 else "short",
            "entry_i": entry_i, "exit_i": t,
            "entry_time": str(df["time"].iloc[entry_i]),
            "exit_time": str(df["time"].iloc[t]),
            "entry": entry, "exit": exit_px, "pnl": pnl, "reason": "eod_force_close",
        })
    return pd.DataFrame(trades)
