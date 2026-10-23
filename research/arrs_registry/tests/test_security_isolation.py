#!/usr/bin/env python3
"""Prove ARRS cannot escalate to execution."""
from __future__ import annotations
import ast
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from registry import ArrsRegistry

P = F = 0

def check(n, c, d=""):
    global P, F
    if c:
        P += 1
        print(f"[PASS] {n}")
    else:
        F += 1
        print(f"[FAIL] {n} {d}")

FORBIDDEN_IMPORT_FRAGMENTS = (
    "autonomous_execution_service",
    "durable_execution_queue",
    "durable_lifecycle_service",
    "mt5",
    "place_order(",
    "submit_order",
)


def test_no_forbidden_imports_in_arrs_src():
    bad = []
    for p in (ROOT / "src").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for frag in FORBIDDEN_IMPORT_FRAGMENTS:
            if frag in text:
                bad.append(f"{p.name}:{frag}")
    check("no_forbidden_import_fragments", len(bad) == 0, str(bad))


def test_register_cannot_set_auth_true():
    with tempfile.TemporaryDirectory() as td:
        r = ArrsRegistry(td)
        try:
            r.register_experiment({
                "experiment_id": "EX", "name": "n", "objective": "o", "status": "s",
                "source_branch": "b", "source_commit": "c", "dataset_class_policy": "A",
                "production_authorized": True, "execution_authorized": False,
            })
            check("block_prod_true", False)
        except ValueError:
            check("block_prod_true", True)


def test_transition_resets_auth():
    with tempfile.TemporaryDirectory() as td:
        r = ArrsRegistry(td)
        r.register_experiment({
            "experiment_id": "EX", "name": "n", "objective": "o", "status": "s",
            "source_branch": "b", "source_commit": "c", "dataset_class_policy": "A",
            "production_authorized": False, "execution_authorized": False,
        })
        r.register_candidate({
            "candidate_id": "C", "experiment_id": "EX", "definition_version": "1",
            "lifecycle_state": "DISCOVERED", "production_authorized": False, "execution_authorized": False,
        })
        # force-corrupt then transition should clear
        r._data["candidates"]["C"]["production_authorized"] = True
        r.transition_candidate("C", "SCREENED", evidence="x")
        check("transition_clears_auth", r.get_candidate("C")["production_authorized"] is False)


def test_arrs_does_not_call_execution_guard_allow_live():
    # Static: evaluation module has no Decision.ALLOW_LIVE
    text = (ROOT / "src" / "evaluation.py").read_text()
    check("no_allow_live", "ALLOW_LIVE" not in text and "place_order" not in text)


if __name__ == "__main__":
    test_no_forbidden_imports_in_arrs_src()
    test_register_cannot_set_auth_true()
    test_transition_resets_auth()
    test_arrs_does_not_call_execution_guard_allow_live()
    print(f"TOTAL {P} PASS {F} FAIL")
    sys.exit(0 if F == 0 else 1)
