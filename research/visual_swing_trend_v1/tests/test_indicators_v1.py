#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from indicators_v1 import bollinger, rsi, compute_all, confirm_swings

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def main():
    c=pd.Series(np.linspace(100,110,200)+np.sin(np.linspace(0,8,200)))
    u,m,l=bollinger(c,17,1.0)
    check("bb_finite", np.isfinite(m.iloc[-1]))
    check("bb_order", float(u.iloc[-1])>=float(l.iloc[-1]))
    r=rsi(c,9)
    check("rsi_range", 0<=float(r.dropna().iloc[-1])<=100)
    n=300
    t=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
    mid=100+np.cumsum(np.random.default_rng(0).normal(0,0.2,n))
    df=pd.DataFrame({"time":t,"open":mid,"high":mid+0.5,"low":mid-0.5,"close":mid})
    out=compute_all(df, obb_on="rsi")
    check("has_obb", "OBB_U" in out.columns)
    check("warmup_nan", out["BB34_U"].isna().sum()>=33)
    sh,sl=confirm_swings(df["high"], df["low"])
    check("swing_series", len(sh)==n)
    # no look-ahead: first 4 bars cannot confirm
    check("no_early_swing", pd.isna(sh.iloc[:4]).all())
    print(f"TOTAL {P} PASS {F} FAIL")
    return 0 if F==0 else 1

if __name__=="__main__":
    sys.exit(main())
