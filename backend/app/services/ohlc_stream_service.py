"""Independent MT5 OHLC history store (not derived from screenshots).

Bars arrive from the MT5 EA / worker via POST /api/mt5/ohlc/stream and are
keyed by account_id + symbol + timeframe. Analyze joins by those keys and
optional candle timestamp alignment.
"""

from __future__ import annotations

import time
from typing import Any


class OhlcStreamService:
    def __init__(self) -> None:
        # key -> payload
        self._store: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(account_id: str, symbol: str, timeframe: str) -> str:
        return f"{account_id.strip()}|{symbol.strip().upper()}|{(timeframe or 'M5').strip().upper()}"

    def ingest(
        self,
        *,
        account_id: str,
        symbol: str,
        timeframe: str,
        bars: list[dict[str, Any]],
        source: str = "mt5_ea",
        current_bar: dict[str, Any] | None = None,
        closed_bar: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not account_id or not symbol or not bars:
            return {"ok": False, "error": "account_id, symbol, and bars required"}
        cleaned: list[dict[str, Any]] = []
        for b in bars:
            try:
                cleaned.append(
                    {
                        "time": int(b.get("time") or b.get("t") or 0),
                        "open": float(b["open"] if "open" in b else b["o"]),
                        "high": float(b["high"] if "high" in b else b["h"]),
                        "low": float(b["low"] if "low" in b else b["l"]),
                        "close": float(b["close"] if "close" in b else b["c"]),
                        "tick_volume": int(b.get("tick_volume") or b.get("volume") or 0),
                        "spread": int(b.get("spread") or 0),
                        "bar_status": b.get("bar_status") or "CLOSED",
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        if not cleaned:
            return {"ok": False, "error": "no valid bars"}
        cleaned.sort(key=lambda x: x["time"])
        last = cleaned[-1]
        payload = {
            "account_id": account_id,
            "symbol": symbol.strip().upper(),
            "timeframe": (timeframe or "M5").strip().upper(),
            "bars": cleaned[-500:],  # cap memory
            "bar_count": len(cleaned[-500:]),
            "latest": last,
            "current_bar": current_bar,
            "closed_bar": closed_bar or last,
            "source": source,
            "received_at_ms": int(time.time() * 1000),
            "open": last["open"],
            "high": last["high"],
            "low": last["low"],
            "close": last["close"],
        }
        self._store[self._key(account_id, symbol, timeframe)] = payload
        return {
            "ok": True,
            "bar_count": payload["bar_count"],
            "latest_time": last["time"],
            "latest_close": last["close"],
        }

    def get(
        self,
        account_id: str,
        symbol: str,
        timeframe: str = "M5",
        *,
        max_age_ms: int = 15 * 60 * 1000,
    ) -> dict[str, Any] | None:
        key = self._key(account_id, symbol, timeframe)
        payload = self._store.get(key)
        if not payload:
            return None
        age = int(time.time() * 1000) - int(payload.get("received_at_ms") or 0)
        if age > max_age_ms:
            payload = dict(payload)
            payload["stale"] = True
            payload["age_ms"] = age
        else:
            payload = dict(payload)
            payload["stale"] = False
            payload["age_ms"] = age
        return payload

    def status(self, account_id: str | None = None) -> dict[str, Any]:
        items = []
        for k, v in self._store.items():
            if account_id and not k.startswith(account_id.strip() + "|"):
                continue
            items.append(
                {
                    "key": k,
                    "symbol": v.get("symbol"),
                    "timeframe": v.get("timeframe"),
                    "bar_count": v.get("bar_count"),
                    "received_at_ms": v.get("received_at_ms"),
                    "latest_close": (v.get("latest") or {}).get("close"),
                }
            )
        return {"streams": items, "count": len(items)}
