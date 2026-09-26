"""
Live short position management logic aligned with simulate_short() in
backend/app/rulebooks/evaluators/common.py.

Historical order of operations per bar j after entry:
  1. If BidHigh >= stop → STOP exit at stop price
  2. R = (entry - BidClose) / risk; if R >= 1.0 and not BE → stop = entry (BE)
  3. If BE: candidate = BidClose + 0.75 * ATR[j]; if candidate < stop → stop = candidate
  4. TIME at close of 72nd holding bar (simulate_short: j from i+1 to i+72 inclusive)

Live differences (documented, not hidden):
  - Historical entry = next-bar AskOpen; live uses actual fill price for risk/R.
  - Historical cost 0.085R is research-only; live incurs broker costs separately.
  - Live stop is enforced via broker SL modification + EA time-exit close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShortPositionState:
    signal_id: str
    symbol: str
    entry_price: float
    initial_risk: float  # 1.5 * ATR at signal (or entry-derived)
    atr_at_signal: float
    entry_bar_index: int = 0
    current_stop: float = 0.0
    be_active: bool = False
    max_hold_bars: int = 72
    trail_atr_mult: float = 0.75
    be_r: float = 1.0
    closed: bool = False
    close_reason: str | None = None
    exit_price: float | None = None
    exit_bar_index: int | None = None

    def __post_init__(self) -> None:
        if self.current_stop <= 0 and self.entry_price > 0 and self.initial_risk > 0:
            # Short: stop above entry
            self.current_stop = self.entry_price + self.initial_risk


def initial_stop_from_entry(entry_price: float, atr14: float, mult: float = 1.5) -> float:
    """Short initial stop using actual fill (faithful live alternative to AskOpen+1.5ATR)."""
    if entry_price <= 0 or atr14 <= 0:
        raise ValueError("entry_price and atr14 must be positive")
    return entry_price + mult * atr14


def risk_from_entry_and_stop(entry_price: float, stop: float) -> float:
    r = stop - entry_price  # short risk distance
    if r <= 0:
        raise ValueError("short stop must be above entry")
    return r


@dataclass
class BarOHLC:
    high: float  # BidHigh
    low: float
    close: float  # BidClose
    atr: float


def step_short_bar(state: ShortPositionState, bar: BarOHLC, bar_index: int) -> ShortPositionState:
    """
    One bar of management. Mutates a copy-like update; returns new state.
    Matches simulate_short loop body (stop check → R/BE → trail → time).
    """
    if state.closed:
        return state
    s = ShortPositionState(**{**state.__dict__})
    if s.initial_risk <= 0:
        s.closed = True
        s.close_reason = "INVALID_RISK"
        return s

    # 1) Stop hit on BidHigh
    if bar.high >= s.current_stop:
        s.closed = True
        s.close_reason = "STOP"
        s.exit_price = s.current_stop
        s.exit_bar_index = bar_index
        return s

    # 2) R from BidClose; BE at +1R
    rr = (s.entry_price - bar.close) / s.initial_risk
    if rr >= s.be_r and not s.be_active:
        s.current_stop = s.entry_price
        s.be_active = True

    # 3) Trail after BE: candidate = close + 0.75 * atr; only tighten (lower stop for short)
    if s.be_active and bar.atr > 0:
        candidate = bar.close + s.trail_atr_mult * bar.atr
        if candidate < s.current_stop:
            s.current_stop = candidate

    # 4) Time exit — holding bars include entry bar (relative 0).
    # simulate_short: j in [i+1, i+72] → TIME on j == i+72 = 72nd holding bar.
    # With entry_bar_index as first holding bar: TIME when
    #   (bar_index - entry_bar_index + 1) >= max_hold_bars
    held = bar_index - s.entry_bar_index + 1
    if held >= s.max_hold_bars:
        s.closed = True
        s.close_reason = "TIME"
        s.exit_price = bar.close
        s.exit_bar_index = bar_index
        return s

    return s


def simulate_live_short_path(
    entry_price: float,
    atr_signal: float,
    bars: list[BarOHLC],
    *,
    max_hold_bars: int = 72,
) -> ShortPositionState:
    """Run management from entry through bars (bar 0 = first bar after entry)."""
    risk = 1.5 * atr_signal
    st = ShortPositionState(
        signal_id="test",
        symbol="TEST",
        entry_price=entry_price,
        initial_risk=risk,
        atr_at_signal=atr_signal,
        entry_bar_index=0,
        max_hold_bars=max_hold_bars,
    )
    for j, bar in enumerate(bars):
        # bar_index matches simulate_short j starting at entry bar
        st = step_short_bar(st, bar, j)
        if st.closed:
            break
    return st


def holding_bars_inclusive(entry_bar_index: int, current_bar_index: int) -> int:
    """
    Number of holding bars from entry through current, inclusive.
    simulate_short: entry at i+1, last TIME bar at i+72 → 72 holding bars.
    """
    if current_bar_index < entry_bar_index:
        return 0
    return current_bar_index - entry_bar_index + 1


def should_time_exit(entry_bar_index: int, current_bar_index: int, max_hold_bars: int = 72) -> bool:
    """True on the max_hold-th holding bar (inclusive), matching simulate_short end=i+72."""
    return holding_bars_inclusive(entry_bar_index, current_bar_index) >= max_hold_bars
