import sys
import types
from datetime import datetime, timezone

import pytest

from app.services.mt5_market_snapshot_service import MT5MarketSnapshotService


class Tick:
    def __init__(self, tms, last, volume_real=1.0):
        self.time_msc = tms
        self.time = tms // 1000
        self.last = last
        self.bid = 0.0
        self.ask = 0.0
        self.volume_real = volume_real


def test_snapshot_uses_ticks_only_through_capture(monkeypatch):
    capture_ms = 1_800_000_123_450
    start_ms = (capture_ms // 60000) * 60000
    fake = types.SimpleNamespace(
        COPY_TICKS_ALL=0,
        symbol_select=lambda symbol, enabled: True,
        last_error=lambda: (0, "ok"),
        copy_ticks_range=lambda symbol, start, end, flag: [
            Tick(start_ms + 100, 1.1000),
            Tick(start_ms + 200, 1.1010),
            Tick(capture_ms, 1.0990),
            Tick(capture_ms + 1000, 9.9999),
        ],
    )
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    result = MT5MarketSnapshotService()._read("EURUSD", capture_ms)
    assert result["open"] == pytest.approx(1.1000)
    assert result["high"] == pytest.approx(1.1010)
    assert result["low"] == pytest.approx(1.0990)
    assert result["close"] == pytest.approx(1.0990)
    assert result["exact_at_capture"] is True
