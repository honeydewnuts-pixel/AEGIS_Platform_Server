"""Pending signals for MT5 AEGIS_Executor (single- and multi-pair).

Key = account_id|SYMBOL. One open pending signal per key until ACK or TTL.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from app.utils.symbol_normalize import normalize_symbol


class ExecutorSignalService:
    def __init__(self, max_age_sec: float = 300.0) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self.max_age_sec = max_age_sec

    @staticmethod
    def _key(account_id: str, symbol: str) -> str:
        return f"{account_id.strip()}|{(symbol or '').strip().upper()}"

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return normalize_symbol(symbol)

    def publish(
        self,
        *,
        account_id: str,
        symbol: str,
        side: str,
        confidence: float = 0.0,
        rule_name: str = "",
        volume: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        details: str = "",
    ) -> str | None:
        side_u = (side or "").strip().upper()
        if side_u not in ("BUY", "SELL"):
            return None
        sym = self.normalize_symbol(symbol)
        if not account_id or not sym:
            return None
        signal_id = str(uuid.uuid4())
        payload = {
            "signal_id": signal_id,
            "account_id": account_id,
            "symbol": sym,
            "side": side_u,
            "confidence": float(confidence or 0),
            "rule_name": rule_name or "",
            "volume": volume,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "details": (details or "")[:500],
            "created_at_ms": int(time.time() * 1000),
            "acked": False,
        }
        with self._lock:
            self._pending[self._key(account_id, sym)] = payload
        return signal_id

    def get_pending(self, account_id: str, symbol: str) -> dict[str, Any] | None:
        key = self._key(account_id, self.normalize_symbol(symbol))
        now = int(time.time() * 1000)
        with self._lock:
            row = self._pending.get(key)
            if not row:
                return None
            age = (now - int(row.get("created_at_ms") or 0)) / 1000.0
            if age > self.max_age_sec:
                self._pending.pop(key, None)
                return None
            if row.get("acked"):
                return None
            return dict(row)

    def get_pending_many(self, account_id: str, symbols: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sym in symbols:
            base = self.normalize_symbol(sym)
            if not base or base in seen:
                continue
            seen.add(base)
            row = self.get_pending(account_id, base)
            if row:
                out.append(row)
        return out

    def ack(
        self,
        account_id: str,
        signal_id: str,
        *,
        ticket: int = 0,
        ok: bool = True,
        message: str = "",
    ) -> bool:
        with self._lock:
            for key, row in list(self._pending.items()):
                if row.get("account_id") == account_id and row.get("signal_id") == signal_id:
                    row["acked"] = True
                    row["ack_ticket"] = ticket
                    row["ack_ok"] = ok
                    row["ack_message"] = message[:300]
                    row["acked_at_ms"] = int(time.time() * 1000)
                    self._pending.pop(key, None)
                    return True
        return False
