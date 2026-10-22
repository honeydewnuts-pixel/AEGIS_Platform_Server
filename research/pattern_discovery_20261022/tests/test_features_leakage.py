#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from features import build_features, forward_labels

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def synthetic_bars(n=100):
    import pandas as pd
    rng = np.random.default_rng(0)
    c = np.cumsum(rng.normal(0, 0.001, n)) + 1.0
    h = c + 0.001; l = c - 0.001; o = c.copy()
    dt = pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC")
    return dict(dt=dt.to_series().reset_index(drop=True), open=o, high=h, low=l, close=c, spread=np.zeros(n))

def test_prefix_features():
    bars = synthetic_bars(200)
    f_full = build_features(bars)
    bars_p = {k: (v[:120] if hasattr(v,'__getitem__') and not isinstance(v, dict) else v) for k,v in bars.items()}
    # rebuild dt properly
    import pandas as pd
    bars_p["dt"] = bars["dt"].iloc[:120]
    for k in ("open","high","low","close","spread"):
        bars_p[k] = bars[k][:120]
    f_pref = build_features(bars_p)
    i = 50
    check("prefix_ret1", abs(f_full["ret1"][i]-f_pref["ret1"][i])<1e-12 or (np.isnan(f_full["ret1"][i]) and np.isnan(f_pref["ret1"][i])))
    check("prefix_range_vs_20", abs(f_full["range_vs_20"][i]-f_pref["range_vs_20"][i])<1e-12 or (np.isnan(f_full["range_vs_20"][i]) and np.isnan(f_pref["range_vs_20"][i])))

def test_label_uses_future_only_as_label():
    c = np.arange(1, 21, dtype=float)
    lab = forward_labels(c, (3,))
    expected = (c[3]-c[0])/(c[0]+1e-12)
    check("label_at_0", abs(lab["fwd_ret_3"][0] - expected)<1e-9, str(lab["fwd_ret_3"][0]))
    check("label_nan_at_end", np.isnan(lab["fwd_ret_3"][18]))

def test_range_vs_20_past_only():
    bars = synthetic_bars(50)
    f = build_features(bars)
    # range_vs_20 at i should not use rng[i] in the mean denominator window
    check("warmup_nan", np.isnan(f["range_vs_20"][10]))

if __name__=="__main__":
    test_prefix_features(); test_label_uses_future_only_as_label(); test_range_vs_20_past_only()
    print(f"TOTAL {P} PASS {F} FAIL"); sys.exit(0 if F==0 else 1)
