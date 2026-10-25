#!/usr/bin/env python3
import sys
from pathlib import Path
import pandas as pd
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
from signals import signal_inside_break, signal_range20_break

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

# synthetic
n=100
t=pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC")
mid=np.linspace(1.1,1.2,n)
df=pd.DataFrame({
    "time":t,
    "bid_open":mid,"bid_high":mid+0.001,"bid_low":mid-0.001,"bid_close":mid,
    "ask_open":mid+0.0001,"ask_high":mid+0.0011,"ask_low":mid-0.0009,"ask_close":mid+0.0001,
})
# force an inside then break
df.loc[10,"bid_high"]=1.105; df.loc[10,"bid_low"]=1.095; df.loc[10,"bid_close"]=1.100
df.loc[11,"bid_high"]=1.104; df.loc[11,"bid_low"]=1.096; df.loc[11,"bid_close"]=1.100  # inside
df.loc[12,"bid_high"]=1.110; df.loc[12,"bid_low"]=1.098; df.loc[12,"bid_close"]=1.109  # break up

s=signal_inside_break(df)
check("inside_break_fires", s.iloc[12]==1.0, str(s.iloc[12]))
s2=signal_range20_break(df)
check("range_len", len(s2)==n)
check("no_nan", not s2.isna().any())
print(f"TOTAL {P} PASS {F} FAIL")
sys.exit(0 if F==0 else 1)
