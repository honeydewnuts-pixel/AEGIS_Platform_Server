#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from p7_features import features, hourly, P7_L1, P7_L2

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def test_hand_calc():
    t0 = pd.Timestamp("2020-01-01", tz="UTC")
    rows=[]
    for i in range(25):
        for m in range(12):
            rows.append(dict(time=t0+pd.Timedelta(hours=i, minutes=5*m), open=100., high=102., low=99., close=101.))
    d=pd.DataFrame(rows)
    h=hourly(d)
    print("complete", int(h.complete.sum()), "of", len(h))
    f=features(h)
    complete_idx = h.index[h.complete]
    check("has_complete", len(complete_idx)>0)
    if len(complete_idx)==0: return
    i=complete_idx[-1]
    check("body", abs(f.loc[i,"body"]-1/3)<1e-9, str(f.loc[i,"body"]))
    check("upper_wick", abs(f.loc[i,"upper_wick"]-1/3)<1e-9)
    check("lower_wick", abs(f.loc[i,"lower_wick"]-1/3)<1e-9)
    check("close_location", abs(f.loc[i,"close_location"]-2/3)<1e-9)

def test_zero_range():
    h=pd.DataFrame(dict(open=[1.,1.],high=[1.,1.],low=[1.,1.],close=[1.,1.],complete=[True,True]))
    f=features(h)
    check("zero_range_nan_body", np.isnan(f.loc[1,"body"]))

def test_inside_equality():
    h=pd.DataFrame(dict(open=[10.,10.],high=[12.,12.],low=[8.,8.],close=[11.,11.],complete=[True,True]))
    f=features(h)
    check("inside_equality", f.loc[1,"inside"]==1.0)

def test_prefix():
    t0=pd.Timestamp("2020-01-01",tz="UTC")
    rows=[]
    for i in range(40):
        for m in range(12):
            rows.append(dict(time=t0+pd.Timedelta(hours=i,minutes=5*m),open=100+i*0.01,high=101+i*0.01,low=99+i*0.01,close=100.5+i*0.01))
    d=pd.DataFrame(rows)
    h1=hourly(d.iloc[:30*12]); f1=features(h1)
    h2=hourly(d); f2=features(h2)
    c1=h1.index[h1.complete]
    ok=True
    for i in c1:
        if i in f2.index and not np.isnan(f1.loc[i,"relative_range"]):
            if abs(f1.loc[i,"relative_range"]-f2.loc[i,"relative_range"])>1e-12:
                ok=False
    check("prefix_rr", ok)

def test_thresholds():
    check("l1_rr", abs(P7_L1["relative_range_max"]-0.5401154458522797)<1e-12)
    check("l2_ov", abs(P7_L2["overlap_max"]-0.21034089475870132)<1e-12)

if __name__=="__main__":
    test_hand_calc(); test_zero_range(); test_inside_equality(); test_prefix(); test_thresholds()
    print(f"TOTAL {P} PASS {F} FAIL"); sys.exit(0 if F==0 else 1)
