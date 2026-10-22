#!/usr/bin/env python3
"""Evaluate P7-L1 and P7-L2 on XAUUSD H1 (Track A) — association layer only."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7_features import load_ohlc, hourly, features, events_p7_l1, events_p7_l2

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)
GOLD = Path("/home/workdir/artifacts/AEGIS_ALT_CSV/XAUUSD_M5_5Y.csv")
HORIZONS = (1, 2, 4, 8)  # H1 bars
COST = 0.42  # SOURCE_REPORTED XAU RT cost price units

def split60(n):
    a, b = int(n * 0.60), int(n * 0.80)
    return (0, a), (a, b), (b, n)

def eval_mask(close, mask, lo, hi, h, nonoverlap=False):
    idx = [i for i in range(lo, hi) if mask.iloc[i] and i + h < len(close)]
    if nonoverlap:
        filtered = []
        next_ok = 0
        for i in idx:
            if i >= next_ok:
                filtered.append(i)
                next_ok = i + h
        idx = filtered
    if not idx:
        return dict(n=0, mean=None, median=None, hit=None)
    rets = [(close[i + h] - close[i]) / close[i] for i in idx]
    # also price delta
    deltas = [close[i + h] - close[i] for i in idx]
    return dict(
        n=len(rets),
        mean=float(np.mean(rets)),
        median=float(np.median(rets)),
        hit=float(np.mean(np.array(rets) > 0)),
        mean_price=float(np.mean(deltas)),
        median_price=float(np.median(deltas)),
    )

def main():
    raw = GOLD.read_bytes()
    hsh = hashlib.sha256(raw).hexdigest()
    d = load_ohlc(str(GOLD))
    h = hourly(d)
    f = features(h)
    close = h["close"].to_numpy()
    m1 = events_p7_l1(f)
    m2 = events_p7_l2(f)
    n = len(h)
    (d0, d1), (v0, v1), (t0, t1) = split60(n)

    rows = []
    for name, mask in (("P7-L1", m1), ("P7-L2", m2)):
        for hzn in HORIZONS:
            for segment, lo, hi in (("dev", d0, d1), ("val", v0, v1), ("test_EXPOSED", t0, t1)):
                for nov in (False, True):
                    r = eval_mask(close, mask, lo, hi, hzn, nonoverlap=nov)
                    rows.append(dict(
                        hypothesis=name, horizon_h1=hzn, segment=segment,
                        nonoverlap=nov, **r,
                        material_price_vs_cost=(
                            r["mean_price"] is not None and abs(r["mean_price"]) > COST and r["n"] >= 50
                        ),
                    ))
        print(name, "raw events", int(mask.sum()), "complete bars", int(h.complete.sum()), flush=True)

    pd.DataFrame(rows).to_csv(OUT / "forward_associations.csv", index=False)
    # occurrence counts
    occ = []
    for name, mask in (("P7-L1", m1), ("P7-L2", m2)):
        occ.append(dict(
            hypothesis=name,
            total_events=int(mask.sum()),
            dev_events=int(mask.iloc[d0:d1].sum()),
            val_events=int(mask.iloc[v0:v1].sum()),
            test_events=int(mask.iloc[t0:t1].sum()),
            complete_h1=int(h.complete.sum()),
            n_h1=n,
        ))
    pd.DataFrame(occ).to_csv(OUT / "hypothesis_occurrences.csv", index=False)

    summary = dict(
        research_id="P7_PRICE_ACTION_EXTENSION_20261022",
        production_authorized=False,
        execution_authorized=False,
        track="A_H1_XAUUSD",
        gold_sha256=hsh,
        gold_sha_matches_p7_training=(hsh == "88e004253d0b879d4e829601e9b228cfa7d4d5afcc25a0dbf4537ba6ef97517c"),
        model_sha256="18380c1ee7b1f6f0a5febb55c5e88e872abdd3c45f92edbec671a21d06cbe8fa",
        cost_rt_price=COST,
        prereg_commit="96ab77d",
        final_20_exposed=True,
        cash_pf_not_computed="no trade-management model registered",
        occurrences=occ,
        note="Association layer only; in-sample historical structure",
    )
    (OUT / "evaluation_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print("DONE")

if __name__ == "__main__":
    main()
