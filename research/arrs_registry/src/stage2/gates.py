"""Preregistered qualification gates — fail closed on missing evidence."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class GatePolicy:
    policy_id: str = "ARRS_STAGE2_GATES_V1"
    min_val_trades: int = 30
    min_test_trades: int = 20
    min_val_pf: float = 1.2
    min_test_pf: float = 1.1
    require_class_a: bool = True
    require_trade_management: bool = True
    # Multiple-testing: if n_variants > 1 without correction, block full qualification
    max_unadjusted_variants: int = 1

    def to_dict(self):
        return asdict(self)


def evaluate_gates(
    *,
    data_report: dict,
    wf: dict,
    tm_defined: bool,
    n_variants_tested: int = 1,
    policy: GatePolicy | None = None,
) -> dict[str, Any]:
    policy = policy or GatePolicy()
    gates = {}

    # Data eligibility
    if not data_report.get("ok"):
        gates["data_eligibility"] = {"status": "FAIL", "detail": data_report.get("issues")}
    elif policy.require_class_a and data_report.get("data_class") != "A_BIDASK":
        gates["data_eligibility"] = {"status": "FAIL", "detail": "Class B cannot claim Bid/Ask executable qualification"}
    else:
        gates["data_eligibility"] = {"status": "PASS"}

    # TM required for trade-level
    if policy.require_trade_management and not tm_defined:
        gates["trade_management"] = {"status": "FAIL", "detail": "TM template required for trade-level qualification"}
    else:
        gates["trade_management"] = {"status": "PASS" if tm_defined else "INSUFFICIENT_EVIDENCE"}

    val = wf.get("partitions", {}).get("val", {})
    test = wf.get("partitions", {}).get("test", {})

    def part_gate(name, part, min_tr, min_pf):
        if part.get("status") == "INSUFFICIENT_DATA" or part.get("trades") is None:
            return {"status": "INSUFFICIENT_EVIDENCE", "detail": part}
        if part.get("trades", 0) < min_tr:
            return {"status": "INSUFFICIENT_EVIDENCE", "detail": f"trades={part.get('trades')}<{min_tr}"}
        pf = part.get("pf")
        if pf is None:
            return {"status": "INSUFFICIENT_EVIDENCE", "detail": "pf undefined"}
        if pf < min_pf:
            return {"status": "FAIL", "detail": f"pf={pf}<{min_pf}"}
        return {"status": "PASS", "detail": {"trades": part["trades"], "pf": pf}}

    gates["validation"] = part_gate("val", val, policy.min_val_trades, policy.min_val_pf)
    gates["final_test"] = part_gate("test", test, policy.min_test_trades, policy.min_test_pf)

    if n_variants_tested > policy.max_unadjusted_variants:
        gates["multiple_testing"] = {
            "status": "INSUFFICIENT_EVIDENCE",
            "detail": f"{n_variants_tested} variants without adjustment; qualification blocked",
        }
    else:
        gates["multiple_testing"] = {"status": "PASS", "detail": "single_or_adjusted"}

    # Aggregate: missing evidence cannot pass
    statuses = [g["status"] for g in gates.values()]
    if any(s == "FAIL" for s in statuses):
        overall = "FAIL"
    elif any(s == "INSUFFICIENT_EVIDENCE" for s in statuses):
        overall = "INSUFFICIENT_EVIDENCE"
    elif statuses and all(s == "PASS" for s in statuses):
        overall = "PASS"
    else:
        overall = "INSUFFICIENT_EVIDENCE"

    return {
        "policy": policy.to_dict(),
        "gates": gates,
        "overall": overall,
        "execution_authorized": False,
        "production_authorized": False,
        "note": "Gate PASS does not grant trading authority",
    }
