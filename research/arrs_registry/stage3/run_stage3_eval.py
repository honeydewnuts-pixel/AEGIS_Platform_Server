#!/usr/bin/env python3
"""Run preregistered Stage 3 candidates on Class A instruments."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "stage2"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from stage2.simulator import TradeManagementTemplate
from stage2.runner import run_evaluation
from stage2.walkforward import PartitionSpec
from signals import signal_inside_break, signal_range20_break

INV = Path(__file__).resolve().parent / "outputs" / "dataset_inventory.csv"
OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(exist_ok=True)

TM = TradeManagementTemplate(
    template_id="TM_ATR_STOP_V1", version="1",
    initial_stop_atr=1.5, max_hold_bars=48, take_profit_atr=None,
)

CANDIDATES = [
    {
        "candidate_id": "CAND-S3-INSIDE-BREAK-V1",
        "candidate_version": "1",
        "signal_fn": signal_inside_break,
    },
    {
        "candidate_id": "CAND-S3-RANGE20-BREAK-V1",
        "candidate_version": "1",
        "signal_fn": signal_range20_break,
    },
]


def main():
    inv = pd.read_csv(INV)
    class_a = inv[inv["eligible_bidask"] == True]
    # Evaluate all Class A FX (exclude if path missing)
    results = []
    for _, row in class_a.iterrows():
        path = row["path"]
        if not Path(path).exists():
            results.append({"symbol": row["symbol"], "status": "MISSING_FILE"})
            continue
        for cand in CANDIDATES:
            print(f"EVAL {row['symbol']} {cand['candidate_id']}", flush=True)
            try:
                res = run_evaluation(
                    dataset_path=path,
                    signal_fn=cand["signal_fn"],
                    candidate_id=cand["candidate_id"],
                    candidate_version=cand["candidate_version"],
                    tm=TM,
                    partition=PartitionSpec(),
                    commission_per_side=0.0,
                    slippage=0.0,
                    n_variants_tested=2,
                    min_rows=500,
                )
                entry = {
                    "symbol": row["symbol"],
                    "data_class": row["data_class"],
                    "dataset_sha256": row["sha256"],
                    "candidate_id": cand["candidate_id"],
                    "status": res.get("status"),
                    "execution_authorized": res.get("execution_authorized"),
                    "production_authorized": res.get("production_authorized"),
                    "evaluation_id": res.get("evaluation_id"),
                    "config_hash": res.get("config_hash"),
                    "dataset_hash_runtime": res.get("dataset_hash"),
                    "full_trades": res.get("n_full_trades"),
                    "full_pf": (res.get("full_sample_metrics") or {}).get("pf"),
                    "full_net": (res.get("full_sample_metrics") or {}).get("net"),
                    "val_trades": (res.get("walk_forward") or {}).get("partitions", {}).get("val", {}).get("trades"),
                    "val_pf": (res.get("walk_forward") or {}).get("partitions", {}).get("val", {}).get("pf"),
                    "test_trades": (res.get("walk_forward") or {}).get("partitions", {}).get("test", {}).get("trades"),
                    "test_pf": (res.get("walk_forward") or {}).get("partitions", {}).get("test", {}).get("pf"),
                    "gates_overall": (res.get("gates") or {}).get("overall"),
                    "data_ok": (res.get("data_report") or {}).get("ok"),
                }
                results.append(entry)
                # per-eval json
                outp = OUT / f"{row['symbol']}_{cand['candidate_id']}.json"
                # strip huge if any
                slim = {k: v for k, v in res.items()}
                outp.write_text(json.dumps(slim, indent=2, default=str))
                print("  ->", entry["status"], "val_pf", entry["val_pf"], "test_pf", entry["test_pf"], flush=True)
            except Exception as e:
                print("  ERR", e, flush=True)
                results.append({"symbol": row["symbol"], "candidate_id": cand["candidate_id"], "status": "ERROR", "error": str(e)})
            pd.DataFrame(results).to_csv(OUT / "stage3_results.csv", index=False)
    pd.DataFrame(results).to_csv(OUT / "stage3_results.csv", index=False)
    print("DONE", len(results), flush=True)


if __name__ == "__main__":
    main()
