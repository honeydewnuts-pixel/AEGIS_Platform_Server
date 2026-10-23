"""Read-only idempotent import of data-driven pattern discovery evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from registry import ArrsRegistry  # noqa: E402

DISC = ROOT / "pattern_discovery_20261022"
OUT = DISC / "outputs"
DOCS = DISC / "docs"

IMPORT_KEY = "pattern_discovery_20261022_v1"


def file_sha(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def import_discovery(reg: ArrsRegistry, *, source_commit: str = "0ba218a", remote_tip: str = "9168b74") -> dict:
    if reg.has_import(IMPORT_KEY):
        return {"status": "already_imported", "import_key": IMPORT_KEY}

    summary_path = OUT / "discovery_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    artifacts = {
        "discovery_summary.json": file_sha(summary_path),
        "pattern_outcomes.csv": file_sha(OUT / "pattern_outcomes.csv"),
        "survivor_patterns.csv": file_sha(OUT / "survivor_patterns.csv"),
        "mfe_mae_cost.csv": file_sha(OUT / "mfe_mae_cost.csv"),
        "dataset_inventory.csv": file_sha(OUT / "dataset_inventory.csv"),
        "FINAL_REPORT.md": file_sha(DOCS / "FINAL_REPORT.md"),
        "CANDIDATE_FREEZE.md": file_sha(DOCS / "CANDIDATE_FREEZE.md"),
    }

    exp = reg.register_experiment({
        "experiment_id": "EXP-PATTERN-DISCOVERY-20261022",
        "name": "Data-driven pattern discovery 24 instruments",
        "objective": "Enumerate price-structure patterns; assess materiality after costs",
        "hypothesis": "Registered binary candle/range/session patterns have cost-aware forward edge",
        "status": "COMPLETED_NEGATIVE",
        "source_branch": "research/data-driven-pattern-discovery-20261022",
        "source_commit": source_commit,
        "remote_tip_at_assessment": remote_tip,
        "reconciliation_note": (
            "Local authoritative artifacts include MFE commit 0ba218a; "
            "remote branch tip was 9168b74 (parent of MFE work). Both recorded."
        ),
        "dataset_class_policy": "Class A Bid/Ask vs Class B OHLC separated; Class B not executable proof",
        "n_instruments": summary.get("n_instruments", 24),
        "n_patterns": summary.get("n_registered_patterns", 22),
        "n_evals": summary.get("total_pattern_horizon_evals", 2640),
        "n_soft_survivors": summary.get("n_survivors_val50"),
        "hard_materiality_passers": 0,
        "rulebooks_produced": 0,
        "artifact_sha256": artifacts,
        "limitations": [
            "final_20pct_EXPOSED",
            "multiple_testing_2640",
            "MFE_approx_MAE_no_net_edge",
            "no_trade_management_rulebook",
        ],
        "production_authorized": False,
        "execution_authorized": False,
        "disposition": "NO_QUALIFIED_RULEBOOK",
    })

    cand = reg.register_candidate({
        "candidate_id": "CAND-PD-WAVE-NEGATIVE-20261022",
        "experiment_id": exp["experiment_id"],
        "definition_version": "1",
        "lifecycle_state": "REJECTED",
        "description": "Aggregate discovery wave — no hard materiality passers",
        "long_short": "BOTH_EVALUATED",
        "trade_management": None,
        "trade_management_status": "NOT_DEFINED",
        "rejection_reason": "hard_materiality_gate_failed_zero_passers",
        "production_authorized": False,
        "execution_authorized": False,
    })

    reg.add_evaluation({
        "evaluation_id": "EVAL-PD-WAVE-20261022",
        "candidate_id": cand["candidate_id"],
        "status": "FAIL",
        "gate": "hard_materiality_abs_mean_gt_10bps_and_hit_gt_0.55",
        "passers": 0,
        "note": "Imported historical result; not re-run",
        "production_authorized": False,
        "execution_authorized": False,
    })

    reg.mark_import(IMPORT_KEY, {
        "source_commit": source_commit,
        "remote_tip": remote_tip,
        "artifacts": artifacts,
        "disposition": "NO_QUALIFIED_RULEBOOK",
    })
    return {"status": "imported", "experiment_id": exp["experiment_id"], "candidate_id": cand["candidate_id"]}
