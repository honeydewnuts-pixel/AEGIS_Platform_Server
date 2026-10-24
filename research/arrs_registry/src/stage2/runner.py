"""End-to-end evaluation runner + ARRS registry integration."""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Any
import pandas as pd

from .data import load_bid_ask_csv, validate_bid_ask, dataset_hash
from .simulator import TradeManagementTemplate, simulate_trades
from .walkforward import walk_forward_evaluate, PartitionSpec, metrics_from_trades
from .gates import evaluate_gates, GatePolicy


def config_hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def run_evaluation(
    *,
    dataset_path: str,
    signals: pd.Series | None = None,
    signal_fn=None,
    candidate_id: str,
    candidate_version: str,
    tm: TradeManagementTemplate,
    partition: PartitionSpec | None = None,
    commission_per_side: float = 0.0,
    slippage: float = 0.0,
    n_variants_tested: int = 1,
    registry=None,
    min_rows: int = 50,
) -> dict[str, Any]:
    path = Path(dataset_path)
    dhash = dataset_hash(path)
    df = load_bid_ask_csv(path)
    data_report = validate_bid_ask(df, min_rows=min_rows)
    cfg = {
        "candidate_id": candidate_id,
        "candidate_version": candidate_version,
        "tm": tm.to_dict(),
        "commission_per_side": commission_per_side,
        "slippage": slippage,
        "partition": (partition or PartitionSpec()).__dict__,
        "dataset_path": str(path),
        "dataset_hash": dhash,
    }
    ch = config_hash(cfg)
    eval_id = f"EVAL-{candidate_id}-{candidate_version}-{ch[:12]}"

    result: dict[str, Any] = {
        "evaluation_id": eval_id,
        "config_hash": ch,
        "dataset_hash": dhash,
        "data_report": data_report,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "production_authorized": False,
        "execution_authorized": False,
        "evaluator_version": "ARRS_STAGE2_V1",
    }

    if not data_report["ok"]:
        result["status"] = "INSUFFICIENT_DATA"
        result["gates"] = evaluate_gates(
            data_report=data_report, wf={"partitions": {}}, tm_defined=True,
            n_variants_tested=n_variants_tested,
        )
        return result

    if signals is None:
        if signal_fn is None:
            result["status"] = "INSUFFICIENT_EVIDENCE"
            result["detail"] = "no signals or signal_fn"
            return result
        signals = signal_fn(df)

    if len(signals) != len(df):
        raise ValueError("signals length must match dataset")

    wf = walk_forward_evaluate(
        df, signals, tm, partition=partition,
        commission_per_side=commission_per_side, slippage=slippage,
    )
    result["walk_forward"] = wf
    gates = evaluate_gates(
        data_report=data_report, wf=wf, tm_defined=True,
        n_variants_tested=n_variants_tested,
    )
    result["gates"] = gates
    result["status"] = gates["overall"]
    # Full-sample descriptive (not qualification)
    full_tr = simulate_trades(df, signals, tm=tm, commission_per_side=commission_per_side, slippage=slippage)
    result["full_sample_metrics"] = metrics_from_trades(full_tr)
    result["n_full_trades"] = len(full_tr)

    if registry is not None:
        try:
            if candidate_id not in {c.get("candidate_id") for c in registry.list_candidates()}:
                # ensure experiment exists lightly
                pass
            registry.add_evaluation({
                "evaluation_id": eval_id,
                "candidate_id": candidate_id,
                "status": result["status"] if result["status"] in ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "NOT_RUN") else "INSUFFICIENT_EVIDENCE",
                "config_hash": ch,
                "dataset_hash": dhash,
                "gates_overall": gates["overall"],
                "production_authorized": False,
                "execution_authorized": False,
                "note": "Stage2 offline evaluation",
            })
        except ValueError as e:
            result["registry_note"] = str(e)

    return result
