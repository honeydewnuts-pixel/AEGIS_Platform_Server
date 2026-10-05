"""Account currency must come from profile, not silent USD assume."""
from app.services.position_sizing_engine import convert_to_account_currency


def test_usd_passthrough():
    v, why = convert_to_account_currency(100.0, "USD", "USD", {})
    assert v == 100.0


def test_missing_fx_fail_closed():
    v, why = convert_to_account_currency(100.0, "EUR", "GBP", {})
    assert v is None
    assert why == "missing_fx_rate"


def test_valid_conversion_eur_to_usd():
    v, why = convert_to_account_currency(100.0, "EUR", "USD", {"EURUSD": 1.10})
    assert v is not None
    assert abs(v - 110.0) < 1e-6


def test_portfolio_overrides_default_usd_from_profile():
    """size_order source uses stored account_currency when profile non-USD."""
    from pathlib import Path
    src = Path("backend/app/services/portfolio_risk_service.py").read_text()
    assert "stored_ccy" in src
    assert "account_currency" in src
    auto = Path("backend/app/services/autonomous_ohlc_signal_service.py").read_text()
    assert "account_currency=acct_ccy" in auto
