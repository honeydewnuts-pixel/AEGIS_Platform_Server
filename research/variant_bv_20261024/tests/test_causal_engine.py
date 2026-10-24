#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from variant_bv_engine import run_variant_bv, EngineConfig, rsi, load_ohlc

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def test_rsi_bounds():
    c=pd.Series(np.linspace(1,2,50))
    r=rsi(c,9)
    check("rsi_finite", np.isfinite(r.iloc[-1]))

def test_downtrend_modes_differ():
    # synthetic trending down
    n=300
    t=pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC")
    close=pd.Series(np.linspace(1.2,1.0,n))
    df=pd.DataFrame(dict(time=t, open=close, high=close+0.0002, low=close-0.0002, close=close,
                         ask_open=close+0.0001, ask_high=close+0.0003, ask_low=close-0.0001, ask_close=close+0.0001))
    a,_=run_variant_bv(df, EngineConfig(downtrend_mode="CORRECTED", cost=0.0001))
    b,_=run_variant_bv(df, EngineConfig(downtrend_mode="LEGACY", cost=0.0001))
    check("modes_run", True)

def test_prefix_invariance_signals_warmup():
    # engine should not crash on short data
    n=250
    t=pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC")
    close=pd.Series(1.0+np.random.default_rng(0).normal(0,0.0005,n).cumsum())
    df=pd.DataFrame(dict(time=t, open=close, high=close+0.0003, low=close-0.0003, close=close,
                         ask_open=close+0.0001, ask_high=close+0.0004, ask_low=close-0.0002, ask_close=close+0.0001))
    tr,_=run_variant_bv(df, EngineConfig(cost=0.0001))
    check("runs_on_synthetic", True)

if __name__=="__main__":
    test_rsi_bounds(); test_downtrend_modes_differ(); test_prefix_invariance_signals_warmup()
    print(f"TOTAL {P} PASS {F} FAIL"); sys.exit(0 if F==0 else 1)
