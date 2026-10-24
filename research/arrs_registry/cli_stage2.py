#!/usr/bin/env python3
"""ARRS Stage 2 offline CLI — never places orders."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "stage2"))

from stage2.data import load_bid_ask_csv, validate_bid_ask, dataset_hash
from stage2.simulator import TradeManagementTemplate
from stage2.runner import run_evaluation
from stage2.walkforward import PartitionSpec


def demo_signal_fn(df: pd.DataFrame) -> pd.Series:
    """Deterministic fixture signal: alternate every 40 bars after warm-up — software test only."""
    n = len(df)
    s = np.zeros(n)
    for i in range(30, n - 5, 40):
        s[i] = 1 if (i // 40) % 2 == 0 else -1
    return pd.Series(s)


def main():
    p = argparse.ArgumentParser(description="ARRS Stage 2 offline evaluator")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate-dataset")
    v.add_argument("path")
    e = sub.add_parser("evaluate")
    e.add_argument("path")
    e.add_argument("--candidate-id", default="CAND-STAGE2-DEMO")
    e.add_argument("--candidate-version", default="1")
    e.add_argument("--stop-atr", type=float, default=1.5)
    e.add_argument("--max-hold", type=int, default=48)
    e.add_argument("--commission", type=float, default=0.0)
    e.add_argument("--slippage", type=float, default=0.0)
    e.add_argument("--out", default=None)
    a = p.parse_args()
    if a.cmd == "validate-dataset":
        df = load_bid_ask_csv(a.path)
        rep = validate_bid_ask(df)
        rep["dataset_hash"] = dataset_hash(a.path)
        print(json.dumps(rep, indent=2))
        sys.exit(0 if rep["ok"] else 1)
    if a.cmd == "evaluate":
        tm = TradeManagementTemplate(
            template_id="TM_ATR_STOP_V1", version="1",
            initial_stop_atr=a.stop_atr, max_hold_bars=a.max_hold,
        )
        res = run_evaluation(
            dataset_path=a.path,
            signal_fn=demo_signal_fn,
            candidate_id=a.candidate_id,
            candidate_version=a.candidate_version,
            tm=tm,
            commission_per_side=a.commission,
            slippage=a.slippage,
            partition=PartitionSpec(),
        )
        text = json.dumps(res, indent=2, default=str)
        if a.out:
            Path(a.out).write_text(text)
        print(text)
        print("execution_authorized=", res.get("execution_authorized"), file=sys.stderr)


if __name__ == "__main__":
    main()
