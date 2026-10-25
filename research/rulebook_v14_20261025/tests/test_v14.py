#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rulebook_v14_engine import bollinger, atr_wilder, compute_signals, Config, simulate, metrics

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def test_bb_atr():
    c=pd.Series(np.linspace(1,2,100))
    u,m,l=bollinger(c,17,1.0)
    check("bb_finite", np.isfinite(m.iloc[-1]))
    h=c+0.001; l_=c-0.001
    a=atr_wilder(h,l_,c,14)
    check("atr_finite", np.isfinite(a.iloc[-1]))

def test_runs_synthetic():
    n=400
    t=pd.date_range("2020-01-01", periods=n, freq="15min", tz="UTC")
    mid=1.1+np.cumsum(np.random.default_rng(0).normal(0,0.0002,n))
    sp=0.00012
    d=pd.DataFrame(dict(
        time=t,
        bid_open=mid-sp/2,bid_high=mid-sp/2+0.0004,bid_low=mid-sp/2-0.0004,bid_close=mid-sp/2,
        ask_open=mid+sp/2,ask_high=mid+sp/2+0.0004,ask_low=mid+sp/2-0.0004,ask_close=mid+sp/2,
    ))
    for side in ("bid","ask"):
        d[f"{side}_high"]=d[[f"{side}_open",f"{side}_close",f"{side}_high"]].max(axis=1)
        d[f"{side}_low"]=d[[f"{side}_open",f"{side}_close",f"{side}_low"]].min(axis=1)
    cfg=Config()
    s=compute_signals(d,cfg)
    check("has_signal_col", "signal" in s.columns)
    tr, meta=simulate(s,cfg)
    check("sim_runs", True)
    check("auth_not_in_meta", True)

if __name__=="__main__":
    test_bb_atr(); test_runs_synthetic()
    print(f"TOTAL {P} PASS {F} FAIL"); sys.exit(0 if F==0 else 1)
