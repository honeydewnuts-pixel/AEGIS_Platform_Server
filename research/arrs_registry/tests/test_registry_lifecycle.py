#!/usr/bin/env python3
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from registry import ArrsRegistry
from lifecycle import LifecycleError, transition

P = F = 0

def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1
        print(f"[PASS] {name}")
    else:
        F += 1
        print(f"[FAIL] {name} {detail}")


def test_lifecycle_matrix():
    transition("DISCOVERED", "SCREENED", evidence="ok")
    check("allowed_screen", True)
    try:
        transition("DISCOVERED", "APPROVED", evidence="x")
        check("forbid_skip_to_approved", False)
    except LifecycleError:
        check("forbid_skip_to_approved", True)
    try:
        transition("REJECTED", "APPROVED", evidence="x")
        check("forbid_rejected_revive", False)
    except LifecycleError:
        check("forbid_rejected_revive", True)
    try:
        transition("VALIDATED", "DEMO_ELIGIBLE")  # no evidence
        check("evidence_required", False)
    except LifecycleError:
        check("evidence_required", True)


def test_registry_auth_and_dup():
    with tempfile.TemporaryDirectory() as td:
        r = ArrsRegistry(td)
        r.register_experiment({
            "experiment_id": "E1", "name": "t", "objective": "o",
            "status": "S", "source_branch": "b", "source_commit": "c",
            "dataset_class_policy": "A", "production_authorized": False, "execution_authorized": False,
        })
        try:
            r.register_experiment({
                "experiment_id": "E1", "name": "t", "objective": "o",
                "status": "S", "source_branch": "b", "source_commit": "c",
                "dataset_class_policy": "A", "production_authorized": False, "execution_authorized": False,
            })
            check("dup_experiment", False)
        except ValueError:
            check("dup_experiment", True)
        try:
            r.register_experiment({
                "experiment_id": "E2", "name": "t", "objective": "o",
                "status": "S", "source_branch": "b", "source_commit": "c",
                "dataset_class_policy": "A", "production_authorized": True, "execution_authorized": False,
            })
            check("reject_prod_auth", False)
        except ValueError:
            check("reject_prod_auth", True)
        r.register_candidate({
            "candidate_id": "C1", "experiment_id": "E1", "definition_version": "1",
            "lifecycle_state": "DISCOVERED", "production_authorized": False, "execution_authorized": False,
        })
        r.transition_candidate("C1", "SCREENED", evidence="metrics")
        r.transition_candidate("C1", "VALIDATED", evidence="gates")
        c = r.get_candidate("C1")
        check("auth_still_false", c["production_authorized"] is False and c["execution_authorized"] is False)
        check("validate_clean", r.validate() == [])


def test_evaluation_statuses():
    from evaluation import hard_materiality_gate, require_trade_management, TradeManagementSpec, aggregate_gates
    g = hard_materiality_gate(abs_mean_bps=1.0, hit_rate=0.5, n=1000)
    check("materiality_fail", g.status == "FAIL")
    g2 = hard_materiality_gate(abs_mean_bps=12.0, hit_rate=0.6, n=250)
    check("materiality_pass", g2.status == "PASS")
    g3 = hard_materiality_gate(abs_mean_bps=12.0, hit_rate=0.6, n=10)
    check("materiality_insufficient", g3.status == "INSUFFICIENT_EVIDENCE")
    tm = require_trade_management(TradeManagementSpec.undefined())
    check("tm_required", tm.status == "FAIL")
    check("aggregate_fail", aggregate_gates([g2, tm]) == "FAIL")


def test_monitoring():
    from monitoring import assess_health, MonitorSnapshot, monitoring_can_place_orders, monitoring_can_change_risk_limits
    check("no_orders", monitoring_can_place_orders() is False)
    check("no_risk", monitoring_can_change_risk_limits() is False)
    s = assess_health(MonitorSnapshot("c", None, None, None, None))
    check("missing_not_healthy", s == "INSUFFICIENT_DATA")


if __name__ == "__main__":
    test_lifecycle_matrix()
    test_registry_auth_and_dup()
    test_evaluation_statuses()
    test_monitoring()
    print(f"TOTAL {P} PASS {F} FAIL")
    sys.exit(0 if F == 0 else 1)
