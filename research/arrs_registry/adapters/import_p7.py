"""Read-only idempotent import of P7 Track A findings."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from registry import ArrsRegistry  # noqa: E402

P7 = ROOT / "p7_price_action_extension"
OUT = P7 / "outputs"
IMPORT_KEY = "p7_price_action_extension_20261022_v1"


def file_sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def import_p7(reg: ArrsRegistry, *, source_commit: str = "c872ab2") -> dict:
    if reg.has_import(IMPORT_KEY):
        return {"status": "already_imported", "import_key": IMPORT_KEY}

    summary = {}
    sp = OUT / "evaluation_summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text())

    artifacts = {
        "evaluation_summary.json": file_sha(sp),
        "forward_associations.csv": file_sha(OUT / "forward_associations.csv"),
        "hypothesis_occurrences.csv": file_sha(OUT / "hypothesis_occurrences.csv"),
        "PREREGISTRATION.md": file_sha(P7 / "docs" / "PREREGISTRATION.md"),
        "FINAL_REPORT.md": file_sha(P7 / "docs" / "FINAL_REPORT.md"),
        "model_sha256": summary.get("model_sha256"),
        "gold_sha256": summary.get("gold_sha256"),
    }

    exp = reg.register_experiment({
        "experiment_id": "EXP-P7-TRACKA-20261022",
        "name": "P7-L1/L2 Track A H1 XAUUSD association",
        "objective": "Test frozen P7 long-tree leaf conditions as structural hypotheses",
        "status": "COMPLETED_EXPLORATORY",
        "source_branch": "research/p7-price-action-extension-20261022",
        "source_commit": source_commit,
        "dataset_class_policy": "XAUUSD Class B OHLC for association; not Bid/Ask executable claim",
        "artifact_sha256": artifacts,
        "gold_sha_matches_training": summary.get("gold_sha_matches_p7_training"),
        "limitations": [
            "in_sample_relative_to_original_model_fit",
            "final_20pct_EXPOSED",
            "no_cash_trade_management_in_this_phase",
            "GBPUSD_training_hash_unverified",
        ],
        "production_authorized": False,
        "execution_authorized": False,
    })

    for hid, state, reason, status in (
        ("P7-L1", "VALIDATED", "exploratory_promising_unconfirmed", "INSUFFICIENT_EVIDENCE"),
        ("P7-L2", "REJECTED", "exploratory_inconclusive", "INSUFFICIENT_EVIDENCE"),
    ):
        # VALIDATED here means research association recorded — still no execution auth
        # P7-L1: use SCREENED then VALIDATED with evidence note of unconfirmed
        cid = f"CAND-{hid}-TRACKA-20261022"
        if hid == "P7-L1":
            reg.register_candidate({
                "candidate_id": cid,
                "experiment_id": exp["experiment_id"],
                "definition_version": "1",
                "lifecycle_state": "DISCOVERED",
                "hypothesis_id": hid,
                "trade_management_status": "NOT_DEFINED",
                "status_label": "EXPLORATORY_PROMISING_UNCONFIRMED",
                "production_authorized": False,
                "execution_authorized": False,
            })
            reg.transition_candidate(cid, "SCREENED", evidence="occurrence_counts_recorded", actor="import_p7")
            reg.transition_candidate(
                cid, "VALIDATED",
                evidence="val_mean_price_exceeds_0.42_cost_but_unconfirmed_in_sample",
                actor="import_p7",
            )
        else:
            reg.register_candidate({
                "candidate_id": cid,
                "experiment_id": exp["experiment_id"],
                "definition_version": "1",
                "lifecycle_state": "DISCOVERED",
                "hypothesis_id": hid,
                "trade_management_status": "NOT_DEFINED",
                "status_label": "EXPLORATORY_INCONCLUSIVE",
                "production_authorized": False,
                "execution_authorized": False,
            })
            reg.transition_candidate(cid, "SCREENED", evidence="occurrence_counts_recorded", actor="import_p7")
            reg.transition_candidate(cid, "REJECTED", evidence=reason, actor="import_p7")

        reg.add_evaluation({
            "evaluation_id": f"EVAL-{hid}-TRACKA-20261022",
            "candidate_id": cid,
            "status": status,
            "note": "Association layer only; independent confirmation required",
            "production_authorized": False,
            "execution_authorized": False,
        })

    reg.mark_import(IMPORT_KEY, {"source_commit": source_commit, "artifacts": artifacts})
    return {"status": "imported", "experiment_id": exp["experiment_id"]}
