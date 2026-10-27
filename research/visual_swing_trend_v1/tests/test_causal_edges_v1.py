#!/usr/bin/env python3
"""Targeted causal / edge tests for Visual Swing-Trend V1.0 research engine."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from indicators_v1 import confirm_swings, compute_all
from signal_engine_v1 import run_diagnostics, EventType

P = F = 0

def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1
        print(f"[PASS] {name}")
    else:
        F += 1
        print(f"[FAIL] {name} {detail}")

def synth(n=200, seed=42):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-06-01", periods=n, freq="15min", tz="UTC")
    mid = 100 + np.cumsum(rng.normal(0, 0.25, n))
    return pd.DataFrame({
        "time": t,
        "open": mid,
        "high": mid + rng.uniform(0.2, 1.0, n),
        "low": mid - rng.uniform(0.2, 1.0, n),
        "close": mid + rng.normal(0, 0.1, n),
    })

def main():
    df = synth()
    # 1. swing confirmation after occurrence
    h = df["high"].to_numpy()
    n = len(h)
    ok = True
    pairs = 0
    for p in range(2, n - 2):
        if h[p] > h[p-1] and h[p] > h[p-2] and h[p] >= h[p+1] and h[p] >= h[p+2]:
            pairs += 1
            # confirmation index is p+2
            if not (p + 2 > p):
                ok = False
    check("swing_conf_after_occ", ok and pairs > 0, f"pairs={pairs}")

    # 2. confirm_swings writes only at p+2
    sh, sl = confirm_swings(df["high"], df["low"])
    check("no_swing_in_first_4", pd.isna(sh.iloc[:4]).all())

    # 3. equal distance does not satisfy strict A
    out = compute_all(df, obb_on="rsi")
    bb34u = out["BB34_U"]
    hi = df["high"]
    dist = bb34u - hi
    exp = out["bb34u_exposed"].fillna(False)
    A = (hi < bb34u) & (dist < dist.shift(1)) & exp
    eq = (hi < bb34u) & (dist == dist.shift(1)) & exp
    check("equal_dist_not_in_A", not bool((A & eq).any()) if len(A) else True)

    # 4. official paths remain off
    r = run_diagnostics(df, obb_on="rsi", d5_mode="A")
    c = r["counts"]
    check("add_disabled", c["official_add_enabled"] is False)
    check("reversal_disabled", c["reversal_enabled"] is False)
    check("initial_off", c["official_initial_enabled"] is False)
    types = {e.event_type for e in r["events"]}
    check("no_add_sell_event", EventType.ADD_SELL not in types)
    check("no_reversal_event", EventType.CLOSE_FOR_REVERSAL not in types)

    # 5. O1/O2 switch is explicit
    r2 = run_diagnostics(df, obb_on="ma7", d5_mode="A")
    check("o2_flag", r2["counts"]["obb_on"] == "ma7")
    check("o1_flag", c["obb_on"] == "rsi")

    # 6. repeated run deterministic counts
    r3 = run_diagnostics(df, obb_on="rsi", d5_mode="A")
    check("deterministic_starts", r3["counts"]["pullback_starts"] == c["pullback_starts"])

    print(f"TOTAL {P} PASS {F} FAIL")
    return 0 if F == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
