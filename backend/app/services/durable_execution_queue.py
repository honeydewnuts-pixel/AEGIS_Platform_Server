"""Stage 5 — durable authorized execution queue (restart-safe).

Only rows that pass ExecutorSignalService.is_execution_authorized may be inserted.
Research methodologies are rejected at the boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AegisExecutionQueue
from app.services.executor_signal_service import ExecutorSignalService
from app.utils.symbol_normalize import normalize_symbol

TERMINAL = frozenset({"ACKED", "REJECTED", "EXPIRED"})
CLAIM_LEASE_SEC = 120.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DurableExecutionQueueService:
    """DB-backed pending execution records."""

    async def enqueue(self, session: AsyncSession, payload: dict[str, Any]) -> AegisExecutionQueue | None:
        """Insert authorized pending row. Rejects unauthorized/research."""
        if not ExecutorSignalService.is_execution_authorized(payload):
            return None
        signal_id = str(payload.get("signal_id") or "")
        account_id = str(payload.get("account_id") or "")
        symbol = normalize_symbol(str(payload.get("symbol") or ""))
        if not signal_id or not account_id or not symbol:
            return None
        # Expire any prior PENDING for same account+symbol (one active pending)
        now = _utcnow()
        q = await session.execute(
            select(AegisExecutionQueue).where(
                and_(
                    AegisExecutionQueue.account_id == account_id,
                    AegisExecutionQueue.symbol == symbol,
                    AegisExecutionQueue.status.in_(["PENDING", "CLAIMED"]),
                )
            )
        )
        for old in q.scalars().all():
            old.status = "EXPIRED"
            old.updated_at = now
        row = AegisExecutionQueue(
            signal_id=signal_id,
            account_id=account_id,
            symbol=symbol,
            side=str(payload.get("side") or "").upper(),
            volume=payload.get("volume"),
            stop_loss=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
            atr14=payload.get("atr14"),
            initial_stop_atr_mult=payload.get("initial_stop_atr_mult"),
            max_hold_bars=payload.get("max_hold_bars"),
            trail_atr_mult=payload.get("trail_atr_mult"),
            methodology=str(payload.get("methodology") or "")[:64],
            rule_name=str(payload.get("rule_name") or "")[:128],
            risk_usd_at_open=payload.get("risk_usd_at_open"),
            production_authorized=bool(payload.get("production_authorized")),
            controlled_demo_authorized=bool(payload.get("controlled_demo_authorized")),
            status="PENDING",
            attempt_count=0,
            details=(str(payload.get("details") or "")[:500] or None),
            confidence=payload.get("confidence"),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        return row

    def _to_payload(self, row: AegisExecutionQueue) -> dict[str, Any]:
        return {
            "signal_id": row.signal_id,
            "account_id": row.account_id,
            "symbol": row.symbol,
            "side": row.side,
            "confidence": float(row.confidence or 0),
            "rule_name": row.rule_name or "",
            "volume": row.volume,
            "stop_loss": row.stop_loss,
            "take_profit": row.take_profit,
            "details": row.details or "",
            "created_at_ms": int(row.created_at.timestamp() * 1000) if row.created_at else 0,
            "acked": row.status in TERMINAL,
            "atr14": row.atr14,
            "initial_stop_atr_mult": row.initial_stop_atr_mult,
            "max_hold_bars": row.max_hold_bars if row.max_hold_bars is not None else 72,
            "trail_atr_mult": row.trail_atr_mult if row.trail_atr_mult is not None else 0.75,
            "methodology": row.methodology or "",
            "risk_usd_at_open": row.risk_usd_at_open,
            "production_authorized": bool(row.production_authorized),
            "controlled_demo_authorized": bool(row.controlled_demo_authorized),
            "queue_status": row.status,
            "durable": True,
        }

    async def get_pending(
        self, session: AsyncSession, account_id: str, symbol: str
    ) -> dict[str, Any] | None:
        sym = normalize_symbol(symbol)
        q = await session.execute(
            select(AegisExecutionQueue)
            .where(
                and_(
                    AegisExecutionQueue.account_id == account_id,
                    AegisExecutionQueue.symbol == sym,
                    AegisExecutionQueue.status.in_(["PENDING", "CLAIMED"]),
                )
            )
            .order_by(AegisExecutionQueue.created_at.desc())
            .limit(1)
        )
        row = q.scalar_one_or_none()
        if row is None:
            return None
        # Lease recovery: CLAIMED too long → PENDING again
        if row.status == "CLAIMED" and row.claimed_at is not None:
            age = (_utcnow() - row.claimed_at).total_seconds()
            if age > CLAIM_LEASE_SEC:
                row.status = "PENDING"
                row.claim_token = None
                row.claimed_at = None
                row.updated_at = _utcnow()
                await session.flush()
        payload = self._to_payload(row)
        if not ExecutorSignalService.is_execution_authorized(payload):
            row.status = "EXPIRED"
            row.updated_at = _utcnow()
            await session.flush()
            return None
        return payload

    async def claim(
        self, session: AsyncSession, account_id: str, signal_id: str, claim_token: str
    ) -> bool:
        """Mark PENDING → CLAIMED for single-executor safety."""
        q = await session.execute(
            select(AegisExecutionQueue)
            .where(
                and_(
                    AegisExecutionQueue.account_id == account_id,
                    AegisExecutionQueue.signal_id == signal_id,
                    AegisExecutionQueue.status == "PENDING",
                )
            )
            .with_for_update()
        )
        row = q.scalar_one_or_none()
        if row is None:
            return False
        row.status = "CLAIMED"
        row.claim_token = claim_token
        row.claimed_at = _utcnow()
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.updated_at = _utcnow()
        await session.flush()
        return True

    async def ack(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        signal_id: str,
        ok: bool,
        position_ticket: int = 0,
        order_ticket: int = 0,
        deal_ticket: int = 0,
        message: str = "",
    ) -> dict[str, Any]:
        """Idempotent terminal transition to ACKED/REJECTED."""
        q = await session.execute(
            select(AegisExecutionQueue)
            .where(
                and_(
                    AegisExecutionQueue.account_id == account_id,
                    AegisExecutionQueue.signal_id == signal_id,
                )
            )
            .with_for_update()
        )
        row = q.scalar_one_or_none()
        if row is None:
            return {"ok": True, "idempotent": True, "found": False}
        if row.status in TERMINAL:
            return {"ok": True, "idempotent": True, "found": True, "status": row.status}
        row.status = "ACKED" if ok else "REJECTED"
        row.ack_ok = bool(ok)
        row.ack_message = (message or "")[:256] or None
        if position_ticket:
            row.position_ticket = int(position_ticket)
        if order_ticket:
            row.order_ticket = int(order_ticket)
        if deal_ticket:
            row.deal_ticket = int(deal_ticket)
        row.updated_at = _utcnow()
        await session.flush()
        return {"ok": True, "idempotent": False, "found": True, "status": row.status}


def get_durable_execution_queue() -> DurableExecutionQueueService:
    return DurableExecutionQueueService()
