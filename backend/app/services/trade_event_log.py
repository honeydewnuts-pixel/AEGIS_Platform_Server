"""Trade-event log — signal_id follows market data → ACK.

Stages (ordered):
  market_data, analysis, signal_generated, risk_check, queued,
  executor_poll, order_submit, broker_result, ack, notification

Does not invent strategy signals. Records what the platform already does.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


STAGES = (
    "market_data",
    "analysis",
    "signal_generated",
    "risk_check",
    "queued",
    "executor_poll",
    "order_submit",
    "broker_result",
    "ack",
    "notification",
)


class TradeEventLog:
    def __init__(self, max_events: int = 2000) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        # signal_id -> ordered stage events
        self._by_signal: dict[str, list[dict[str, Any]]] = {}
        self._max_per_signal = 40

    def record(
        self,
        *,
        stage: str,
        account_id: str,
        status: str,
        signal_id: str | None = None,
        symbol: str = "",
        detail: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ev = {
            "ts_ms": int(time.time() * 1000),
            "stage": stage,
            "status": status,
            "account_id": (account_id or "").strip(),
            "signal_id": signal_id or "",
            "symbol": (symbol or "").upper(),
            "detail": (detail or "")[:500],
            "extra": extra or {},
        }
        with self._lock:
            self._events.appendleft(ev)
            if signal_id:
                lst = self._by_signal.setdefault(signal_id, [])
                lst.append(ev)
                if len(lst) > self._max_per_signal:
                    self._by_signal[signal_id] = lst[-self._max_per_signal :]
        return ev

    def for_account(self, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
        aid = (account_id or "").strip()
        with self._lock:
            out = [e for e in self._events if e["account_id"] == aid]
        return out[: max(1, min(limit, 500))]

    def for_signal(self, signal_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._by_signal.get(signal_id or "", []))

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)[: max(1, min(limit, 500))]
