#!/usr/bin/env python3
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
from registry import ArrsRegistry
from import_discovery import import_discovery
from import_p7 import import_p7

P=F=0
def check(n,c,d=""):
    global P,F
    if c: P+=1; print(f"[PASS] {n}")
    else: F+=1; print(f"[FAIL] {n} {d}")

def main():
    with tempfile.TemporaryDirectory() as td:
        r = ArrsRegistry(td)
        a1 = import_discovery(r)
        a2 = import_discovery(r)
        check("discovery_first", a1["status"] == "imported")
        check("discovery_idempotent", a2["status"] == "already_imported")
        b1 = import_p7(r)
        b2 = import_p7(r)
        check("p7_first", b1["status"] == "imported")
        check("p7_idempotent", b2["status"] == "already_imported")
        cands = r.list_candidates()
        neg = [c for c in cands if c["candidate_id"] == "CAND-PD-WAVE-NEGATIVE-20261022"]
        check("negative_preserved", len(neg) == 1 and neg[0]["lifecycle_state"] == "REJECTED")
        check("validate", r.validate() == [])
        # no auth
        check("all_auth_false", all(c["production_authorized"] is False for c in cands))
    print(f"TOTAL {P} PASS {F} FAIL")
    sys.exit(0 if F == 0 else 1)

if __name__ == "__main__":
    main()
