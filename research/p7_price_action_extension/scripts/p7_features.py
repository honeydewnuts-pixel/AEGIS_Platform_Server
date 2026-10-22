"""P7 price-action features — exact formulas from P7_Gold_Cash_Replay_Engine.py."""
from __future__ import annotations
import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "body", "upper_wick", "lower_wick", "close_location", "relative_range",
    "move3", "move6", "move12", "overlap", "inside", "outside",
]
P7_L1 = dict(relative_range_max=0.5401154458522797, upper_wick_min=0.048643046990036964, overlap_min=0.6506349742412567)
P7_L2 = dict(relative_range_min=0.5401154458522797, lower_wick_max=0.07916074246168137, overlap_max=0.21034089475870132)

def load_ohlc(path: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    d.columns = [str(x).strip().strip("<>").lower() for x in d.columns]
    if "time" not in d.columns:
        for k in ("timestamp", "datetime", "date"):
            if k in d.columns:
                d = d.rename(columns={k: "time"}); break
    d["time"] = pd.to_datetime(d["time"], utc=True, errors="coerce")
    for k in ("open", "high", "low", "close"):
        if k not in d.columns:
            if f"bid_{k}" in d.columns: d[k] = d[f"bid_{k}"]
            elif f"bid{k}" in d.columns: d[k] = d[f"bid{k}"]
    for k in ("open", "high", "low", "close"):
        d[k] = pd.to_numeric(d[k], errors="coerce")
    d = d.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
    return d

def hourly(d: pd.DataFrame) -> pd.DataFrame:
    z = d.copy()
    z["bucket"] = z["time"].dt.floor("h")
    g = z.groupby("bucket", sort=True)
    h = g.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        first_observed=("time", "first"), last_observed=("time", "last"), count=("time", "size"),
    )
    h["decision_time"] = h.index + pd.Timedelta(hours=1)
    def _regular(x):
        if len(x) != 12: return False
        arr = pd.to_datetime(x, utc=True).values.astype("datetime64[ns]").astype(np.int64)
        return bool(np.array_equal(arr - arr[0], np.arange(12) * 300_000_000_000))
    regular = g["time"].apply(_regular)
    h["complete"] = (
        (h["count"] == 12)
        & (h["first_observed"] == h.index)
        & (h["last_observed"] == h.index + pd.Timedelta(minutes=55))
        & regular
    )
    return h.reset_index()

def features(h: pd.DataFrame) -> pd.DataFrame:
    o, hi, lo, c = h["open"], h["high"], h["low"], h["close"]
    rg = (hi - lo).replace(0, np.nan)
    sc = (hi - lo).rolling(20).median().replace(0, np.nan)
    x = pd.DataFrame(index=h.index)
    x["body"] = (c - o) / rg
    x["upper_wick"] = (hi - pd.concat([o, c], axis=1).max(axis=1)) / rg
    x["lower_wick"] = (pd.concat([o, c], axis=1).min(axis=1) - lo) / rg
    x["close_location"] = (c - lo) / rg
    x["relative_range"] = rg / sc
    for p in (3, 6, 12):
        x[f"move{p}"] = (c - c.shift(p)) / sc
    it = (pd.concat([hi, hi.shift()], axis=1).min(axis=1) - pd.concat([lo, lo.shift()], axis=1).max(axis=1)).clip(lower=0)
    un = pd.concat([hi, hi.shift()], axis=1).max(axis=1) - pd.concat([lo, lo.shift()], axis=1).min(axis=1)
    x["overlap"] = it / un.replace(0, np.nan)
    x["inside"] = ((hi <= hi.shift()) & (lo >= lo.shift())).astype(float)
    x["outside"] = ((hi > hi.shift()) & (lo < lo.shift())).astype(float)
    if "complete" in h.columns:
        x.loc[~h["complete"].astype(bool), :] = np.nan
    return x

def events_p7_l1(feat: pd.DataFrame) -> pd.Series:
    return (
        (feat["relative_range"] <= P7_L1["relative_range_max"])
        & (feat["upper_wick"] > P7_L1["upper_wick_min"])
        & (feat["overlap"] > P7_L1["overlap_min"])
        & feat["relative_range"].notna() & feat["upper_wick"].notna() & feat["overlap"].notna()
    )

def events_p7_l2(feat: pd.DataFrame) -> pd.Series:
    return (
        (feat["relative_range"] > P7_L2["relative_range_min"])
        & (feat["lower_wick"] <= P7_L2["lower_wick_max"])
        & (feat["overlap"] <= P7_L2["overlap_max"])
        & feat["relative_range"].notna() & feat["lower_wick"].notna() & feat["overlap"].notna()
    )
