"""Dataset validation and identity for Class A Bid/Ask bars."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np


def dataset_hash(path: str | Path, extra: dict | None = None) -> str:
    p = Path(path)
    h = hashlib.sha256()
    h.update(p.read_bytes())
    if extra:
        h.update(json.dumps(extra, sort_keys=True).encode())
    return h.hexdigest()


def load_bid_ask_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {str(c).lower().strip(): c for c in df.columns}
    def col(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None
    t = col("time", "timestamp", "date", "datetime")
    if t is None:
        raise ValueError("INSUFFICIENT_DATA: missing timestamp column")
    # Prefer explicit bid/ask
    bo = col("bid_open", "bidopen", "open_bid")
    bh = col("bid_high", "bidhigh")
    bl = col("bid_low", "bidlow")
    bc = col("bid_close", "bidclose")
    ao = col("ask_open", "askopen", "open_ask")
    ah = col("ask_high", "askhigh")
    al = col("ask_low", "asklow")
    ac = col("ask_close", "askclose")
    if not all([bo, bh, bl, bc, ao, ah, al, ac]):
        # Fall back: open/high/low/close as bid; no ask → Class B
        o, h, l, c = col("open"), col("high"), col("low"), col("close")
        if not all([o, h, l, c]):
            raise ValueError("INSUFFICIENT_DATA: missing OHLC and Bid/Ask")
        out = pd.DataFrame({
            "time": pd.to_datetime(df[t], utc=True, errors="coerce"),
            "bid_open": pd.to_numeric(df[o], errors="coerce"),
            "bid_high": pd.to_numeric(df[h], errors="coerce"),
            "bid_low": pd.to_numeric(df[l], errors="coerce"),
            "bid_close": pd.to_numeric(df[c], errors="coerce"),
        })
        out["ask_open"] = out["bid_open"]
        out["ask_high"] = out["bid_high"]
        out["ask_low"] = out["bid_low"]
        out["ask_close"] = out["bid_close"]
        out.attrs["data_class"] = "B_OHLC_PROXY"
    else:
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
        })
        out.attrs["data_class"] = "A_BIDASK"
    out = out.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return out


def validate_bid_ask(df: pd.DataFrame, *, min_rows: int = 50) -> dict[str, Any]:
    """Fail-closed validation. Returns report with ok bool and issues list."""
    issues = []
    data_class = df.attrs.get("data_class", "UNKNOWN")
    if len(df) < min_rows:
        issues.append(f"insufficient_rows:{len(df)}<{min_rows}")
    if not df["time"].is_monotonic_increasing:
        issues.append("timestamps_not_sorted")
    if df["time"].duplicated().any():
        issues.append("duplicate_timestamps")
    # OHLC consistency bid
    bad_bid = (df["bid_high"] < df["bid_low"]) | (df["bid_high"] < df["bid_open"]) | (df["bid_high"] < df["bid_close"])
    bad_bid |= (df["bid_low"] > df["bid_open"]) | (df["bid_low"] > df["bid_close"])
    if bad_bid.any():
        issues.append(f"invalid_bid_ohlc:{int(bad_bid.sum())}")
    bad_ask = (df["ask_high"] < df["ask_low"]) | (df["ask_high"] < df["ask_open"]) | (df["ask_high"] < df["ask_close"])
    if bad_ask.any():
        issues.append(f"invalid_ask_ohlc:{int(bad_ask.sum())}")
    crossed = (df["bid_open"] > df["ask_open"]) | (df["bid_close"] > df["ask_close"])
    if crossed.any():
        issues.append(f"crossed_quotes:{int(crossed.sum())}")
    # Gaps (median step)
    if len(df) > 2:
        deltas = df["time"].diff().dt.total_seconds().dropna()
        med = float(deltas.median()) if len(deltas) else 0
        if med > 0:
            large = deltas > med * 10
            if large.any():
                issues.append(f"large_gaps:{int(large.sum())}")  # warning-level; still ok for research
    ok = not any(
        x.startswith(p)
        for x in issues
        for p in ("insufficient_rows", "timestamps_not_sorted", "duplicate_timestamps",
                  "invalid_bid_ohlc", "invalid_ask_ohlc")
    )
    # crossed quotes: reject if many
    if any(x.startswith("crossed_quotes") for x in issues):
        n_cross = int([x for x in issues if x.startswith("crossed_quotes")][0].split(":")[1])
        if n_cross > max(5, len(df) * 0.01):
            ok = False
    return {
        "ok": ok,
        "issues": issues,
        "data_class": data_class,
        "n_rows": len(df),
        "start": str(df["time"].iloc[0]) if len(df) else None,
        "end": str(df["time"].iloc[-1]) if len(df) else None,
    }
