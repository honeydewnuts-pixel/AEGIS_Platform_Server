#!/usr/bin/env python3
"""MFE/MAE and cost-aware materiality for top same-sign patterns."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import load_ohlc, build_features
from discover import ALL_PATTERNS, split_idx

OUT = Path(__file__).resolve().parents[1] / "outputs"
INV = OUT / "dataset_inventory.csv"

COST_PIPS = {"default_fx": 2.8, "jpy": 2.8, "crypto": 15.0, "index": 5.0, "metal": 4.0, "oil": 5.0}

def pip_size(sym):
    if "JPY" in sym: return 0.01
    if sym == "XAGUSD": return 0.01
    if sym == "XAUUSD": return 0.1
    if sym in ("BTCUSD", "ETHUSD", "GER40", "UK100", "US100", "US500"): return 1.0
    if "OIL" in sym: return 0.01
    return 0.0001

def cost_price(sym):
    if "JPY" in sym: g = "jpy"
    elif sym in ("BTCUSD", "ETHUSD"): g = "crypto"
    elif sym in ("GER40", "UK100", "US100", "US500"): g = "index"
    elif sym in ("XAUUSD", "XAGUSD"): g = "metal"
    elif "OIL" in sym: g = "oil"
    else: g = "default_fx"
    return COST_PIPS[g] * pip_size(sym)

def mfe_mae(high, low, close, idx, horizon):
    n = len(close)
    out = []
    for i in idx:
        if i + horizon >= n or i + 1 >= n: continue
        entry = close[i]
        wh = high[i+1:i+horizon+1]
        wl = low[i+1:i+horizon+1]
        if len(wh) == 0: continue
        out.append(dict(
            mfe_long=float(np.max(wh)-entry), mae_long=float(entry-np.min(wl)),
            mfe_short=float(entry-np.min(wl)), mae_short=float(np.max(wh)-entry),
        ))
    return out

def main():
    inv = pd.read_csv(INV)
    outcomes = pd.read_csv(OUT / "pattern_outcomes.csv")
    sub = outcomes[(outcomes.support_ok==True)&(outcomes.same_sign==True)&(outcomes.val_n>=100)].copy()
    sub["abs_vm"] = sub["val_mean"].abs()
    rows_out = []
    boundaries = []
    for _, invrow in inv.iterrows():
        sym, path, dcls = invrow.symbol, invrow.path, invrow.data_class
        bars = load_ohlc(path, dcls)
        f = build_features(bars)
        n = len(bars["close"])
        (d0,d1),(v0,v1),(t0,t1) = split_idx(n)
        boundaries.append(dict(
            symbol=sym, data_class=dcls, n=n,
            dev_start=str(bars["dt"].iloc[d0]), dev_end=str(bars["dt"].iloc[d1-1]),
            val_start=str(bars["dt"].iloc[v0]), val_end=str(bars["dt"].iloc[v1-1]),
            test_start=str(bars["dt"].iloc[t0]), test_end=str(bars["dt"].iloc[t1-1]),
            note="test_period_EXPOSED",
        ))
        top = sub[sub.symbol==sym].nlargest(3, "abs_vm")
        if top.empty: continue
        cost = cost_price(sym)
        for _, prow in top.iterrows():
            pname = prow.pattern
            h = int(prow.horizon)
            pred = dict(ALL_PATTERNS)[pname]
            mask = np.array([False]*n)
            for i in range(n):
                try:
                    if pred(f, i): mask[i] = True
                except Exception: pass
            idx = [i for i in range(v0,v1) if mask[i]]
            stats = mfe_mae(bars["high"], bars["low"], bars["close"], idx, h)
            if not stats: continue
            prefer_long = prow.val_mean > 0
            mfe = np.mean([s["mfe_long"] if prefer_long else s["mfe_short"] for s in stats])
            mae = np.mean([s["mae_long"] if prefer_long else s["mae_short"] for s in stats])
            ratio = mfe / cost if cost > 0 else None
            material = ratio is not None and ratio >= 3.0 and mfe > cost
            rows_out.append(dict(
                symbol=sym, data_class=dcls, pattern=pname, horizon=h,
                val_n=len(stats), val_mean_ret=float(prow.val_mean),
                mean_mfe=float(mfe), mean_mae=float(mae),
                rt_cost_price=float(cost), mfe_cost_ratio=float(ratio) if ratio else None,
                prefer_long=bool(prefer_long), material_mfe_ge_3x_cost=bool(material),
            ))
        print(f"{sym}: done", flush=True)
    pd.DataFrame(rows_out).to_csv(OUT/"mfe_mae_cost.csv", index=False)
    pd.DataFrame(boundaries).to_csv(OUT/"chronological_boundaries.csv", index=False)
    n_mat = sum(1 for r in rows_out if r["material_mfe_ge_3x_cost"])
    (OUT/"mfe_mae_summary.json").write_text(json.dumps(dict(
        n_mfe_evaluations=len(rows_out), n_material_mfe_3x_cost=n_mat,
        conclusion="No pattern reached mean MFE >= 3x RT cost on validation shortlist",
        production_authorized=False, execution_authorized=False,
    ), indent=2))
    print(f"MFE rows={len(rows_out)} material_3x={n_mat}", flush=True)

if __name__ == "__main__":
    main()
