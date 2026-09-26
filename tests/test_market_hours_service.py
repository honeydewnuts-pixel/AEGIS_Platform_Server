from datetime import datetime, timezone

from app.services.market_hours_service import (
    classify_session_group,
    session_status,
    fx_style_session_open,
)


def test_classify_fx_vs_crypto():
    assert classify_session_group("GBPUSD") == "WEEKEND_BREAK"
    assert classify_session_group("EURUSD.r") == "WEEKEND_BREAK"
    assert classify_session_group("XAUUSD") == "WEEKEND_BREAK"
    assert classify_session_group("BTCUSD") == "ALWAYS_OPEN"
    assert classify_session_group("ETHUSD") == "ALWAYS_OPEN"
    assert classify_session_group("Volatility75") == "ALWAYS_OPEN"


def test_saturday_fx_closed_crypto_open():
    sat = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    assert session_status("GBPUSD", sat)["market_open"] is False
    assert session_status("GBPUSD", sat)["pause_uploads"] is True
    assert session_status("BTCUSD", sat)["market_open"] is True
    assert session_status("BTCUSD", sat)["pause_uploads"] is False


def test_sunday_open_after_22_utc():
    before = datetime(2026, 9, 27, 21, 0, tzinfo=timezone.utc)
    after = datetime(2026, 9, 27, 22, 30, tzinfo=timezone.utc)
    assert fx_style_session_open(before) is False
    assert fx_style_session_open(after) is True
