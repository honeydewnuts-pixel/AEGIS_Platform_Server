"""Pending signals for MT5 AEGIS_Executor — idempotent by signal_id.

Once a signal_id is successfully ACK'd (or permanently failed ACK), it is never
re-issued. Duplicate ACKs are accepted (idempotent).
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from app.utils.symbol_normalize import normalize_symbol


class ExecutorSignalService:
    def __init__(self, max_age_sec: float = 300.0, completed_ttl_sec: float = 86400.0) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}  # account|symbol -> payload
        self._completed: dict[str, dict[str, Any]] = {}  # signal_id -> audit
        self._recent: list[dict[str, Any]] = []  # last N execution events for clients
        self.max_age_sec = max_age_sec
        self.completed_ttl_sec = completed_ttl_sec

    @staticmethod
    def _key(account_id: str, symbol: str) -> str:
        return f"{account_id.strip()}|{normalize_symbol(symbol)}"

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return normalize_symbol(symbol)

    def _prune_completed(self) -> None:
        now = time.time()
        dead = [
            sid
            for sid, meta in self._completed.items()
            if now - float(meta.get("completed_at", 0)) > self.completed_ttl_sec
        ]
        for sid in dead:
            self._completed.pop(sid, None)

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
        key = self._key(account_id, symbol)
        now = int(time.time() * 1000)
        with self._lock:
            self._prune_completed()
            row = self._pending.get(key)
            if not row:
                return None
            sid = row.get("signal_id")
            if sid and sid in self._completed:
                self._pending.pop(key, None)
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
        order_ticket: int = 0,
        deal_ticket: int = 0,
        position_ticket: int = 0,
        retcode: int = 0,
        ok: bool = True,
        message: str = "",
        symbol: str = "",
        side: str = "",
        volume: float = 0.0,
    ) -> dict[str, Any]:
        """Idempotent ACK. Returns status dict."""
        with self._lock:
            self._prune_completed()
            # Already completed → idempotent success
            if signal_id in self._completed:
                prev = self._completed[signal_id]
                return {
                    "acked": True,
                    "idempotent": True,
                    "signal_id": signal_id,
                    **{k: prev.get(k) for k in ("order_ticket", "deal_ticket", "position_ticket", "ok")},
                }

            found_key = None
            row = None
            for key, r in self._pending.items():
                if r.get("account_id") == account_id and r.get("signal_id") == signal_id:
                    found_key = key
                    row = r
                    break

            audit = {
                "signal_id": signal_id,
                "account_id": account_id,
                "order_ticket": order_ticket or ticket,
                "deal_ticket": deal_ticket,
                "position_ticket": position_ticket,
                "retcode": retcode,
                "ok": ok,
                "message": (message or "")[:300],
                "symbol": symbol or (row or {}).get("symbol", ""),
                "side": side or (row or {}).get("side", ""),
                "volume": volume,
                "completed_at": time.time(),
                "completed_at_ms": int(time.time() * 1000),
            }
            self._completed[signal_id] = audit
            if found_key:
                self._pending.pop(found_key, None)
            if ok:
                self._recent.insert(0, dict(audit))
                self._recent = self._recent[:100]
            return {"acked": True, "idempotent": False, "signal_id": signal_id, **audit}

    def recent_executions(self, account_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = [r for r in self._recent if r.get("account_id") == account_id]
            return rows[:limit]
