"""Margin data integration: free margin + margin_per_lot fail-closed through sizing."""
from __future__ import annotations

import pytest

from app.services.position_sizing_engine import (
    default_spec_for_symbol,
    fx_rates_for_pair_price,
    size_by_stop_risk,
)


def _base(**extra):
    spec = default_spec_for_symbol("EURUSD")
    assert spec is not None
    kw = dict(
        equity=10_000.0,
        risk_pct=1.0,
        entry_price=1.10,
        stop_loss=1.09,
        side="BUY",
        spec=spec,
        fx_rates=fx_rates_for_pair_price("EURUSD", 1.10),
        require_margin_check=True,
    )
    kw.update(extra)
    return kw


def test_valid_margin_permits_order():
    r = size_by_stop_risk(**_base(margin_per_lot=200.0, available_margin=5_000.0))
    assert r.allow is True
    assert r.volume > 0
    assert r.audit["margin_check_status"] == "passed"
    assert r.audit["required_margin"] is not None
    assert r.audit["available_margin"] == 5_000.0
    assert r.audit["margin_per_lot"] == 200.0


def test_insufficient_margin_rejects():
    r = size_by_stop_risk(**_base(margin_per_lot=50_000.0, available_margin=10.0))
    assert r.allow is False
    assert r.volume == 0.0
    assert r.reason == "insufficient_margin"
    assert r.audit["required_margin"] is not None
    assert r.audit["available_margin"] == 10.0


def test_missing_margin_prevents_execution():
    r = size_by_stop_risk(**_base())
    assert r.allow is False
    assert r.volume == 0.0
    assert r.reason == "margin_data_missing"


def test_failed_sizing_cannot_enqueue_semantics():
    """Mirror autonomous path: only enqueue when allow and volume > 0."""
    r = size_by_stop_risk(**_base(margin_per_lot=None, available_margin=1000.0))
    can_enqueue = bool(r.allow) and float(r.volume) > 0
    assert can_enqueue is False
    assert r.reason == "margin_data_missing"
    assert "margin_per_lot" in (r.audit.get("margin_missing_fields") or [])


def test_audit_records_rejection_reason():
    r = size_by_stop_risk(**_base(margin_per_lot=100.0, available_margin=None))
    assert r.reason == "margin_data_missing"
    assert r.audit["margin_check_status"] == "rejected_missing_data"
    assert r.audit["margin_per_lot_supplied"] == 100.0
    assert r.audit["available_margin_supplied"] is None


def test_mt5_equity_payload_shape_example():
    """Documented example of MT5 OHLC Feed v2.05 equity POST body."""
    example = {
        "account_id": "ACC-1987D3D2E6",
        "equity_usd": 10000.00,
        "available_margin_usd": 9842.50,  # ACCOUNT_MARGIN_FREE — not equity
        "source": "mt5_ea",
    }
    assert example["available_margin_usd"] != example["equity_usd"]
    assert example["available_margin_usd"] > 0


def test_mt5_instrument_spec_margin_per_lot_example():
    """Documented example: margin_per_lot is for 1.0 lot via OrderCalcMargin."""
    example = {
        "account_id": "ACC-1987D3D2E6",
        "symbol": "EURUSD",
        "account_type": "standard",
        "broker_id": "default",
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "margin_per_lot": 333.33,  # OrderCalcMargin for volume=1.0
        "source": "mt5",
    }
    assert example["margin_per_lot"] > 0
