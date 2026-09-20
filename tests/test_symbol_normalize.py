from app.utils.symbol_normalize import normalize_symbol, symbols_match


def test_suffixes():
    assert normalize_symbol("GBPUSD.r") == "GBPUSD"
    assert normalize_symbol("GBPUSDm") == "GBPUSD"
    assert normalize_symbol("EURUSD#") == "EURUSD"
    assert normalize_symbol("eurusd.pro") == "EURUSD"
    assert symbols_match("GBPUSD.r", "GBPUSD")


def test_stream_key_alignment():
    from app.services.ohlc_stream_service import OhlcStreamService

    s = OhlcStreamService()
    bars = [
        {"time": 1, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "tick_volume": 1, "spread": 1}
        for _ in range(5)
    ]
    r = s.ingest(account_id="ACC-1", symbol="GBPUSD.r", timeframe="M5", bars=bars, symbol_broker="GBPUSD.r")
    assert r["ok"] and r["symbol"] == "GBPUSD"
    got = s.get("ACC-1", "GBPUSD", "M5")
    assert got is not None and got["close"] == 1.05
    assert s.get("ACC-1", "GBPUSD.r", "M5") is not None
