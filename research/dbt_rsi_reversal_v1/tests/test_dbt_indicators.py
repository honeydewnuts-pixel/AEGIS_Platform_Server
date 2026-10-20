#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from indicators import sma, rsi_wilder, bollinger, williams_r, compute_stack
from state_engine import find_rsi_swings, evolve_states, SWING_LEFT, SWING_RIGHT

P, F = 0, 0

def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1; print(f"[PASS] {name}")
    else:
        F += 1; print(f"[FAIL] {name} {detail}")

def test_sma():
    x = np.array([1., 2., 3., 4., 5.], float)
    y = sma(x, 3)
    check("sma_period3", abs(y[2] - 2.0) < 1e-12 and abs(y[4] - 4.0) < 1e-12, str(y))

def test_rsi_bounds():
    rng = np.random.default_rng(0)
    c = np.cumsum(rng.normal(0, 0.001, 200)) + 1.0
    r = rsi_wilder(c, 9)
    valid = r[~np.isnan(r)]
    check("rsi_in_0_100", valid.min() >= 0 and valid.max() <= 100, f"{valid.min()}-{valid.max()}")

def test_bb_on_rsi():
    c = np.linspace(1.0, 1.1, 100)
    ind = compute_stack(c, c + 0.001, c - 0.001)
    check("rbb_not_nan_late", not np.isnan(ind["RBB_U"][80]))
    check("rbb_order", ind["RBB_U"][80] >= ind["RBB_M"][80] >= ind["RBB_L"][80])

def test_wpr_bounds():
    h = np.array([1.1, 1.2, 1.15, 1.3, 1.25] * 20, float)
    l = h - 0.05
    c = (h + l) / 2
    w = williams_r(h, l, c, 14)
    valid = w[~np.isnan(w)]
    check("wpr_in_range", valid.min() >= -100 and valid.max() <= 0, f"{valid.min()}-{valid.max()}")

def test_swing_no_lookahead():
    rsi = np.array([50, 40, 30, 35, 40, 45, 50, 40, 30, 20, 25, 30], float)
    swings = find_rsi_swings(rsi, L=2, R=2)
    for ext, conf, kind in swings:
        check(f"confirm_after_extreme_{ext}", conf == ext + 2)
        check(f"confirm_in_bounds_{ext}", conf < len(rsi))

def test_state_warmup():
    c = np.ones(100)
    ind = compute_stack(c, c, c)
    st = evolve_states(ind)
    check("early_insufficient_or_neutral", st[0] in ("INSUFFICIENT_HISTORY", "NEUTRAL"))

def test_provisional_params():
    check("swing_L_is_2", SWING_LEFT == 2)
    check("swing_R_is_2", SWING_RIGHT == 2)

if __name__ == "__main__":
    test_sma(); test_rsi_bounds(); test_bb_on_rsi(); test_wpr_bounds()
    test_swing_no_lookahead(); test_state_warmup(); test_provisional_params()
    print(f"TOTAL {P} PASS {F} FAIL")
    sys.exit(0 if F == 0 else 1)
