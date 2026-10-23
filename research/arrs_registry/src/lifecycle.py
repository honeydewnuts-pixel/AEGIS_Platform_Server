"""Validated lifecycle transitions — fail closed."""
from __future__ import annotations
from schema import LIFECYCLE_STATES

class LifecycleError(ValueError):
    pass

# Permitted edges (from -> set of to)
ALLOWED = {
    "DISCOVERED": {"SCREENED", "REJECTED"},
    "SCREENED": {"VALIDATED", "REJECTED", "DISCOVERED"},
    "VALIDATED": {"DEMO_ELIGIBLE", "REJECTED", "DEGRADED"},
    "DEMO_ELIGIBLE": {"DEMO_QUALIFIED", "REJECTED", "SUSPENDED", "DEGRADED"},
    "DEMO_QUALIFIED": {"APPROVED", "REJECTED", "SUSPENDED", "DEGRADED"},
    "APPROVED": {"DEGRADED", "SUSPENDED", "RETIRED"},
    "DEGRADED": {"SUSPENDED", "RETIRED", "VALIDATED", "REJECTED"},
    "SUSPENDED": {"DEGRADED", "RETIRED", "REJECTED", "VALIDATED"},
    "REJECTED": set(),  # terminal for this version; new version for reconsideration
    "RETIRED": set(),
}

# APPROVED is research-governance label only; does NOT grant production_authorized
RESEARCH_ONLY_APPROVED = True

def transition(current: str, new: str, *, evidence: str | None = None, actor: str = "system") -> str:
    if current not in LIFECYCLE_STATES or new not in LIFECYCLE_STATES:
        raise LifecycleError(f"Unknown state: {current!r} -> {new!r}")
    if new not in ALLOWED.get(current, set()):
        raise LifecycleError(f"Invalid transition {current} -> {new}")
    if new in ("VALIDATED", "DEMO_ELIGIBLE", "DEMO_QUALIFIED", "APPROVED") and not evidence:
        raise LifecycleError(f"Evidence required for transition to {new}")
    return new
