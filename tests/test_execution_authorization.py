"""Adversarial execution-path authorization tests (no broker)."""
from __future__ import annotations

import pytest

from app.services.execution_authorization import (
    evaluate_symbol_authorization,
    filter_actionable_signal,
    is_queue_row_execution_authorized,
)


class _Reg:
    def __init__(self, instruments=None, rulebooks=None):
        self._instruments = instruments or []
        self._rulebooks = {r["rulebook_id"]: r for r in (rulebooks or [])}

    def list_instruments(self, tradeable_only=False):
        rows = self._instruments
        if tradeable_only:
            rows = [r for r in rows if r.get("tradeable")]
        return rows

    def get_rulebook(self, rid):
        return self._rulebooks.get(rid)


def test_missing_registry_fail_closed():
    ok, reason, _ = evaluate_symbol_authorization(None, "EURUSD")
    assert ok is False
    assert reason == "registry_unavailable_fail_closed"


def test_unknown_instrument():
    ok, reason, _ = evaluate_symbol_authorization(_Reg(), "EURUSD")
    assert ok is False
    assert reason == "unknown_instrument"


def test_research_eligible_not_authorized():
    reg = _Reg(instruments=[{
        "instrument": "EURUSD", "tradeable": False, "good": False,
        "router_status": "RESEARCH_ELIGIBLE", "eligible_rulebooks": ["RB1"],
        "timeframe": "M5",
    }])
    ok, reason, _ = evaluate_symbol_authorization(reg, "EURUSD")
    assert ok is False
    assert "not_authorized" in reason


def test_tradeable_without_rulebook_ok_for_symbol_gate():
    reg = _Reg(instruments=[{
        "instrument": "EURUSD", "tradeable": True, "good": True,
        "router_status": "TRADING_ENABLED", "eligible_rulebooks": ["RB1"],
        "timeframe": "M5",
    }])
    ok, reason, _ = evaluate_symbol_authorization(reg, "EURUSD")
    assert ok is True


def test_rulebook_not_in_registry():
    reg = _Reg(
        instruments=[{
            "instrument": "EURUSD", "tradeable": True, "good": True,
            "router_status": "TRADING_ENABLED", "eligible_rulebooks": ["RB1"],
            "timeframe": "M5",
        }],
        rulebooks=[],
    )
    ok, reason, _ = evaluate_symbol_authorization(reg, "EURUSD", rulebook_id="RB1")
    assert ok is False
    assert reason == "rulebook_not_in_operational_registry"


def test_rulebook_not_eligible():
    reg = _Reg(
        instruments=[{
            "instrument": "EURUSD", "tradeable": True, "good": True,
            "router_status": "TRADING_ENABLED", "eligible_rulebooks": ["OTHER"],
            "timeframe": "M5",
        }],
        rulebooks=[{"rulebook_id": "RB1", "instrument": "EURUSD", "timeframe": "M5"}],
    )
    ok, reason, _ = evaluate_symbol_authorization(reg, "EURUSD", rulebook_id="RB1")
    assert ok is False
    assert reason == "rulebook_not_in_instrument_eligible_list"


def test_timeframe_mismatch():
    reg = _Reg(
        instruments=[{
            "instrument": "EURUSD", "tradeable": True, "good": True,
            "router_status": "TRADING_ENABLED", "eligible_rulebooks": ["RB1"],
            "timeframe": "M15",
        }],
        rulebooks=[{"rulebook_id": "RB1", "instrument": "EURUSD", "timeframe": "M5"}],
    )
    ok, reason, _ = evaluate_symbol_authorization(reg, "EURUSD", rulebook_id="RB1")
    assert ok is False
    assert "timeframe" in reason


def test_queue_row_requires_explicit_flags():
    assert is_queue_row_execution_authorized({}) is False
    assert is_queue_row_execution_authorized({"production_authorized": False}) is False
    assert is_queue_row_execution_authorized({"production_authorized": True}) is True
    assert is_queue_row_execution_authorized({"controlled_demo_authorized": True}) is True


def test_filter_actionable_rejects_unauthorized_queue_row():
    reg = _Reg(instruments=[{
        "instrument": "EURUSD", "tradeable": True, "good": True,
        "router_status": "TRADING_ENABLED", "eligible_rulebooks": ["RB1"],
        "timeframe": "M5",
    }])
    row = {
        "symbol": "EURUSD",
        "production_authorized": False,
        "controlled_demo_authorized": False,
        "rulebook_id": "RB1",
    }
    ok, reason = filter_actionable_signal(reg, row)
    assert ok is False
    assert reason == "queue_row_not_execution_authorized"


def test_filter_actionable_accepts_controlled_demo_when_registry_ok():
    reg = _Reg(
        instruments=[{
            "instrument": "EURUSD", "tradeable": True, "good": True,
            "router_status": "TRADING_ENABLED", "eligible_rulebooks": ["RB1"],
            "timeframe": "M5",
        }],
        rulebooks=[{"rulebook_id": "RB1", "instrument": "EURUSD", "timeframe": "M5"}],
    )
    row = {
        "symbol": "EURUSD",
        "production_authorized": False,
        "controlled_demo_authorized": True,
        "rulebook_id": "RB1",
        "timeframe": "M5",
    }
    ok, reason = filter_actionable_signal(reg, row)
    assert ok is True
    assert reason == "ok"


def test_single_pending_parity_logic():
    """Unauthorized queue row must map to has_signal=False (mirrors router contract)."""
    reg = _Reg(instruments=[{
        "instrument": "EURUSD", "tradeable": True, "good": True,
        "router_status": "TRADING_ENABLED", "eligible_rulebooks": [],
        "timeframe": "M5",
    }])
    row = {
        "symbol": "EURUSD",
        "side": "BUY",
        "signal_id": "sig-1",
        "production_authorized": False,
        "controlled_demo_authorized": False,
    }
    ok, reason = filter_actionable_signal(reg, row)
    assert ok is False
    # Simulated single-pending response shape
    resp = {
        "has_signal": False if not ok else True,
        "signal": "HOLD" if not ok else row["side"],
        "authorized": ok,
        "reason": reason,
    }
    assert resp["has_signal"] is False
    assert resp["authorized"] is False
