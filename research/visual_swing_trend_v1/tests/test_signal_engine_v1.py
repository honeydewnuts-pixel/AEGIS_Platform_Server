#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from signal_engine_v1 import run_diagnostics, disagree_examples, EventType

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def synth(n=400, seed=1):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    mid = 100 + np.cumsum(rng.normal(0, 0.3, n))
    return pd.DataFrame({
        "time": t,
        "open": mid,
        "high": mid + rng.uniform(0.1, 0.8, n),
        "low": mid - rng.uniform(0.1, 0.8, n),
        "close": mid + rng.normal(0, 0.1, n),
    })

def main():
    df = synth()
    r = run_diagnostics(df, obb_on="rsi", d5_mode="A")
    c = r["counts"]
    check("has_counts", c["bars"] == len(df))
    check("reversal_disabled", c["reversal_enabled"] is False)
    check("add_disabled", c["official_add_enabled"] is False)
    check("initial_default_off", c["official_initial_enabled"] is False)
    check("d5_keys", "d5_A_bars" in c and "d5_B_bars" in c and "d5_C_bars" in c)
    # O1 vs O2 both runnable
    r2 = run_diagnostics(df, obb_on="ma7")
    check("o2_runs", r2["counts"]["bars"] == len(df))
    # disagree table builds
    d = disagree_examples(df, max_examples=5)
    check("disagree_df", isinstance(d, pd.DataFrame))
    # no official ADD/REVERSAL in events
    types = {e.event_type for e in r["events"]}
    check("no_official_add_event", EventType.ADD_SELL not in types and EventType.ADD_BUY not in types)
    check("no_reversal_event", EventType.CLOSE_FOR_REVERSAL not in types)
    print(f"TOTAL {P} PASS {F} FAIL")
    return 0 if F==0 else 1

if __name__ == "__main__":
    sys.exit(main())
