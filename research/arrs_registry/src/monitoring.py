"""Candidate health monitoring — recommendations only; no execution changes."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class MonitorSnapshot:
    candidate_id: str
    signal_count_recent: int | None
    expectancy_recent: float | None
    max_dd_recent: float | None
    data_quality_ok: bool | None
    baseline_expectancy: float | None = None


def assess_health(snap: MonitorSnapshot) -> str:
    """Return HEALTHY | DEGRADED | SUSPEND_RECOMMENDED | INSUFFICIENT_DATA."""
    if snap.data_quality_ok is False:
        return "SUSPEND_RECOMMENDED"
    if snap.signal_count_recent is None or snap.expectancy_recent is None:
        return "INSUFFICIENT_DATA"  # missing data ≠ healthy
    if snap.signal_count_recent < 5:
        return "INSUFFICIENT_DATA"
    if snap.baseline_expectancy is not None and snap.expectancy_recent < 0.5 * snap.baseline_expectancy:
        return "DEGRADED"
    if snap.max_dd_recent is not None and snap.max_dd_recent > 0.25:
        return "DEGRADED"
    return "HEALTHY"


def monitoring_can_place_orders() -> bool:
    return False


def monitoring_can_change_risk_limits() -> bool:
    return False
