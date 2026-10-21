#!/usr/bin/env python3
"""V7 Fixed Squeeze — all-instrument baseline + controlled single-family variants."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v7_engine import V7Params, load_bars, run_v7, split_60_20_20, pf, six_block_pf

OUT = Path(__file__).resolve().parents[1] / "outputs"
INV = OUT / "dataset_inventory.csv"

CANDIDATES = [
    V7Params(candidate_id="BASELINE"),
    V7Params(squeeze_pct=0.45, candidate_id="A1_sq045"),
    V7Params(squeeze_lookback=12, candidate_id="A2_lb12"),
    V7Params(squeeze_pct=0.45, squeeze_lookback=12, candidate_id="A3_sq045_lb12"),
    V7Params(breakout_lookback=6, candidate_id="B1_bo6"),
    V7Params(breakout_lookback=7, candidate_id="B2_bo7"),
    V7Params(pullback_lookback=4, candidate_id="C1_pb4"),
    V7Params(pullback_lookback=5, candidate_id="C2_pb5"),
    V7Params(atr_mult=1.05, candidate_id="D1_atr105"),
]

def eval_segment(trades, lo, hi):
    seg = [t for t in trades if lo <= t["entry_i"] < hi and t["exit_i"] < hi]
    nets = [t["net"] for t in seg]
    return dict(
        trades=len(seg),
        net_pf=pf(nets),
        gross_pf=pf([t["gross"] for t in seg]),
        expectancy=float(np.mean(nets)) if nets else None,
        sum_net=float(sum(nets)) if nets else 0.0,
    )

def gates(val):
    t = val["trades"]
    npf = val["net_pf"]
    blocks = val["blocks"]
    g1 = t is not None and t > 350
    g2 = npf is not None and npf != float("inf") and npf > 1.6
    finite = [b for b in blocks if b is not None and b != float("inf")]
    # blocks with no trades => fail gate 3
    g3 = len(finite) == 6 and min(finite) > 1.0 if len(finite) == 6 else False
    if any(b is None for b in blocks):
        g3 = False
    return g1, g2, g3, g1 and g2 and g3

def main():
    inv = pd.read_csv(INV)
    inv = inv[inv["eligible"] == True]
    results = []
    for _, row in inv.iterrows():
        sym, path, dcls = row["symbol"], row["path"], row["data_class"]
        print(f"\n==== {sym} ({dcls}) ====", flush=True)
        try:
            bars = load_bars(path, dcls)
        except Exception as e:
            print("  LOAD FAIL", e, flush=True)
            results.append(dict(symbol=sym, data_class=dcls, candidate="ALL", status="LOAD_FAIL", error=str(e)))
            continue
        n = len(bars["close"])
        (d0, d1), (v0, v1), (t0, t1) = split_60_20_20(n)
        for params in CANDIDATES:
            # BOTH directions combined for research; also track long/short counts
            trades, funnel = run_v7(bars, params, direction="BOTH")
            # filter to development for selection info
            dev = eval_segment(trades, d0, d1)
            val = eval_segment(trades, v0, v1)
            tst = eval_segment(trades, t0, t1)
            blocks = six_block_pf(trades, v0, v1)
            val["blocks"] = blocks
            g1, g2, g3, qual = gates(val)
            long_n = sum(1 for t in trades if t["side"] == "LONG" and v0 <= t["entry_i"] < v1)
            short_n = sum(1 for t in trades if t["side"] == "SHORT" and v0 <= t["entry_i"] < v1)
            rec = dict(
                symbol=sym, data_class=dcls, candidate=params.candidate_id,
                rows=n, dev_trades=dev["trades"], dev_net_pf=dev["net_pf"],
                val_trades=val["trades"], val_net_pf=val["net_pf"],
                val_long=long_n, val_short=short_n,
                block_pfs=";".join("" if b is None else f"{b:.3f}" if b != float("inf") else "inf" for b in blocks),
                min_block_pf=(min([b for b in blocks if b is not None and b != float("inf")])
                              if any(b is not None and b != float("inf") for b in blocks) else None),
                test_trades=tst["trades"], test_net_pf=tst["net_pf"],
                gate1_trades_gt350=g1, gate2_pf_gt16=g2, gate3_minblock_gt1=g3,
                qualifies=qual,
                funnel_entered=funnel["entered"],
                funnel_squeeze=funnel["squeeze"], funnel_vol=funnel["vol_exp"],
                funnel_breakout=funnel["breakout"], funnel_pullback=funnel["pullback"],
                funnel_trend=funnel["trend"], funnel_session=funnel["session"],
                note="Class B is OHLC proxy — not verified Bid/Ask execution" if dcls == "B_OHLC" else "",
            )
            results.append(rec)
            mark = "QUAL" if qual else "fail"
            print(
                f"  {params.candidate_id:16} val_trades={val['trades']:4} "
                f"val_pf={val['net_pf']} min_block={rec['min_block_pf']} {mark}",
                flush=True,
            )
        # checkpoint
        pd.DataFrame(results).to_csv(OUT / "all_instrument_results.csv", index=False)

    pd.DataFrame(results).to_csv(OUT / "all_instrument_results.csv", index=False)
    qual = [r for r in results if r.get("qualifies")]
    summary = dict(
        research_id="V7_FIXED_SQUEEZE_ALL_INSTRUMENTS",
        production_authorized=False, execution_authorized=False,
        n_result_rows=len(results),
        n_qualifying=len(qual),
        qualifying=qual,
        baseline_note=(
            "Original V7 Fixed Squeeze implementation/report for GBPUSD/XAUUSD "
            "was NOT found in repository. Engine implemented from frozen rule text in task. "
            "Baseline reproduction of prior published numbers is BLOCKED pending artifact recovery."
        ),
    )
    (OUT / "qualification_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== QUALIFYING ====", len(qual), flush=True)
    for q in qual:
        print(q["symbol"], q["candidate"], q["val_trades"], q["val_net_pf"], flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
