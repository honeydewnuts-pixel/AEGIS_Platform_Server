"""Broker-confirmed position lifecycle (Stage 2.5).

Authoritative open risk is tied to broker-confirmed positions, not signal publication.

States:
  SIGNAL_GENERATED → SIGNAL_QUEUED → ORDER_SENT → BROKER_CONFIRMED_OPEN
  → POSITION_OPEN → POSITION_MODIFIED → POSITION_CLOSED → BROKER_CONFIRMED_CLOSE
  → RISK_RELEASED
"""
from __future__ import annotations

import threading
import time
from typing import Any


class PositionLifecycleService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # signal_id -> state dict
        self._signals: dict[str, dict[str, Any]] = {}
        # (account_id, position_ticket) -> signal_id
        self._ticket_index: dict[tuple[str, int], str] = {}
        # signal_ids that already recorded open risk
        self._open_risk_recorded: set[str] = set()
        # signal_ids that already released risk
        self._risk_released: set[str] = set()
        # account_id -> {symbol: side} derived from last reconcile
        self._broker_sides: dict[str, dict[str, str]] = {}

    def _sig_key(self, account_id: str, signal_id: str) -> str:
        return f"{account_id}|{signal_id}"

    def on_queued(self, account_id: str, signal_id: str, symbol: str, side: str) -> None:
        with self._lock:
            k = self._sig_key(account_id, signal_id)
            self._signals[k] = {
                "account_id": account_id,
                "signal_id": signal_id,
                "symbol": symbol,
                "side": side,
                "state": "SIGNAL_QUEUED",
                "updated_at": time.time(),
            }

    def on_ack(
        self,
        *,
        account_id: str,
        signal_id: str,
        ok: bool,
        position_ticket: int,
        order_ticket: int,
        deal_ticket: int,
        symbol: str,
        side: str,
        volume: float,
        risk_usd: float | None,
        idempotent: bool,
    ) -> None:
        with self._lock:
            k = self._sig_key(account_id, signal_id)
            row = self._signals.get(k) or {
                "account_id": account_id,
                "signal_id": signal_id,
                "symbol": symbol,
                "side": side,
            }
            if idempotent:
                return
            row["order_ticket"] = order_ticket
            row["deal_ticket"] = deal_ticket
            row["position_ticket"] = position_ticket
            row["volume"] = volume
            if risk_usd is not None:
                row["risk_usd"] = float(risk_usd)
            if not ok:
                row["state"] = "ORDER_REJECTED"
            elif position_ticket > 0:
                row["state"] = "BROKER_CONFIRMED_OPEN"
                self._ticket_index[(account_id, position_ticket)] = signal_id
            else:
                # ACK without position ticket = order path only
                row["state"] = "ORDER_SENT"
            row["updated_at"] = time.time()
            self._signals[k] = row

    def should_record_open_risk(self, account_id: str, signal_id: str) -> bool:
        with self._lock:
            if signal_id in self._open_risk_recorded:
                return False
            k = self._sig_key(account_id, signal_id)
            row = self._signals.get(k) or {}
            return int(row.get("position_ticket") or 0) > 0

    def mark_open_risk_recorded(self, account_id: str, signal_id: str, risk_usd: float) -> None:
        with self._lock:
            self._open_risk_recorded.add(signal_id)
            k = self._sig_key(account_id, signal_id)
            if k in self._signals:
                self._signals[k]["state"] = "POSITION_OPEN"
                self._signals[k]["risk_usd"] = float(risk_usd)
                self._signals[k]["open_risk_recorded"] = True

    def on_broker_close(
        self,
        *,
        account_id: str,
        signal_id: str,
        position_ticket: int,
        symbol: str,
        risk_usd: float | None,
    ) -> float | None:
        """Return risk USD to release, or None if already released / unknown."""
        with self._lock:
            if not signal_id and position_ticket:
                signal_id = self._ticket_index.get((account_id, position_ticket), "")
            if signal_id and signal_id in self._risk_released:
                return None
            k = self._sig_key(account_id, signal_id) if signal_id else ""
            row = self._signals.get(k) if k else None
            release = None
            if risk_usd is not None:
                release = abs(float(risk_usd))
            elif row and row.get("risk_usd") is not None:
                release = abs(float(row["risk_usd"]))
            if signal_id:
                self._risk_released.add(signal_id)
            if row is not None:
                row["state"] = "RISK_RELEASED" if release else "BROKER_CONFIRMED_CLOSE"
                row["updated_at"] = time.time()
            if position_ticket:
                self._ticket_index.pop((account_id, position_ticket), None)
            return release

    def get_signal_state(self, account_id: str, signal_id: str) -> str:
        with self._lock:
            row = self._signals.get(self._sig_key(account_id, signal_id))
            return str((row or {}).get("state") or "UNKNOWN")

    def reconcile_from_broker(
        self, account_id: str, positions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Rebuild broker-side map; clear tickets not present at broker."""
        with self._lock:
            sides: dict[str, str] = {}
            live_tickets: set[int] = set()
            for p in positions or []:
                if not isinstance(p, dict):
                    continue
                sym = str(p.get("symbol") or "").upper().split(".")[0]
                side = str(p.get("side") or p.get("type") or "").upper()
                if side in ("BUY", "LONG"):
                    side = "BUY"
                elif side in ("SELL", "SHORT"):
                    side = "SELL"
                else:
                    continue
                if sym:
                    sides[sym] = side
                try:
                    t = int(p.get("position_ticket") or p.get("ticket") or 0)
                except (TypeError, ValueError):
                    t = 0
                if t > 0:
                    live_tickets.add(t)
            # Drop index entries for vanished tickets
            stale = [
                k for k in self._ticket_index
                if k[0] == account_id and k[1] not in live_tickets
            ]
            for k in stale:
                del self._ticket_index[k]
            self._broker_sides[account_id] = sides
            return {
                "account_id": account_id,
                "broker_positions": len(positions or []),
                "symbols": sorted(sides.keys()),
                "stale_tickets_cleared": len(stale),
            }

    def broker_side(self, account_id: str, symbol: str) -> str | None:
        with self._lock:
            return (self._broker_sides.get(account_id) or {}).get(
                symbol.strip().upper().split(".")[0]
            )


_singleton: PositionLifecycleService | None = None


def get_lifecycle_service() -> PositionLifecycleService:
    global _singleton
    if _singleton is None:
        _singleton = PositionLifecycleService()
    return _singleton
