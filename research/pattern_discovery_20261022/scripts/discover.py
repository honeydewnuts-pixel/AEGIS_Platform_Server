#!/usr/bin/env python3
"""Bounded data-driven pattern discovery — no conventional indicators as prerequisites."""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import load_ohlc, build_features, forward_labels

OUT = Path(__file__).resolve().parents[1] / "outputs"
INV = OUT / "dataset_inventory.csv"
HORIZONS = (3, 6, 12, 24, 48)
MIN_SUPPORT = 200  # min pattern occurrences in development

# Registered binary pattern definitions (interpretable, fixed before evaluation)
PATTERN_SPECS = [
    ("long_lower_wick", lambda f, i: f["lower_wick_frac"][i] > 0.6 and f["body_frac"][i] < 0.3),
    ("long_upper_wick", lambda f, i: f["upper_wick_frac"][i] > 0.6 and f["body_frac"][i] < 0.3),
    ("bull_engulf", lambda f, i: f["bull_engulf"][i] == 1),
    ("bear_engulf", lambda f, i: f["bear_engulf"][i] == 1),
    ("inside_bar", lambda f, i: f["inside"][i] == 1),
    ("outside_bar", lambda f, i: f["outside"][i] == 1),
    ("close_near_high", lambda f, i: f["close_loc"][i] > 0.8),
    ("close_near_low", lambda f, i: f["close_loc"][i] < 0.2),
    ("range_compression", lambda f, i: not np.isnan(f["range_vs_20"][i]) and f["range_vs_20"][i] < 0.5),
    ("range_expansion", lambda f, i: not np.isnan(f["range_vs_20"][i]) and f["range_vs_20"][i] > 2.0),
    ("consec_bull_3", lambda f, i: f["dir"][i] > 0 and f["consec_dir"][i] >= 2),
    ("consec_bear_3", lambda f, i: f["dir"][i] < 0 and f["consec_dir"][i] >= 2),
    ("break_20hi", lambda f, i: not np.isnan(f["dist_20hi"][i]) and f["dist_20hi"][i] > 0),
    ("break_20lo", lambda f, i: not np.isnan(f["dist_20lo"][i]) and f["dist_20lo"][i] < 0),
    ("london_open_hour", lambda f, i: f["hour"][i] in (7, 8)),
    ("ny_open_hour", lambda f, i: f["hour"][i] in (12, 13)),
    ("asian_hour", lambda f, i: f["hour"][i] in (0, 1, 2, 3)),
]

# Interaction patterns (bounded)
INTERACTIONS = [
    ("compress_then_expand_proxy", lambda f, i: (
        i >= 1 and not np.isnan(f["range_vs_20"][i - 1]) and f["range_vs_20"][i - 1] < 0.6
        and not np.isnan(f["range_vs_20"][i]) and f["range_vs_20"][i] > 1.5
    )),
    ("bull_engulf_after_compression", lambda f, i: (
        f["bull_engulf"][i] == 1 and not np.isnan(f["range_vs_20"][i]) and f["range_vs_20"][i] < 0.8
    )),
    ("bear_engulf_after_compression", lambda f, i: (
        f["bear_engulf"][i] == 1 and not np.isnan(f["range_vs_20"][i]) and f["range_vs_20"][i] < 0.8
    )),
    ("long_lower_wick_at_20lo", lambda f, i: (
        f["lower_wick_frac"][i] > 0.5 and not np.isnan(f["dist_20lo"][i]) and f["dist_20lo"][i] > -0.002
        and f["dist_20lo"][i] < 0.002
    )),
    ("long_upper_wick_at_20hi", lambda f, i: (
        f["upper_wick_frac"][i] > 0.5 and not np.isnan(f["dist_20hi"][i]) and abs(f["dist_20hi"][i]) < 0.002
    )),
]

ALL_PATTERNS = PATTERN_SPECS + INTERACTIONS

def split_idx(n):
    a, b = int(n * 0.60), int(n * 0.80)
    return (0, a), (a, b), (b, n)

def evaluate_pattern(mask, labels, lo, hi, horizon):
    """Mean forward return and hit rate on indices in [lo,hi) where mask True and label finite."""
    y = labels[f"fwd_ret_{horizon}"]
    idx = [i for i in range(lo, hi) if mask[i] and not np.isnan(y[i])]
    if not idx:
        return dict(n=0, mean_ret=None, hit_rate=None, median_ret=None)
    vals = y[idx]
    return dict(
        n=len(vals),
        mean_ret=float(np.mean(vals)),
        median_ret=float(np.median(vals)),
        hit_rate=float(np.mean(vals > 0)),
    )

def run_instrument(sym, path, dcls):
    bars = load_ohlc(path, dcls)
    f = build_features(bars)
    labels = forward_labels(bars["close"], HORIZONS)
    n = len(bars["close"])
    (d0, d1), (v0, v1), (t0, t1) = split_idx(n)
    results = []
    for name, pred in ALL_PATTERNS:
        mask = np.zeros(n, dtype=bool)
        for i in range(n):
            try:
                if pred(f, i):
                    mask[i] = True
            except Exception:
                pass
        for h in HORIZONS:
            dev = evaluate_pattern(mask, labels, d0, d1, h)
            val = evaluate_pattern(mask, labels, v0, v1, h)
            # predictive signal: |mean_ret| and consistency of sign on val
            results.append(dict(
                symbol=sym, data_class=dcls, pattern=name, horizon=h,
                dev_n=dev["n"], dev_mean=dev["mean_ret"], dev_hit=dev["hit_rate"],
                val_n=val["n"], val_mean=val["mean_ret"], val_hit=val["hit_rate"],
                same_sign=(
                    dev["mean_ret"] is not None and val["mean_ret"] is not None
                    and np.sign(dev["mean_ret"]) == np.sign(val["mean_ret"])
                    and abs(dev["mean_ret"]) > 0 and abs(val["mean_ret"]) > 0
                ),
                support_ok=dev["n"] >= MIN_SUPPORT,
            ))
    return results

def main():
    inv = pd.read_csv(INV)
    inv = inv[inv.eligible == True]
    all_rows = []
    n_patterns = len(ALL_PATTERNS)
    print(f"Registered patterns: {n_patterns}, horizons: {HORIZONS}, min_support: {MIN_SUPPORT}", flush=True)
    print(f"Search space size: {n_patterns * len(HORIZONS)} pattern-horizon pairs per instrument", flush=True)
    for _, row in inv.iterrows():
        print(f"=== {row.symbol} ({row.data_class}) ===", flush=True)
        try:
            rows = run_instrument(row.symbol, row.path, row.data_class)
            all_rows.extend(rows)
            # quick summary: patterns with support + same sign + val_n>=50
            surv = [r for r in rows if r["support_ok"] and r["same_sign"] and (r["val_n"] or 0) >= 50]
            print(f"  candidates with support+same_sign: {len(surv)}", flush=True)
        except Exception as e:
            print(f"  FAIL {e}", flush=True)
        pd.DataFrame(all_rows).to_csv(OUT / "pattern_outcomes.csv", index=False)

    df = pd.DataFrame(all_rows)
    # Survivors: support, same sign, val_n>=50, |val_mean| rank
    survivors = df[
        (df.support_ok == True) & (df.same_sign == True) & (df.val_n >= 50)
    ].copy()
    survivors["abs_val_mean"] = survivors["val_mean"].abs()
    survivors = survivors.sort_values("abs_val_mean", ascending=False)

    # Multiple-testing note: n_pairs * n_patterns * n_horizons tests
    n_tests = len(df)
    summary = dict(
        research_id="DATA_DRIVEN_PATTERN_DISCOVERY_20261022",
        production_authorized=False, execution_authorized=False,
        n_instruments=int(inv.shape[0]),
        n_registered_patterns=n_patterns,
        n_horizons=len(HORIZONS),
        min_support=MIN_SUPPORT,
        total_pattern_horizon_evals=n_tests,
        n_with_support=int(df.support_ok.sum()),
        n_same_sign_and_support=int(((df.support_ok) & (df.same_sign)).sum()),
        n_survivors_val50=int(len(survivors)),
        methods_run=["registered_binary_pattern_enumeration", "conditional_forward_return_analysis"],
        methods_not_run=["unrestricted_clustering", "deep_decision_trees", "sparse_regression_search"],
        multiple_testing_note=f"{n_tests} pattern-horizon-instrument evaluations; no naive p-values treated as confirmation",
        top_survivors=survivors.head(30).to_dict("records"),
        note="Pattern-level evidence only. No trading rulebook qualification. No cash PF.",
    )
    survivors.to_csv(OUT / "survivor_patterns.csv", index=False)
    (OUT / "discovery_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nTOTAL evals={n_tests} survivors(val_n>=50,same_sign,support)={len(survivors)}")
    print("TOP 10 by |val_mean|:")
    for _, r in survivors.head(10).iterrows():
        print(f"  {r.symbol:8} {r.pattern:30} h={r.horizon:2} val_n={r.val_n:5} val_mean={r.val_mean:.6f} hit={r.val_hit:.3f}")
    print("DONE")

if __name__ == "__main__":
    main()
