"""File-based ARRS registry with integrity checks. Single-writer design."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from schema import SCHEMA_VERSION, LIFECYCLE_STATES, EVAL_STATUSES, AUTH_FIELDS
from lifecycle import transition, LifecycleError


def _sha256_obj(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


class ArrsRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "registry.json"
        self.lock_path = self.root / ".registry.lock"
        self._data = self._load()

    def _empty(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "production_authorized_default": False,
            "execution_authorized_default": False,
            "experiments": {},
            "candidates": {},
            "evaluations": {},
            "events": [],
            "imports": {},
        }

    def _load(self) -> dict:
        if not self.path.exists():
            return self._empty()
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {data.get('schema_version')}")
        return data

    def _atomic_write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, indent=2, sort_keys=True, default=str) + "\n"
        fd, tmp = tempfile.mkstemp(dir=str(self.root), prefix=".reg_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            try:
                os.replace(tmp, self.path)
            except OSError:
                # Fallback for filesystems that reject replace
                self.path.write_text(payload, encoding="utf-8")
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _event(self, kind: str, **kwargs) -> None:
        self._data["events"].append({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": kind,
            **kwargs,
        })

    def _reject_auth_elevation(self, record: dict) -> None:
        for k in AUTH_FIELDS:
            if record.get(k) is True:
                raise ValueError(
                    f"ARRS refuses to set {k}=true; research cannot authorize execution"
                )
            record[k] = False

    def register_experiment(self, exp: dict) -> dict:
        eid = exp.get("experiment_id")
        if not eid:
            raise ValueError("experiment_id required")
        if eid in self._data["experiments"]:
            raise ValueError(f"Duplicate experiment_id: {eid}")
        self._reject_auth_elevation(exp)
        exp = dict(exp)
        exp.setdefault("status", "REGISTERED")
        exp["record_hash"] = _sha256_obj({k: v for k, v in exp.items() if k != "record_hash"})
        self._data["experiments"][eid] = exp
        self._event("experiment_registered", experiment_id=eid, record_hash=exp["record_hash"])
        self._atomic_write()
        return exp

    def register_candidate(self, cand: dict) -> dict:
        cid = cand.get("candidate_id")
        eid = cand.get("experiment_id")
        if not cid or not eid:
            raise ValueError("candidate_id and experiment_id required")
        if eid not in self._data["experiments"]:
            raise ValueError(f"Unknown experiment_id: {eid}")
        if cid in self._data["candidates"]:
            raise ValueError(f"Duplicate candidate_id: {cid}")
        state = cand.get("lifecycle_state", "DISCOVERED")
        if state not in LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle_state: {state}")
        self._reject_auth_elevation(cand)
        cand = dict(cand)
        cand["lifecycle_state"] = state
        cand["definition_version"] = cand.get("definition_version") or "1"
        cand["record_hash"] = _sha256_obj({k: v for k, v in cand.items() if k != "record_hash"})
        self._data["candidates"][cid] = cand
        self._event("candidate_registered", candidate_id=cid, state=state)
        self._atomic_write()
        return cand

    def transition_candidate(
        self, candidate_id: str, new_state: str, *, evidence: str | None = None, actor: str = "system"
    ) -> dict:
        c = self._data["candidates"].get(candidate_id)
        if not c:
            raise ValueError(f"Unknown candidate: {candidate_id}")
        old = c["lifecycle_state"]
        transition(old, new_state, evidence=evidence, actor=actor)
        c["lifecycle_state"] = new_state
        # Authorization never elevated
        c["production_authorized"] = False
        c["execution_authorized"] = False
        c["record_hash"] = _sha256_obj({k: v for k, v in c.items() if k != "record_hash"})
        self._event(
            "lifecycle_transition",
            candidate_id=candidate_id,
            from_state=old,
            to_state=new_state,
            evidence=evidence,
            actor=actor,
        )
        self._atomic_write()
        return c

    def add_evaluation(self, ev: dict) -> dict:
        eid = ev.get("evaluation_id")
        cid = ev.get("candidate_id")
        if not eid or not cid:
            raise ValueError("evaluation_id and candidate_id required")
        if cid not in self._data["candidates"]:
            raise ValueError(f"Unknown candidate: {cid}")
        if eid in self._data["evaluations"]:
            raise ValueError(f"Duplicate evaluation_id: {eid}")
        status = ev.get("status", "NOT_RUN")
        if status not in EVAL_STATUSES:
            raise ValueError(f"Invalid evaluation status: {status}")
        self._reject_auth_elevation(ev)
        ev = dict(ev)
        ev["status"] = status
        ev["record_hash"] = _sha256_obj({k: v for k, v in ev.items() if k != "record_hash"})
        self._data["evaluations"][eid] = ev
        self._event("evaluation_added", evaluation_id=eid, candidate_id=cid, status=status)
        self._atomic_write()
        return ev

    def mark_import(self, import_key: str, meta: dict) -> None:
        if import_key in self._data["imports"]:
            return  # idempotent
        self._data["imports"][import_key] = meta
        self._event("import_recorded", import_key=import_key)
        self._atomic_write()

    def has_import(self, import_key: str) -> bool:
        return import_key in self._data["imports"]

    def list_experiments(self) -> list:
        return list(self._data["experiments"].values())

    def list_candidates(self) -> list:
        return list(self._data["candidates"].values())

    def get_candidate(self, candidate_id: str) -> dict | None:
        return self._data["candidates"].get(candidate_id)

    def events(self) -> list:
        return list(self._data["events"])

    def validate(self) -> list[str]:
        """Return list of integrity issues (empty if ok)."""
        issues = []
        for cid, c in self._data["candidates"].items():
            if c.get("experiment_id") not in self._data["experiments"]:
                issues.append(f"orphan candidate {cid}")
            if c.get("lifecycle_state") not in LIFECYCLE_STATES:
                issues.append(f"bad state {cid}")
            for k in AUTH_FIELDS:
                if c.get(k) is True:
                    issues.append(f"auth elevation on {cid}.{k}")
        for eid, e in self._data["evaluations"].items():
            if e.get("candidate_id") not in self._data["candidates"]:
                issues.append(f"orphan evaluation {eid}")
            if e.get("status") not in EVAL_STATUSES:
                issues.append(f"bad eval status {eid}")
        return issues
