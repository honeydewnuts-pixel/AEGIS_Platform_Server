"""Visual Swing-Trend V1.0 — research signal engine (partial).
production_authorized=false; execution_authorized=false.

Enabled paths:
  - Indicators (O1 default for research after screenshot evidence; O2 still switchable)
  - Causal 2-bar swing (D2 provisional)
  - Setup state + first-valid-close timing (D3 accepted)
  - Duplicate prevention infrastructure
  - One-add-per-pullback state machine (D5 path disabled until operator freezes A/B/C)

Disabled:
  - Official ADD_SELL/ADD_BUY until D5 frozen
  - All reversal events (D6 BLOCKED)
  - Position management / stops / sizing
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd

from indicators_v1 import compute_all, confirm_swings


class EventType(str, Enum):
    INITIAL_BUY = "INITIAL_BUY"
    INITIAL_SELL = "INITIAL_SELL"
    ADD_BUY = "ADD_BUY"
    ADD_SELL = "ADD_SELL"
    CLOSE_FOR_REVERSAL = "CLOSE_FOR_REVERSAL"
    REVERSAL_BUY = "REVERSAL_BUY"
    REVERSAL_SELL = "REVERSAL_SELL"
    SETUP_INVALIDATED = "SETUP_INVALIDATED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    PULLBACK_CANDIDATE = "PULLBACK_CANDIDATE"  # diagnostic only


@dataclass
class ResearchEvent:
    event_type: str
    bar_index: int
    signal_time: Any
    direction: str
    reason: str
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SetupState:
    active: bool = False
    direction: Optional[str] = None
    started_at: Optional[int] = None
    band_transition_at: Optional[int] = None
    ma_cross_m_at: Optional[int] = None
    price_swing_confirmed_at: Optional[int] = None
    rsi_swing_confirmed_at: Optional[int] = None


@dataclass
class PullbackState:
    """One-add-per-distinct-pullback infrastructure (D5 definition not frozen)."""
    in_pullback: bool = False
    add_emitted: bool = False
    started_at: Optional[int] = None
    last_distance: Optional[float] = None


def _cross_above(series: pd.Series) -> pd.Series:
    a = series.fillna(False)
    return (~a.shift(1).fillna(False)) & a


def run_diagnostics(
    df: pd.DataFrame,
    *,
    obb_on: str = "rsi",
    d5_mode: Optional[str] = None,  # None = no official ADD; 'A'|'B'|'C' for candidates only
    enable_initial: bool = False,  # False until D1+full INITIAL frozen by operator
) -> Dict[str, Any]:
    """Return diagnostic counts and optional research events.

    enable_initial=False by default: do not emit official INITIAL until operator
    confirms remaining INITIAL sequence details with D1.
    """
    out = compute_all(df, obb_on=obb_on)
    sh_price, sl_price = confirm_swings(df["high"], df["low"])
    # RSI swings (provisional D4)
    rsi_sh, rsi_sl = confirm_swings(out["RSI9"].ffill(), out["RSI9"].ffill())

    n = len(df)
    events: List[ResearchEvent] = []

    # --- candidate condition series ---
    outside_above = out["bb17u_outside_above"].fillna(False)
    outside_below = out["bb17l_outside_below"].fillna(False)
    exposed_u = out["bb34u_exposed"].fillna(False)
    exposed_l = out["bb34l_exposed"].fillna(False)
    ma_above_m = (out["MA7"] > out["OBB_M"]).fillna(False)
    ma_above_u = (out["MA7"] > out["OBB_U"]).fillna(False)
    ma_cross_m = _cross_above(ma_above_m)
    ma_cross_u = _cross_above(ma_above_u)

    # D5 candidates only
    bb34u = out["BB34_U"]
    hi = df["high"]
    cl = df["close"]
    dist = (bb34u - hi)  # positive when high below band
    A = (hi < bb34u) & (dist < dist.shift(1)) & exposed_u.fillna(False)
    B = (hi >= bb34u) & exposed_u.fillna(False)
    C = (cl > bb34u) & exposed_u.fillna(False)

    # Pullback state machine (infrastructure; no official ADD)
    pb = PullbackState()
    pullback_starts = 0
    pullback_ends = 0
    duplicate_blocked = 0
    for i in range(1, n):
        if not exposed_u.iloc[i]:
            if pb.in_pullback:
                pullback_ends += 1
            pb = PullbackState()
            continue
        # start: enter approach (A-style) from non-approach
        approaching = bool(A.iloc[i]) if d5_mode in (None, "A") else (
            bool(B.iloc[i]) if d5_mode == "B" else bool(C.iloc[i])
        )
        if approaching and not pb.in_pullback:
            pb = PullbackState(in_pullback=True, started_at=i, last_distance=float(dist.iloc[i]) if np.isfinite(dist.iloc[i]) else None)
            pullback_starts += 1
            events.append(ResearchEvent(
                EventType.PULLBACK_CANDIDATE, i, df["time"].iloc[i] if "time" in df.columns else i,
                "SELL", f"pullback_start_mode={d5_mode or 'A'}",
                {"bar": i},
            ))
        elif pb.in_pullback and approaching and pb.add_emitted:
            duplicate_blocked += 1
        # end: price moves away (distance increases) or leaves exposed
        if pb.in_pullback and not approaching:
            # only end if distance clearly increased or high fell away
            pullback_ends += 1
            pb = PullbackState()

    counts = {
        "bars": n,
        "obb_on": obb_on,
        "outside_above_bars": int(outside_above.sum()),
        "outside_below_bars": int(outside_below.sum()),
        "ma_cross_m": int(ma_cross_m.sum()),
        "ma_cross_u": int(ma_cross_u.sum()),
        "d5_A_bars": int(A.sum()),
        "d5_B_bars": int(B.sum()),
        "d5_C_bars": int(C.sum()),
        "pullback_starts": pullback_starts,
        "pullback_ends": pullback_ends,
        "duplicate_approaches_blocked": duplicate_blocked,
        "official_initial_enabled": enable_initial,
        "official_add_enabled": False,
        "reversal_enabled": False,
        "research_events": len(events),
    }
    return {"counts": counts, "events": events, "frame": out}


def disagree_examples(df: pd.DataFrame, obb_on: str = "rsi", max_examples: int = 8) -> pd.DataFrame:
    """Bars where D5 A/B/C disagree under exposed context."""
    out = compute_all(df, obb_on=obb_on)
    exp = out["bb34u_exposed"].fillna(False)
    bb34u = out["BB34_U"]
    hi = df["high"]
    cl = df["close"]
    dist = bb34u - hi
    A = (hi < bb34u) & (dist < dist.shift(1))
    B = hi >= bb34u
    C = cl > bb34u
    # disagree: exactly one of B,C or A without B
    mask = exp & ((A.astype(int) + B.astype(int) + C.astype(int)) == 1)
    rows = []
    idxs = np.where(mask.fillna(False).to_numpy())[0][:max_examples]
    for i in idxs:
        rows.append({
            "time": df["time"].iloc[i] if "time" in df.columns else i,
            "high": float(hi.iloc[i]),
            "close": float(cl.iloc[i]),
            "BB34_U": float(bb34u.iloc[i]),
            "A": bool(A.iloc[i]),
            "B": bool(B.iloc[i]),
            "C": bool(C.iloc[i]),
            "dist_to_band": float(dist.iloc[i]),
        })
    return pd.DataFrame(rows)
