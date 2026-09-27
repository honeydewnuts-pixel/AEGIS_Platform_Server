from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

EXPECTED_V37_SHA256 = "6e962ec23023f9c747514bed17077a9bc7dadc4b42591feb1e29140c1e580ed5"

@dataclass(frozen=True)
class ReplayResult:
    signals: np.ndarray
    trades: pd.DataFrame
    metrics: dict[str, float]


def load_v37_dataset(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != EXPECTED_V37_SHA256:
        raise ValueError(f"Unexpected V37 dataset SHA-256: {digest}")
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="raise")
    if not df["datetime"].is_monotonic_increasing:
        raise ValueError("V37 dataset is not chronologically sorted")
    required = {"BidOpen", "BidHigh", "BidLow", "BidClose", "AskOpen", "AskHigh", "AskLow", "AskClose"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing market-data columns: {sorted(missing)}")
    return df


def wilder_atr14(bid_high: np.ndarray, bid_low: np.ndarray, bid_close: np.ndarray) -> np.ndarray:
    """Exact frozen V31/V35 ATR recurrence recovered from the research implementation."""
    n = len(bid_close)
    tr = np.full(n, np.nan, dtype=float)
    if n > 1:
        tr[1:] = np.maximum.reduce([
            bid_high[1:] - bid_low[1:],
            np.abs(bid_high[1:] - bid_close[:-1]),
            np.abs(bid_low[1:] - bid_close[:-1]),
        ])
    atr = np.full(n, np.nan, dtype=float)
    if n > 1:
        atr[1] = tr[1]
        for k in range(2, n):
            atr[k] = (13.0 * atr[k - 1] + tr[k]) / 14.0
    atr[:14] = np.nan
    return atr


def trade_metrics(trades: pd.DataFrame) -> dict[str, float]:
    r = trades["R"].to_numpy(float) if len(trades) else np.array([], dtype=float)
    gp = float(r[r > 0].sum())
    gl = float(-r[r < 0].sum())
    eq = np.cumsum(r)
    dd = float((np.maximum.accumulate(eq) - eq).max()) if len(r) else float("nan")
    return {
        "trades": float(len(r)),
        "wins": float(np.sum(r > 0)),
        "losses": float(np.sum(r < 0)),
        "win_rate": float(np.mean(r > 0)) if len(r) else float("nan"),
        "PF": gp / gl if gl else float("nan"),
        "avg_R": float(np.mean(r)) if len(r) else float("nan"),
        "total_R": float(np.sum(r)) if len(r) else float("nan"),
        "max_DD": dd,
    }


# Historical V31/V35 cash-test reproduction only. Never use on demo/live P&L paths.
LEGACY_FIXED_COST_R = 0.085

# Cost modes for simulate_short / operational cash tests:
#   legacy_fixed_r — deduct LEGACY_FIXED_COST_R from gross R (exact historical reproduction)
#   bid_ask_only   — no extra R deduction; entry AskOpen / exit Bid already embed spread
#   configured     — deduct commission_r (+ optional fixed_cost_r) only; never invent spread
COST_MODE_LEGACY = "legacy_fixed_r"
COST_MODE_BID_ASK = "bid_ask_only"
COST_MODE_CONFIGURED = "configured"


def resolve_cost_deduction_r(
    cost_mode: str = COST_MODE_LEGACY,
    *,
    fixed_cost_r: float | None = None,
    commission_r: float = 0.0,
) -> tuple[float, str]:
    """Return (deduction_in_R_units, cost_model_label). Never fabricates unknown broker costs."""
    mode = (cost_mode or COST_MODE_LEGACY).strip().lower()
    if mode == COST_MODE_LEGACY:
        ded = LEGACY_FIXED_COST_R if fixed_cost_r is None else float(fixed_cost_r)
        return ded, "legacy_fixed_r_v1"
    if mode == COST_MODE_BID_ASK:
        # Spread is already in Ask entry vs Bid exit; do not subtract another fixed R.
        return 0.0, "bid_ask_embedded_v1"
    if mode == COST_MODE_CONFIGURED:
        ded = float(commission_r or 0.0)
        if fixed_cost_r is not None:
            ded += float(fixed_cost_r)
        return ded, "configured_v1"
    raise ValueError(f"Unknown cost_mode={cost_mode!r}")


def finalize_trades(
    df: pd.DataFrame,
    trades: list[tuple],
    *,
    cost_model_version: str = "legacy_fixed_r_v1",
) -> pd.DataFrame:
    """
    trades tuples:
      (event_i, exit_i, entry, exit, R, reason)  # legacy 6-tuple
      or
      (event_i, exit_i, entry, exit, R, reason, gross_R, cost_R)  # extended
    """
    if not trades:
        cols = [
            "event_i", "exit_i", "entry", "exit", "R", "reason",
            "gross_R", "cost_R", "cost_model_version",
        ]
        out = pd.DataFrame(columns=cols)
        return out.assign(
            signal_datetime=pd.Series(dtype="datetime64[ns]"),
            entry_datetime=pd.Series(dtype="datetime64[ns]"),
            exit_datetime=pd.Series(dtype="datetime64[ns]"),
            duration_bars=pd.Series(dtype="int64"),
        )

    nfields = len(trades[0])
    if nfields >= 8:
        out = pd.DataFrame(
            trades,
            columns=["event_i", "exit_i", "entry", "exit", "R", "reason", "gross_R", "cost_R"],
        )
    else:
        out = pd.DataFrame(trades, columns=["event_i", "exit_i", "entry", "exit", "R", "reason"])
        out["gross_R"] = out["R"]  # unknown split for pure legacy callers
        out["cost_R"] = 0.0
    out["cost_model_version"] = cost_model_version
    out["event_i"] = out["event_i"].astype(int)
    out["exit_i"] = out["exit_i"].astype(int)
    out["signal_datetime"] = df.loc[out.event_i, "datetime"].to_numpy()
    out["entry_datetime"] = df.loc[out.event_i + 1, "datetime"].to_numpy()
    out["exit_datetime"] = df.loc[out.exit_i, "datetime"].to_numpy()
    out["duration_bars"] = out["exit_i"] - out["event_i"]
    return out


def simulate_short(
    df: pd.DataFrame,
    atr: np.ndarray,
    events: np.ndarray,
    *,
    cost_mode: str = COST_MODE_LEGACY,
    fixed_cost_r: float | None = None,
    commission_r: float = 0.0,
) -> pd.DataFrame:
    """
    Short-only bar simulator matching frozen V31/V35 exit rules.

    Default cost_mode=legacy_fixed_r preserves historical V53.6/V31 reproduction
    (gross_R - 0.085). Operational / revised cash tests must pass
    cost_mode=bid_ask_only (or configured) so the universal 0.085R is not applied.

    Price convention (frozen):
      entry = next-bar AskOpen
      stop trigger = BidHigh
      time exit = BidClose
      BE at +1R, trail 0.75*ATR after BE, max hold 72 bars from entry bar
    """
    h = df["BidHigh"].to_numpy(float)
    c = df["BidClose"].to_numpy(float)
    ao = df["AskOpen"].to_numpy(float)
    n = len(df)
    cost_deduction, cost_label = resolve_cost_deduction_r(
        cost_mode, fixed_cost_r=fixed_cost_r, commission_r=commission_r
    )
    trades: list[tuple] = []
    next_allowed = 0
    for i in events:
        if i <= next_allowed or i + 1 >= n:
            continue
        A = atr[i]
        if A is None or not np.isfinite(A) or A <= 0:
            continue
        entry = ao[i + 1]
        risk = 1.5 * A
        stop = entry + risk
        be = False
        end = min(n - 1, i + 72)
        exit_i = None
        exit_px = None
        reason = None
        for j in range(i + 1, end + 1):
            if h[j] >= stop:
                exit_i = j
                exit_px = stop
                reason = "STOP"
                break
            rr = (entry - c[j]) / risk
            if rr >= 1.0 and not be:
                stop = entry
                be = True
            if be:
                candidate = c[j] + 0.75 * atr[j]
                if candidate < stop:
                    stop = candidate
            if j == end:
                exit_i = j
                exit_px = c[j]
                reason = "TIME"
        if exit_i is None:
            continue
        gross = (entry - exit_px) / risk
        cost_r = float(cost_deduction)
        R = gross - cost_r
        trades.append((i, exit_i, entry, exit_px, R, reason, gross, cost_r))
        next_allowed = exit_i
    return finalize_trades(df, trades, cost_model_version=cost_label)


def simulate_short_legacy(df: pd.DataFrame, atr: np.ndarray, events: np.ndarray) -> pd.DataFrame:
    """Explicit historical reproduction entrypoint (0.085R fixed cost)."""
    return simulate_short(df, atr, events, cost_mode=COST_MODE_LEGACY)


def simulate_short_operational(df: pd.DataFrame, atr: np.ndarray, events: np.ndarray) -> pd.DataFrame:
    """
    Operational cash-test path: Bid/Ask prices only; no universal 0.085R.
    Does not invent commission or slippage.
    """
    return simulate_short(df, atr, events, cost_mode=COST_MODE_BID_ASK)
