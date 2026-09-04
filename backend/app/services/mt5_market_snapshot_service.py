"""Authoritative M1 market snapshot from the already-connected MT5 terminal.

This service deliberately uses the MetaTrader5 terminal API on the Windows
worker. It does not call a broker REST/HTTP market-data API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncio


class MT5MarketSnapshotService:
    """Read-only market data helper; assumes MT5 is already connected."""

    @staticmethod
    def _price(tick: Any) -> float | None:
        last = float(getattr(tick, "last", 0.0) or 0.0)
        bid = float(getattr(tick, "bid", 0.0) or 0.0)
        ask = float(getattr(tick, "ask", 0.0) or 0.0)
        if last > 0:
            return last
        if bid > 0:
            return bid
        if ask > 0:
            return ask
        return None

    @staticmethod
    def _tick_time_ms(tick: Any) -> int:
        sec = int(getattr(tick, "time", 0) or 0)
        usec = int(getattr(tick, "time_msc", 0) or 0)
        if usec:
            return usec
        return sec * 1000

    def _read(self, symbol: str, captured_at_ms: int) -> dict[str, Any]:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise RuntimeError("MetaTrader5 package is required on the Windows MT5 worker.") from exc

        symbol = symbol.strip()
        if not symbol:
            raise ValueError("MT5 symbol is required for synchronized OHLC.")

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"MT5 symbol is unavailable: {symbol}")

        capture_dt = datetime.fromtimestamp(captured_at_ms / 1000.0, tz=timezone.utc)
        minute_start_ms = (captured_at_ms // 60000) * 60000
        minute_start = datetime.fromtimestamp(minute_start_ms / 1000.0, tz=timezone.utc)

        ticks = mt5.copy_ticks_range(
            symbol,
            minute_start,
            capture_dt,
            mt5.COPY_TICKS_ALL,
        )
        if ticks is None:
            code = mt5.last_error()
            raise RuntimeError(f"MT5 tick query failed for {symbol}: {code}")

        rows = []
        for tick in ticks:
            tms = self._tick_time_ms(tick)
            if minute_start_ms <= tms <= captured_at_ms:
                price = self._price(tick)
                if price is not None:
                    rows.append((tms, price, float(getattr(tick, "volume_real", 0.0) or 0.0)))

        if not rows:
            raise RuntimeError(
                f"No MT5 ticks available for {symbol} at capture time {capture_dt.isoformat()}."
            )

        rows.sort(key=lambda x: x[0])
        prices = [r[1] for r in rows]
        volume = sum(r[2] for r in rows)

        return {
            "source": "MT5_TERMINAL_TICKS",
            "symbol": symbol,
            "timeframe": "M1",
            "candle_time": minute_start.isoformat(),
            "capture_time": capture_dt.isoformat(),
            "capture_at_ms": captured_at_ms,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "tick_count": len(rows),
            "tick_volume_real_sum": volume,
            "exact_at_capture": True,
        }

    async def get_m1_ohlc_at(self, symbol: str, captured_at_ms: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._read, symbol, int(captured_at_ms))
