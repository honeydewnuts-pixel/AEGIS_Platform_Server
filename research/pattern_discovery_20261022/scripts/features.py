"""Price-structure features from completed M5 bars — no conventional indicators."""
from __future__ import annotations
import numpy as np

def load_ohlc(path: str, data_class: str):
    import pandas as pd
    df = pd.read_csv(path)
    ts = None
    for c in df.columns:
        if "time" in c.lower() or c.lower() == "date":
            ts = c; break
    if ts is None:
        ts = df.columns[0]
    df["datetime"] = pd.to_datetime(df[ts], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    cols = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in cols:
                return df[cols[n]].astype(float).to_numpy()
        raise KeyError(names)
    if data_class == "A_BIDASK":
        o = pick("bid_open", "bidopen")
        h = pick("bid_high", "bidhigh")
        l = pick("bid_low", "bidlow")
        c = pick("bid_close", "bidclose")
        spread = pick("ask_close", "askclose") - c
    else:
        o, h, l, c = pick("open"), pick("high"), pick("low"), pick("close")
        spread = np.zeros(len(c))
    return dict(dt=df["datetime"], open=o, high=h, low=l, close=c, spread=spread)

def build_features(bars):
    """Causal features at bar t using only bars <= t (completed)."""
    o, h, l, c = bars["open"], bars["high"], bars["low"], bars["close"]
    n = len(c)
    rng = h - l
    body = np.abs(c - o)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l
    # avoid div0
    eps = 1e-12
    f = {}
    f["range"] = rng
    f["body_frac"] = body / (rng + eps)
    f["upper_wick_frac"] = upper_wick / (rng + eps)
    f["lower_wick_frac"] = lower_wick / (rng + eps)
    f["close_loc"] = (c - l) / (rng + eps)  # 0=low, 1=high
    f["dir"] = np.sign(c - o)  # +1 bull, -1 bear, 0 doji
    f["ret1"] = np.full(n, np.nan)
    f["ret1"][1:] = (c[1:] - c[:-1]) / (c[:-1] + eps)
    f["abs_ret1"] = np.abs(f["ret1"])
    # multi-bar returns (causal: from t-k to t)
    for k in (3, 6, 12):
        r = np.full(n, np.nan)
        r[k:] = (c[k:] - c[:-k]) / (c[:-k] + eps)
        f[f"ret{k}"] = r
    # range vs recent mean range (exclude current for pure past — use prior)
    mean_rng20 = np.full(n, np.nan)
    for i in range(20, n):
        mean_rng20[i] = np.mean(rng[i - 20:i])  # past only
    f["range_vs_20"] = rng / (mean_rng20 + eps)
    # consecutive same-direction count (ending at t)
    consec = np.zeros(n)
    for i in range(1, n):
        if f["dir"][i] != 0 and f["dir"][i] == f["dir"][i - 1]:
            consec[i] = consec[i - 1] + 1
        else:
            consec[i] = 0
    f["consec_dir"] = consec
    # higher-high / lower-low flags vs prior bar
    f["hh"] = np.zeros(n); f["ll"] = np.zeros(n)
    f["hh"][1:] = (h[1:] > h[:-1]).astype(float)
    f["ll"][1:] = (l[1:] < l[:-1]).astype(float)
    # inside / outside bar
    f["inside"] = np.zeros(n); f["outside"] = np.zeros(n)
    f["inside"][1:] = ((h[1:] <= h[:-1]) & (l[1:] >= l[:-1])).astype(float)
    f["outside"][1:] = ((h[1:] > h[:-1]) & (l[1:] < l[:-1])).astype(float)
    # engulfing (simple)
    f["bull_engulf"] = np.zeros(n); f["bear_engulf"] = np.zeros(n)
    f["bull_engulf"][1:] = ((c[1:] > o[1:]) & (c[:-1] < o[:-1]) & (c[1:] >= o[:-1]) & (o[1:] <= c[:-1])).astype(float)
    f["bear_engulf"][1:] = ((c[1:] < o[1:]) & (c[:-1] > o[:-1]) & (c[1:] <= o[:-1]) & (o[1:] >= c[:-1])).astype(float)
    # UTC hour / dow
    hour = bars["dt"].dt.hour.to_numpy()
    dow = bars["dt"].dt.dayofweek.to_numpy()
    f["hour"] = hour.astype(float)
    f["dow"] = dow.astype(float)
    # distance from recent 20-bar high/low (past only)
    dist_hi = np.full(n, np.nan); dist_lo = np.full(n, np.nan)
    for i in range(20, n):
        rh = np.max(h[i - 20:i])
        rl = np.min(l[i - 20:i])
        dist_hi[i] = (c[i] - rh) / (rh + eps)
        dist_lo[i] = (c[i] - rl) / (rl + eps)
    f["dist_20hi"] = dist_hi
    f["dist_20lo"] = dist_lo
    return f

def forward_labels(close, horizons=(3, 6, 12, 24, 48)):
    """Forward signed return from t to t+h using close[t+h]/close[t]. Label at t uses future — only for evaluation."""
    n = len(close)
    labels = {}
    for h in horizons:
        y = np.full(n, np.nan)
        y[: n - h] = (close[h:] - close[: n - h]) / (close[: n - h] + 1e-12)
        labels[f"fwd_ret_{h}"] = y
        labels[f"fwd_dir_{h}"] = np.sign(y)
    return labels
