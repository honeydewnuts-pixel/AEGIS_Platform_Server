"""Broker-confirmed position lifecycle (Stage 2.5 / Stage 3 verification).

Authoritative open risk is tied to broker-confirmed positions, not signal publication.
All keys are account-scoped: account_id + signal_id / account_id + position_ticket.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class PositionLifecycleService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._signals: dict[str, dict[str, Any]] = {}
        self._ticket_index: dict[tuple[str, int], str] = {}
        self._open_risk_recorded: set[str] = set()  # account|signal
        self._risk_released: set[str] = set()
        self._broker_sides: dict[str, dict[str, str]] = {}
        # account_id -> total risk tracked by this service (for reconcile)
        self._account_open_risk: dict[str, float] = {}
        self._accounting_failures: list[dict[str, Any]] = []

    def _sig_key(self, account_id: str, signal_id: str) -> str:
        return f"{(account_id or '').strip()}|{(signal_id or '').strip()}"

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
                row["state"] = "ORDER_SENT"
            row["updated_at"] = time.time()
            self._signals[k] = row

    def should_record_open_risk(self, account_id: str, signal_id: str) -> bool:
        with self._lock:
            k = self._sig_key(account_id, signal_id)
            if k in self._open_risk_recorded:
                return False
            row = self._signals.get(k) or {}
            return int(row.get("position_ticket") or 0) > 0

    def mark_open_risk_recorded(self, account_id: str, signal_id: str, risk_usd: float) -> None:
        with self._lock:
            k = self._sig_key(account_id, signal_id)
            self._open_risk_recorded.add(k)
            if k in self._signals:
                self._signals[k]["state"] = "POSITION_OPEN"
                self._signals[k]["risk_usd"] = float(risk_usd)
                self._signals[k]["open_risk_recorded"] = True
            self._account_open_risk[account_id] = float(
                self._account_open_risk.get(account_id, 0.0)
            ) + float(risk_usd)

    def on_broker_close(
        self,
        *,
        account_id: str,
        signal_id: str,
        position_ticket: int,
        symbol: str,
        risk_usd: float | None = None,
    ) -> tuple[float | None, str]:
        """Return (risk_to_release, status).

        Authoritative amount is server-recorded risk when available.
        Client-supplied risk_usd is ignored when server has a record.
        """
        with self._lock:
            if not signal_id and position_ticket:
                signal_id = self._ticket_index.get((account_id, position_ticket), "")
            k = self._sig_key(account_id, signal_id) if signal_id else ""
            if k and k in self._risk_released:
                return None, "ALREADY_RELEASED"
            row = self._signals.get(k) if k else None
            if row is not None and row.get("risk_usd") is not None:
                release = abs(float(row["risk_usd"]))
            elif k and k in self._open_risk_recorded:
                # recorded but amount missing — reconciliation required
                self._accounting_failures.append({
                    "type": "close_missing_risk_amount",
                    "account_id": account_id,
                    "signal_id": signal_id,
                    "ts": time.time(),
                })
                return None, "RECONCILIATION_REQUIRED"
            else:
                # No server record — do not trust client amount
                self._accounting_failures.append({
                    "type": "close_without_server_risk_record",
                    "account_id": account_id,
                    "signal_id": signal_id,
                    "client_risk": risk_usd,
                    "ts": time.time(),
                })
                return None, "RECONCILIATION_REQUIRED"

            if k:
                self._risk_released.add(k)
            if row is not None:
                row["state"] = "RISK_RELEASED"
                row["updated_at"] = time.time()
            if position_ticket:
                self._ticket_index.pop((account_id, position_ticket), None)
            self._account_open_risk[account_id] = max(
                0.0,
                float(self._account_open_risk.get(account_id, 0.0)) - release,
            )
            return release, "RISK_RELEASED"

    def get_signal_state(self, account_id: str, signal_id: str) -> str:
        with self._lock:
            row = self._signals.get(self._sig_key(account_id, signal_id))
            return str((row or {}).get("state") or "UNKNOWN")

    def record_accounting_failure(self, detail: dict[str, Any]) -> None:
        with self._lock:
            self._accounting_failures.append({**detail, "ts": time.time()})

    def reconcile_from_broker(
        self, account_id: str, positions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Rebuild sides + compute target open-risk from broker positions.

        Returns risk_delta_usd: positive = need to add to ledger, negative = release.
        """
        with self._lock:
            sides: dict[str, str] = {}
            live_tickets: set[int] = set()
            target_risk = 0.0
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
                # Prefer server risk for this ticket
                sig = self._ticket_index.get((account_id, t), "")
                k = self._sig_key(account_id, sig) if sig else ""
                row = self._signals.get(k) if k else None
                if row and row.get("risk_usd") is not None:
                    target_risk += abs(float(row["risk_usd"]))
                elif p.get("risk_usd") is not None:
                    try:
                        target_risk += abs(float(p["risk_usd"]))
                    except (TypeError, ValueError):
                        pass

            stale = [
                k for k in list(self._ticket_index)
                if k[0] == account_id and k[1] not in live_tickets
            ]
            released_stale = 0.0
            for tk in stale:
                sig = self._ticket_index.pop(tk, "")
                sk = self._sig_key(account_id, sig) if sig else ""
                if sk and sk not in self._risk_released:
                    row = self._signals.get(sk)
                    if row and row.get("risk_usd") is not None:
                        released_stale += abs(float(row["risk_usd"]))
                        self._risk_released.add(sk)
                        row["state"] = "RISK_RELEASED"
            current = float(self._account_open_risk.get(account_id, 0.0))
            # After stale release
            current = max(0.0, current - released_stale)
            risk_delta = target_risk - current
            self._account_open_risk[account_id] = target_risk
            self._broker_sides[account_id] = sides
            return {
                "account_id": account_id,
                "broker_positions": len(positions or []),
                "symbols": sorted(sides.keys()),
                "stale_tickets_cleared": len(stale),
                "stale_risk_released": released_stale,
                "target_open_risk_usd": target_risk,
                "previous_tracked_risk_usd": current + released_stale,
                "risk_delta_usd": risk_delta,
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
