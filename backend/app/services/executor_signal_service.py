"""In-memory pending signals for MT5 AEGIS_Executor.mq5 clients.

When the brain emits BUY/SELL, publish here. The EA polls GET /api/executor/pending
and ACKs after OrderSend so the same signal is not re-traded.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class ExecutorSignalService:
    def __init__(self, max_age_sec: float = 300.0) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}  # key = account_id|SYMBOL
        self._acked: set[str] = set()
        self.max_age_sec = max_age_sec

    @staticmethod
    def _key(account_id: str, symbol: str) -> str:
        return f"{account_id.strip()}|{(symbol or '').strip().upper()}"

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
        sym = (symbol or "").strip().upper()
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
        key = self._key(account_id, symbol)
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

    def ack(self, account_id: str, signal_id: str, *, ticket: int = 0, ok: bool = True, message: str = "") -> bool:
        with self._lock:
            for key, row in list(self._pending.items()):
                if row.get("account_id") == account_id and row.get("signal_id") == signal_id:
                    row["acked"] = True
                    row["ack_ticket"] = ticket
                    row["ack_ok"] = ok
                    row["ack_message"] = message[:300]
                    row["acked_at_ms"] = int(time.time() * 1000)
                    self._acked.add(signal_id)
                    # drop after ack so EA does not re-read
                    self._pending.pop(key, None)
                    return True
        return False
