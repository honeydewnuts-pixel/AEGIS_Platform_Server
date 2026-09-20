"""Independent MT5 OHLC history store (not derived from screenshots).

Bars arrive via POST /api/mt5/ohlc/stream, keyed by account_id + base symbol + TF.
Broker suffixes (GBPUSD.r) are normalized so Feed and Executor stay aligned.
"""
from __future__ import annotations

import time
from typing import Any

from app.utils.symbol_normalize import normalize_symbol


class OhlcStreamService:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(account_id: str, symbol: str, timeframe: str) -> str:
        base = normalize_symbol(symbol)
        return f"{account_id.strip()}|{base}|{(timeframe or 'M5').strip().upper()}"

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
        symbol_broker: str | None = None,
    ) -> dict[str, Any]:
        if not account_id or not symbol or not bars:
            return {"ok": False, "error": "account_id, symbol, and bars required"}
        base = normalize_symbol(symbol)
        if not base:
            return {"ok": False, "error": "invalid symbol"}
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
        broker = (symbol_broker or symbol or "").strip()
        payload = {
            "account_id": account_id,
            "symbol": base,
            "symbol_broker": broker,
            "timeframe": (timeframe or "M5").strip().upper(),
            "bars": cleaned[-500:],
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
        self._store[self._key(account_id, base, timeframe)] = payload
        return {
            "ok": True,
            "symbol": base,
            "symbol_broker": broker,
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
        out = dict(payload)
        out["stale"] = age > max_age_ms
        out["age_ms"] = age
        return out

    def status(self, account_id: str | None = None) -> dict[str, Any]:
        items = []
        for k, v in self._store.items():
            if account_id and not k.startswith(account_id.strip() + "|"):
                continue
            items.append(
                {
                    "key": k,
                    "symbol": v.get("symbol"),
                    "symbol_broker": v.get("symbol_broker"),
                    "timeframe": v.get("timeframe"),
                    "bar_count": v.get("bar_count"),
                    "received_at_ms": v.get("received_at_ms"),
                    "latest_close": (v.get("latest") or {}).get("close"),
                }
            )
        return {"streams": items, "count": len(items)}
