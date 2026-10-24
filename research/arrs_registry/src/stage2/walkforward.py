"""Chronological partitions and walk-forward evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import pandas as pd
from .simulator import simulate_trades, TradeManagementTemplate


@dataclass(frozen=True)
class PartitionSpec:
    train_frac: float = 0.6
    val_frac: float = 0.2
    test_frac: float = 0.2
    embargo_bars: int = 0  # purge after train

    def __post_init__(self):
        s = self.train_frac + self.val_frac + self.test_frac
        if abs(s - 1.0) > 1e-6:
            raise ValueError("partition fractions must sum to 1")


def chronological_partitions(n: int, spec: PartitionSpec) -> dict[str, tuple[int, int]]:
    """Return half-open index ranges [start, end)."""
    if n < 30:
        raise ValueError("INSUFFICIENT_DATA: n too small for partitions")
    t1 = int(n * spec.train_frac)
    t2 = t1 + int(n * spec.val_frac)
    # embargo after train
    train = (0, max(0, t1 - spec.embargo_bars))
    val = (t1, t2)
    test = (t2, n)
    return {"train": train, "val": val, "test": test}


def slice_df(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    return df.iloc[start:end].reset_index(drop=True)


def metrics_from_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades is None or len(trades) == 0:
        return {"trades": 0, "pf": None, "net": 0.0, "win_rate": None, "expectancy": None}
    pnl = trades["pnl"].astype(float)
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    pf = (gp / gl) if gl > 0 else (None if gp == 0 else float("inf"))
    return {
        "trades": int(len(trades)),
        "pf": None if pf is None or pf == float("inf") else round(pf, 4),
        "net": round(float(pnl.sum()), 6),
        "win_rate": round(float((pnl > 0).mean()), 4),
        "expectancy": round(float(pnl.mean()), 6),
        "avg_win": round(float(pnl[pnl > 0].mean()), 6) if (pnl > 0).any() else None,
        "avg_loss": round(float(pnl[pnl < 0].mean()), 6) if (pnl < 0).any() else None,
    }


def walk_forward_evaluate(
    df: pd.DataFrame,
    signals: pd.Series,
    tm: TradeManagementTemplate,
    *,
    partition: PartitionSpec | None = None,
    commission_per_side: float = 0.0,
    slippage: float = 0.0,
) -> dict[str, Any]:
    spec = partition or PartitionSpec()
    parts = chronological_partitions(len(df), spec)
    out: dict[str, Any] = {"partition_spec": spec.__dict__, "partitions": {}, "final_test_locked": True}
    for name, (a, b) in parts.items():
        sub = slice_df(df, a, b)
        sig = signals.iloc[a:b].reset_index(drop=True)
        if len(sub) < 20:
            out["partitions"][name] = {"status": "INSUFFICIENT_DATA", "range": [a, b]}
            continue
        tr = simulate_trades(sub, sig, tm=tm, commission_per_side=commission_per_side, slippage=slippage)
        m = metrics_from_trades(tr)
        m["range"] = [a, b]
        m["n_bars"] = len(sub)
        out["partitions"][name] = m
    return out
