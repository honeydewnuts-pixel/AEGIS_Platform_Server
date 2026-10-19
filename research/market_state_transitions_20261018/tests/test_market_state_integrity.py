#!/usr/bin/env python3
"""Dedicated integrity tests for market-state transitions study."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# Import analysis helpers
from run_market_state_transitions import (
    rolling_rv, past_percentiles, classify, thin_idx, abs_disp,
    bootstrap_mean_diff, LOOKBACK, H_STAR, THIN, WARM, N_BOOT, SEED,
)

PASSES = 0
FAILS = 0


def check(name, cond, detail=""):
    global PASSES, FAILS
    if cond:
        PASSES += 1
        print(f"[PASS] {name}")
    else:
        FAILS += 1
        print(f"[FAIL] {name} — {detail}")


def test_prereg_hash():
    prereg = (ROOT / "docs/AEGIS_MARKET_STATE_TRANSITIONS_PREREGISTRATION.md").read_bytes()
    h = hashlib.sha256(prereg).hexdigest()
    stored = (OUT / "preregistration_hash.txt").read_text().split()[0]
    check("prereg_hash_match", h == stored, f"{h[:16]} vs {stored[:16]}")


def test_materiality_count_reconciliation():
    s = json.loads((OUT / "market_state_summary.json").read_text())
    df = pd.read_csv(OUT / "instrument_state_summary.csv")
    n_mat = int((df["materiality"] >= 1).sum())
    n_ci = int(((df["ci_lo"] > 0) | (df["ci_hi"] < 0)).sum())
    n_same = int(df["same_sign"].sum())
    check("mat_ge1_equals_summary", n_mat == s["n_mat_ge1"], f"{n_mat} vs {s['n_mat_ge1']}")
    check("ci_excl_equals_summary", n_ci == s["n_ci_excludes_0"], f"{n_ci} vs {s['n_ci_excludes_0']}")
    check("same_sign_equals_summary", n_same == s["n_same_sign_stability"], f"{n_same} vs {s['n_same_sign_stability']}")
    check("mat_count_not_exceed_pairs", n_mat <= s["n_pairs"], f"{n_mat} > {s['n_pairs']}")
    check("no_15_over_13_bug", n_mat <= 13 and s["n_mat_ge1"] <= 13, "aggregate > denominator")


def test_rolling_rv_past_only():
    bc = np.array([1.0, 1.1, 1.0, 1.2, 1.15, 1.3, 1.25, 1.4] + [1.0] * 30, float)
    rv, disp = rolling_rv(bc)
    # rv at i should only use disp from i-LOOKBACK..i-1
    i = LOOKBACK + 5
    expected = np.mean(disp[i - LOOKBACK:i])
    check("rv_matches_past_window", abs(rv[i] - expected) < 1e-12, f"{rv[i]} vs {expected}")
    check("rv_nan_before_warm", np.isnan(rv[LOOKBACK]), "should be nan at LOOKBACK")


def test_prefix_invariance_synthetic():
    """Appending future bars must not change earlier state labels."""
    rng = np.random.default_rng(0)
    n = 800
    bc = np.cumsum(rng.normal(0, 0.0001, n)) + 1.0
    dow = np.array([i % 7 for i in range(n)])
    rv, _ = rolling_rv(bc)
    # Full
    p20a, p33a, p67a, p80a = past_percentiles(rv, dow, n)
    states_full = classify(rv, p20a, p33a, p67a, p80a, n)
    # Prefix
    prefix = 600
    p20b, p33b, p67b, p80b = past_percentiles(rv, dow, prefix)
    states_pref = classify(rv, p20b, p33b, p67b, p80b, prefix)
    # Compare elevated flags where both defined (after warm)
    start = WARM + LOOKBACK + 50
    ok = True
    for i in range(start, prefix):
        if states_full["ELEVATED"][i] != states_pref["ELEVATED"][i]:
            # Allow mismatch only if percentile was nan in one
            if not (np.isnan(p80a[i]) or np.isnan(p80b[i])):
                ok = False
                break
    check("prefix_invariance_elevated", ok, f"mismatch near i={i if not ok else 'n/a'}")


def test_outcome_alignment():
    bc = np.arange(100, dtype=float)
    idx = np.array([10, 20, 50])
    out = abs_disp(bc, idx, H_STAR)
    # abs(bc[i+12]-bc[i]) = 12 for arithmetic sequence
    check("H_star_is_12", H_STAR == 12, str(H_STAR))
    check("abs_disp_forward", abs(out[0] - 12.0) < 1e-9, str(out[0]))
    # end of series
    out2 = abs_disp(bc, np.array([95]), H_STAR)
    check("horizon_unavailable_is_nan", np.isnan(out2[0]), str(out2[0]))


def test_thin_independence():
    mask = np.zeros(100, dtype=bool)
    mask[::3] = True
    idx = thin_idx(mask, step=12)
    if len(idx) >= 2:
        gaps = np.diff(idx)
        check("thin_min_gap", gaps.min() >= 12, str(gaps.min()))
    else:
        check("thin_min_gap", True)


def test_bootstrap_reproducible():
    a = np.random.default_rng(1).normal(0.001, 0.0005, 200)
    b = np.random.default_rng(2).normal(0.0008, 0.0005, 200)
    d1, ci1, _, _ = bootstrap_mean_diff(a, b, n_boot=100, seed=SEED)
    d2, ci2, _, _ = bootstrap_mean_diff(a, b, n_boot=100, seed=SEED)
    check("bootstrap_seed_repro_diff", d1 == d2, f"{d1} vs {d2}")
    check("bootstrap_seed_repro_ci", ci1 == ci2, f"{ci1} vs {ci2}")
    check("N_BOOT_is_1000", N_BOOT == 1000, str(N_BOOT))


def test_classify_boundaries():
    n = 50
    rv = np.full(n, 0.5)
    p20 = np.full(n, 0.3)
    p33 = np.full(n, 0.4)
    p67 = np.full(n, 0.6)
    p80 = np.full(n, 0.7)
    rv[10] = 0.2   # quiet
    rv[11] = 0.5   # ordinary
    rv[12] = 0.8   # elevated
    st = classify(rv, p20, p33, p67, p80, n)
    check("quiet_boundary", st["QUIET"][10] and not st["ELEVATED"][10])
    check("ordinary_boundary", st["ORDINARY"][11])
    check("elevated_boundary", st["ELEVATED"][12] and not st["QUIET"][12])
    # Q2A: quiet then elevated
    st2 = classify(rv, p20, p33, p67, p80, n)
    # force transition at 13
    rv[13] = 0.2
    rv[14] = 0.9
    st3 = classify(rv, p20, p33, p67, p80, n)
    check("q2a_transition", st3["Q2A"][14], "expected Q2A at 14")


def test_dataset_manifest_present():
    m = OUT / "dataset_manifest.csv"
    check("manifest_exists", m.exists())
    if m.exists():
        df = pd.read_csv(m)
        check("manifest_13_rows", len(df) == 13, str(len(df)))
        check("manifest_has_sha", "sha256" in df.columns)


def main():
    print("=== Market-state integrity tests ===")
    test_prereg_hash()
    test_materiality_count_reconciliation()
    test_rolling_rv_past_only()
    test_prefix_invariance_synthetic()
    test_outcome_alignment()
    test_thin_independence()
    test_bootstrap_reproducible()
    test_classify_boundaries()
    test_dataset_manifest_present()
    print(f"\nTOTAL: {PASSES} PASS, {FAILS} FAIL")
    return 0 if FAILS == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
