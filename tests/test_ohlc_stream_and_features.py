from app.services.ohlc_stream_service import OhlcStreamService
from app.services.feature_engine import compute_features


def test_ingest_and_get():
    s = OhlcStreamService()
    bars = [
        {"time": 1000 + i * 300, "open": 1.1 + i * 0.001, "high": 1.11 + i * 0.001,
         "low": 1.09 + i * 0.001, "close": 1.105 + i * 0.001, "tick_volume": 10}
        for i in range(30)
    ]
    r = s.ingest(account_id="ACC-1", symbol="GBPUSD", timeframe="M5", bars=bars)
    assert r["ok"] is True
    got = s.get("ACC-1", "GBPUSD", "M5")
    assert got is not None
    assert got["bar_count"] == 30
    assert got["stale"] is False


def test_features_ready():
    bars = [
        {"time": 1000 + i * 300, "open": 1.0 + i * 0.01, "high": 1.02 + i * 0.01,
         "low": 0.99 + i * 0.01, "close": 1.01 + i * 0.01}
        for i in range(40)
    ]
    f = compute_features(bars)
    assert f["ready"] is True
    assert f["rsi_14"] is not None
    assert f["bar_count"] == 40
