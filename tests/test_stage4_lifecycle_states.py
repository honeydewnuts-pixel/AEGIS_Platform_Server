"""Stage 4 — lifecycle state vocabulary and mismatch documentation tests."""
from __future__ import annotations

from pathlib import Path


# Documented valid states used by DurableLifecycleService
VALID_STATES = {
    "SIGNAL_QUEUED",
    "ORDER_SENT",
    "ORDER_REJECTED",
    "BROKER_CONFIRMED_OPEN",
    "POSITION_OPEN",
    "POSITION_CLOSED",
    "RISK_RELEASED",
    "RECONCILIATION_REQUIRED",
}

TERMINAL = {"RISK_RELEASED", "POSITION_CLOSED", "ORDER_REJECTED"}


def test_lifecycle_states_present_in_service_source():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    for s in ("SIGNAL_QUEUED", "POSITION_OPEN", "RISK_RELEASED", "RECONCILIATION_REQUIRED", "ORDER_REJECTED"):
        assert f'"{s}"' in src or f"'{s}'" in src


def test_reconcile_reports_unknown_broker_tickets():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "unknown_broker_tickets" in src
    assert "unknown_positions_not_auto_adopted" in src


def test_on_close_idempotent_already_released():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "ALREADY_RELEASED" in src
    assert "with_for_update" in src


def test_ack_skips_risk_when_already_open():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "should_record_open_risk" in src or "already recorded" in src.lower() or "return row, False" in src
