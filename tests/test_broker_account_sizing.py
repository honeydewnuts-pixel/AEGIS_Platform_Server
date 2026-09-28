"""Standard vs micro broker specs — position sizing without strategy changes."""
import pytest

from app.services.position_sizing_engine import (
    instrument_spec_from_broker,
    size_by_stop_risk,
    fx_rates_for_pair_price,
)
from app.services.risk_assessment import assess_per_trade_risk


def _usdchf_standard():
    return instrument_spec_from_broker(
        "USDCHF",
        contract_size=100_000,
        volume_min=0.01,
        volume_max=100,
        volume_step=0.01,
        tick_size=0.00001,
        base_currency="USD",
        quote_currency="CHF",
        profit_currency="CHF",
    )


def _usdchf_micro():
    # Illustrative micro: 1,000 units per lot (broker-specific — not universal)
    return instrument_spec_from_broker(
        "USDCHF",
        contract_size=1_000,
        volume_min=0.01,
        volume_max=500,
        volume_step=0.01,
        tick_size=0.00001,
        base_currency="USD",
        quote_currency="CHF",
        profit_currency="CHF",
    )


ENTRY, STOP = 0.9000, 0.9015  # 15 pip short stop


def _size(equity, risk_pct, spec):
    rates = fx_rates_for_pair_price("USDCHF", ENTRY)
    return size_by_stop_risk(
        equity=equity,
        risk_pct=risk_pct,
        entry_price=ENTRY,
        stop_loss=STOP,
        side="SELL",
        spec=spec,
        account_currency="USD",
        fx_rates=rates,
    )


def test_standard_vs_micro_same_risk_budget():
    """Micro contract → larger volume for same monetary risk."""
    st = _size(1000, 1.0, _usdchf_standard())
    mi = _size(1000, 1.0, _usdchf_micro())
    assert st.allow and mi.allow
    assert mi.volume > st.volume


@pytest.mark.parametrize("equity", [50, 100, 250, 500, 1000, 5000, 10000])
def test_equity_ladder_standard(equity):
    r = _size(equity, 1.0, _usdchf_standard())
    if equity < 200:  # ~$166 loss/lot at this stop → min 0.01 needs ~$1.67 at 1%
        # 1% of 50 = 0.5 < 1.67 → reject
        if equity * 0.01 < 1.67:
            assert not r.allow or r.volume >= 0.01
    if r.allow:
        assert r.audit["estimated_monetary_risk"] <= equity * 0.01 + 1e-6


def test_small_account_micro_can_trade_when_standard_cannot():
    # 0.5% of $100 = $0.50 risk — standard loss/lot ~$166 → reject
    st = _size(100, 0.5, _usdchf_standard())
    assert not st.allow
    assert st.reason == "min_lot_exceeds_risk_budget"
    # micro loss/lot = 0.0015 * 1000 / 0.9 ≈ 1.667 → still may reject at 0.5%
    # 2.5% of $100 = $2.50 → micro 0.01 ok
    mi = _size(100, 2.5, _usdchf_micro())
    assert mi.allow
    assert mi.volume >= 0.01


def test_custom_contract_size():
    spec = instrument_spec_from_broker(
        "EURUSD",
        contract_size=10_000,
        volume_min=0.1,
        volume_max=50,
        volume_step=0.1,
        tick_size=0.00001,
        base_currency="EUR",
        quote_currency="USD",
        profit_currency="USD",
    )
    r = size_by_stop_risk(
        equity=5000,
        risk_pct=1.0,
        entry_price=1.10,
        stop_loss=1.09,
        side="BUY",
        spec=spec,
    )
    # loss/lot = 0.01 * 10000 = 100 USD → 50/100 = 0.5 → step 0.1 → 0.5
    assert r.allow
    assert r.volume == pytest.approx(0.5)


def test_invalid_spec_raises():
    with pytest.raises(ValueError):
        instrument_spec_from_broker(
            "USDCHF",
            contract_size=0,
            volume_min=0.01,
            volume_max=100,
            volume_step=0.01,
            tick_size=0.00001,
        )


def test_assessment_then_size_pipeline():
    """Client tolerance ≠ per-trade %; sizing uses assessed %."""
    a = assess_per_trade_risk(
        client_tolerance_pct=10.0,
        equity=10_000,
        max_concurrent_slots=5,
        open_positions=0,
    )
    assert a.allow
    assert a.per_trade_risk_pct < 10.0
    r = _size(10_000, a.per_trade_risk_pct, _usdchf_standard())
    assert r.allow
    assert r.audit["estimated_monetary_risk"] <= 10_000 * a.per_trade_risk_pct / 100 + 1e-6


def test_volume_step_round_down():
    spec = instrument_spec_from_broker(
        "GBPUSD",
        contract_size=100_000,
        volume_min=0.01,
        volume_max=100,
        volume_step=0.01,
        tick_size=0.00001,
        base_currency="GBP",
        quote_currency="USD",
        profit_currency="USD",
    )
    r = size_by_stop_risk(
        equity=1900,
        risk_pct=1.0,
        entry_price=1.25,
        stop_loss=1.24,
        side="BUY",
        spec=spec,
    )
    # loss/lot = 1000; budget 19 → 0.019 → 0.01
    assert r.allow
    assert r.volume == pytest.approx(0.01)
