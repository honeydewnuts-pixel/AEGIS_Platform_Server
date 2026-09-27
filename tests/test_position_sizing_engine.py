"""Unit tests for generalized stop-loss risk position sizing."""
import pytest

from app.services.position_sizing_engine import (
    InstrumentSpec,
    convert_to_account_currency,
    default_spec_for_symbol,
    fx_rates_for_pair_price,
    size_by_stop_risk,
    stop_distance,
)


def test_stop_distance_sides():
    assert stop_distance(1.0, 1.01, "SELL") == pytest.approx(0.01)
    assert stop_distance(1.0, 0.99, "BUY") == pytest.approx(0.01)
    assert stop_distance(1.0, 0.99, "SELL") == 0.0


def test_usdchf_short_sizing_not_hardcoded():
    """USDCHF as first validation case via generic FX template."""
    spec = default_spec_for_symbol("USDCHF")
    assert spec is not None
    assert spec.contract_size == 100_000
    assert spec.profit_currency == "CHF"
    entry = 0.9000
    stop = 0.9015  # 15 pip stop
    rates = fx_rates_for_pair_price("USDCHF", entry)
    # loss per lot CHF = 0.0015 * 100000 = 150 CHF
    # CHF→USD: 150 / 0.90 = 166.666... USD
    r = size_by_stop_risk(
        equity=10_000,
        risk_pct=1.0,  # $100 risk
        entry_price=entry,
        stop_loss=stop,
        side="SELL",
        spec=spec,
        account_currency="USD",
        fx_rates=rates,
    )
    assert r.allow
    # 100 / 166.67 ≈ 0.60 lots, round down to 0.01 step
    assert r.volume == pytest.approx(0.60, abs=0.011)
    assert r.audit["estimated_monetary_risk"] <= 100.0 + 1e-6


def test_round_down_never_exceeds_budget():
    spec = default_spec_for_symbol("EURUSD")
    assert spec is not None
    entry = 1.1000
    stop = 1.0900  # 100 pip long stop
    rates = fx_rates_for_pair_price("EURUSD", entry)
    r = size_by_stop_risk(
        equity=1000,
        risk_pct=0.5,  # $5
        entry_price=entry,
        stop_loss=stop,
        side="BUY",
        spec=spec,
        fx_rates=rates,
    )
    # loss/lot = 0.01 * 100000 = 1000 USD → 5/1000 = 0.005 → below min 0.01 → reject
    assert not r.allow
    assert r.reason == "min_lot_exceeds_risk_budget"


def test_min_lot_reject():
    spec = default_spec_for_symbol("GBPUSD")
    r = size_by_stop_risk(
        equity=100,
        risk_pct=0.05,
        entry_price=1.25,
        stop_loss=1.24,
        side="BUY",
        spec=spec,
        fx_rates=fx_rates_for_pair_price("GBPUSD", 1.25),
    )
    assert not r.allow
    assert r.reason == "min_lot_exceeds_risk_budget"


def test_missing_fx_rate_rejects():
    spec = InstrumentSpec(
        symbol="EURGBP",
        asset_class="forex",
        contract_size=100_000,
        volume_min=0.01,
        volume_max=100,
        volume_step=0.01,
        tick_size=0.00001,
        profit_currency="GBP",
        quote_currency="GBP",
        base_currency="EUR",
    )
    r = size_by_stop_risk(
        equity=10_000,
        risk_pct=1.0,
        entry_price=0.85,
        stop_loss=0.84,
        side="BUY",
        spec=spec,
        account_currency="USD",
        fx_rates={},  # no GBPUSD
    )
    assert not r.allow
    assert r.reason == "missing_fx_rate"


def test_invalid_stop_rejects():
    spec = default_spec_for_symbol("USDCHF")
    r = size_by_stop_risk(
        equity=5000,
        risk_pct=1.0,
        entry_price=0.9,
        stop_loss=0.89,  # below entry on SELL
        side="SELL",
        spec=spec,
        fx_rates=fx_rates_for_pair_price("USDCHF", 0.9),
    )
    assert not r.allow
    assert r.reason == "invalid_stop_distance"


def test_insufficient_margin():
    spec = default_spec_for_symbol("EURUSD")
    r = size_by_stop_risk(
        equity=50_000,
        risk_pct=5.0,
        entry_price=1.10,
        stop_loss=1.09,
        side="BUY",
        spec=spec,
        fx_rates=fx_rates_for_pair_price("EURUSD", 1.10),
        margin_per_lot=1000.0,
        available_margin=10.0,
    )
    assert not r.allow
    assert r.reason == "insufficient_margin"


def test_metal_xauusd():
    spec = default_spec_for_symbol("XAUUSD")
    assert spec is not None
    r = size_by_stop_risk(
        equity=10_000,
        risk_pct=1.0,
        entry_price=2000.0,
        stop_loss=1990.0,
        side="BUY",
        spec=spec,
        account_currency="USD",
    )
    # loss/lot = 10 * 100 = 1000 USD → 100/1000 = 0.1
    assert r.allow
    assert r.volume == pytest.approx(0.10, abs=0.001)


def test_equity_required():
    spec = default_spec_for_symbol("USDCHF")
    r = size_by_stop_risk(
        equity=0,
        risk_pct=1.0,
        entry_price=0.9,
        stop_loss=0.91,
        side="SELL",
        spec=spec,
    )
    assert not r.allow
    assert r.reason == "equity_required_for_risk_sizing"


def test_convert_identity():
    v, why = convert_to_account_currency(100, "USD", "USD", None)
    assert v == 100 and why == "ok"


def test_volume_step_rounding():
    spec = InstrumentSpec(
        symbol="EURUSD", asset_class="forex", contract_size=100_000,
        volume_min=0.01, volume_max=100, volume_step=0.01,
        tick_size=0.00001, profit_currency="USD", quote_currency="USD", base_currency="EUR",
    )
    # design budget so raw_lots = 0.019 → round down 0.01
    # loss/lot = 1000 → need budget 19
    r = size_by_stop_risk(
        equity=1900,
        risk_pct=1.0,  # 19
        entry_price=1.1,
        stop_loss=1.09,
        side="BUY",
        spec=spec,
    )
    assert r.allow
    assert r.volume == pytest.approx(0.01)
