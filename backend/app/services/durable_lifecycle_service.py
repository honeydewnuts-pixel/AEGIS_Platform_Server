"""Durable AEGIS position lifecycle (DB-backed, account-scoped, idempotent)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AegisPositionLifecycle


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DurableLifecycleService:
    """Persist lifecycle rows; never invent risk amounts."""

    async def upsert_queued(
        self, session: AsyncSession, *, account_id: str, signal_id: str, symbol: str, side: str
    ) -> AegisPositionLifecycle:
        row = await self._get(session, account_id, signal_id)
        now = _utcnow()
        if row is None:
            row = AegisPositionLifecycle(
                account_id=account_id,
                signal_id=signal_id,
                symbol=symbol or "",
                side=side or "",
                state="SIGNAL_QUEUED",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            if row.state in ("RISK_RELEASED", "POSITION_CLOSED"):
                return row
            row.symbol = symbol or row.symbol
            row.side = side or row.side
            if row.state == "SIGNAL_QUEUED":
                pass
            row.updated_at = now
        await session.flush()
        return row

    async def on_ack(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        signal_id: str,
        ok: bool,
        position_ticket: int,
        order_ticket: int,
        deal_ticket: int,
        symbol: str,
        side: str,
        volume: float | None,
        risk_usd: float | None,
    ) -> tuple[AegisPositionLifecycle | None, bool]:
        """Returns (row, should_record_open_risk). Idempotent on already-open."""
        row = await self._get(session, account_id, signal_id)
        now = _utcnow()
        if row is None:
            row = AegisPositionLifecycle(
                account_id=account_id,
                signal_id=signal_id,
                symbol=symbol or "",
                side=side or "",
                state="ORDER_SENT",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        if row.state in ("POSITION_OPEN", "BROKER_CONFIRMED_OPEN") and int(row.position_ticket or 0) > 0:
            return row, False  # already recorded
        if row.state == "RISK_RELEASED":
            return row, False
        row.order_ticket = order_ticket or row.order_ticket
        row.deal_ticket = deal_ticket or row.deal_ticket
        row.symbol = symbol or row.symbol
        row.side = side or row.side
        if volume is not None:
            row.volume = float(volume)
        if risk_usd is not None and row.risk_usd_at_open is None:
            row.risk_usd_at_open = float(risk_usd)
        if not ok:
            row.state = "ORDER_REJECTED"
            row.updated_at = now
            await session.flush()
            return row, False
        if position_ticket > 0:
            row.position_ticket = int(position_ticket)
            if row.risk_usd_at_open is not None:
                row.state = "POSITION_OPEN"
                row.opened_at = row.opened_at or now
                row.updated_at = now
                await session.flush()
                return row, True
            row.state = "BROKER_CONFIRMED_OPEN"
            row.opened_at = row.opened_at or now
            row.updated_at = now
            await session.flush()
            # Confirmed open but no risk amount → reconciliation required
            return row, False
        row.state = "ORDER_SENT"
        row.updated_at = now
        await session.flush()
        return row, False

    async def mark_risk_recorded(
        self, session: AsyncSession, *, account_id: str, signal_id: str, risk_usd: float
    ) -> None:
        """Mark portfolio open-risk as applied for this lifecycle row (idempotent)."""
        row = await self._get(session, account_id, signal_id)
        if row is None:
            return
        if row.state == "RISK_RELEASED":
            return
        row.risk_usd_at_open = float(risk_usd)
        row.open_risk_applied = True
        row.state = "POSITION_OPEN"
        row.opened_at = row.opened_at or _utcnow()
        row.updated_at = _utcnow()
        await session.flush()

    async def on_close(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        signal_id: str,
        position_ticket: int,
        symbol: str,
        close_reason: str | None,
    ) -> tuple[float | None, str]:
        """Release using server risk only. Returns (amount, status).

        Concurrent-safe: SELECT ... FOR UPDATE then conditional state transition.
        Only the first transition to RISK_RELEASED returns the risk amount.
        """
        from sqlalchemy import select, and_

        row = None
        if signal_id:
            q = await session.execute(
                select(AegisPositionLifecycle)
                .where(
                    and_(
                        AegisPositionLifecycle.account_id == account_id,
                        AegisPositionLifecycle.signal_id == signal_id,
                    )
                )
                .with_for_update()
            )
            row = q.scalar_one_or_none()
        if row is None and position_ticket:
            q = await session.execute(
                select(AegisPositionLifecycle)
                .where(
                    and_(
                        AegisPositionLifecycle.account_id == account_id,
                        AegisPositionLifecycle.position_ticket == int(position_ticket),
                    )
                )
                .with_for_update()
            )
            row = q.scalar_one_or_none()
        if row is None:
            return None, "RECONCILIATION_REQUIRED"
        if row.state == "RISK_RELEASED":
            return None, "ALREADY_RELEASED"
        if row.risk_usd_at_open is None:
            row.state = "RECONCILIATION_REQUIRED"
            row.updated_at = _utcnow()
            await session.flush()
            return None, "RECONCILIATION_REQUIRED"
        # Atomic logical transition under row lock
        # Only return amount if portfolio open-risk was actually applied
        amount = abs(float(row.risk_usd_at_open)) if bool(getattr(row, "open_risk_applied", False)) else None
        row.state = "RISK_RELEASED"
        row.closed_at = _utcnow()
        row.close_reason = (close_reason or "")[:64] or None
        if position_ticket:
            row.position_ticket = int(position_ticket)
        if symbol:
            row.symbol = symbol
        row.updated_at = _utcnow()
        await session.flush()
        return amount, "RISK_RELEASED"

    _OPEN_STATES = (
        "BROKER_CONFIRMED_OPEN",
        "POSITION_OPEN",
        "ORDER_SENT",
        "RECONCILIATION_REQUIRED",
    )

    async def list_open(self, session: AsyncSession, account_id: str) -> list[AegisPositionLifecycle]:
        q = await session.execute(
            select(AegisPositionLifecycle).where(
                and_(
                    AegisPositionLifecycle.account_id == account_id,
                    AegisPositionLifecycle.state.in_(list(self._OPEN_STATES)),
                )
            )
        )
        return list(q.scalars().all())

    async def list_open_for_update(
        self, session: AsyncSession, account_id: str
    ) -> list[AegisPositionLifecycle]:
        """Same as list_open but locks rows until the transaction ends."""
        q = await session.execute(
            select(AegisPositionLifecycle)
            .where(
                and_(
                    AegisPositionLifecycle.account_id == account_id,
                    AegisPositionLifecycle.state.in_(list(self._OPEN_STATES)),
                )
            )
            .with_for_update()
        )
        return list(q.scalars().all())

    async def reconcile(
        self, session: AsyncSession, account_id: str, broker_positions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Broker authoritative for existence; durable records hold risk amounts.

        Concurrent-safe: open lifecycle rows are locked with SELECT FOR UPDATE.
        Only the transaction that transitions a row to RISK_RELEASED contributes
        its risk_usd_at_open to stale_risk_released. A second concurrent reconcile
        waits on the lock, then observes RISK_RELEASED and contributes zero.
        """
        open_rows = await self.list_open_for_update(session, account_id)
        live_tickets: set[int] = set()
        broker_by_ticket: dict[int, dict] = {}
        for p in broker_positions or []:
            try:
                t = int(p.get("position_ticket") or p.get("ticket") or 0)
            except (TypeError, ValueError):
                t = 0
            if t > 0:
                live_tickets.add(t)
                broker_by_ticket[t] = p

        released = 0.0
        recon_required = 0
        confirmed = 0
        open_risk_recovered = 0.0
        recovered_signal_ids: list[str] = []
        now = _utcnow()
        for row in open_rows:
            # Re-check under lock — another txn may have released while we waited
            if row.state == "RISK_RELEASED":
                continue
            pt = int(row.position_ticket or 0)
            if pt > 0 and pt not in live_tickets:
                if row.risk_usd_at_open is not None:
                    # Only release portfolio risk if it was previously applied
                    if bool(getattr(row, "open_risk_applied", False)):
                        released += abs(float(row.risk_usd_at_open))
                    row.state = "RISK_RELEASED"
                    row.closed_at = now
                    row.close_reason = row.close_reason or "broker_absent_on_reconcile"
                    row.updated_at = now
                else:
                    row.state = "RECONCILIATION_REQUIRED"
                    row.updated_at = now
                    recon_required += 1
            elif pt > 0 and pt in live_tickets:
                confirmed += 1
                if row.state in ("ORDER_SENT", "BROKER_CONFIRMED_OPEN") and row.risk_usd_at_open is not None:
                    row.state = "POSITION_OPEN"
                    row.updated_at = now
                # Stage 6.4A: restore missing portfolio open-risk exactly once
                if (
                    row.risk_usd_at_open is not None
                    and not bool(getattr(row, "open_risk_applied", False))
                    and row.state not in ("RISK_RELEASED",)
                ):
                    amt = abs(float(row.risk_usd_at_open))
                    row.open_risk_applied = True
                    if row.state != "POSITION_OPEN":
                        row.state = "POSITION_OPEN"
                    row.updated_at = now
                    open_risk_recovered += amt
                    recovered_signal_ids.append(str(row.signal_id or ""))
            elif pt == 0 and row.state in ("ORDER_SENT", "SIGNAL_QUEUED"):
                pass

        durable_tickets = {
            int(r.position_ticket or 0)
            for r in open_rows
            if r.position_ticket and r.state != "RISK_RELEASED"
        }
        unknown_broker_tickets: list[int] = []
        for t, p in broker_by_ticket.items():
            if t not in durable_tickets:
                sid = str(p.get("signal_id") or "")
                if sid:
                    # Lock the candidate row if present
                    q = await session.execute(
                        select(AegisPositionLifecycle)
                        .where(
                            and_(
                                AegisPositionLifecycle.account_id == account_id,
                                AegisPositionLifecycle.signal_id == sid,
                            )
                        )
                        .with_for_update()
                    )
                    existing = q.scalar_one_or_none()
                    if existing and existing.risk_usd_at_open is not None:
                        if existing.state != "RISK_RELEASED":
                            existing.position_ticket = t
                            existing.state = "POSITION_OPEN"
                            existing.updated_at = now
                            confirmed += 1
                        continue
                # Broker ticket not linked to durable AEGIS lifecycle → exception, do not auto-adopt
                unknown_broker_tickets.append(t)
                recon_required += 1

        await session.flush()
        return {
            "account_id": account_id,
            "broker_positions": len(broker_positions or []),
            "stale_risk_released": released,
            "open_risk_recovered": open_risk_recovered,
            "recovered_signal_ids": recovered_signal_ids,
            "confirmed_open": confirmed,
            "reconciliation_required_count": recon_required,
            "unknown_broker_tickets": unknown_broker_tickets,
            "unknown_positions_not_auto_adopted": True,
        }

    async def _get(
        self, session: AsyncSession, account_id: str, signal_id: str
    ) -> AegisPositionLifecycle | None:
        q = await session.execute(
            select(AegisPositionLifecycle).where(
                and_(
                    AegisPositionLifecycle.account_id == account_id,
                    AegisPositionLifecycle.signal_id == signal_id,
                )
            )
        )
        return q.scalar_one_or_none()

    async def _get_by_ticket(
        self, session: AsyncSession, account_id: str, position_ticket: int
    ) -> AegisPositionLifecycle | None:
        q = await session.execute(
            select(AegisPositionLifecycle).where(
                and_(
                    AegisPositionLifecycle.account_id == account_id,
                    AegisPositionLifecycle.position_ticket == int(position_ticket),
                )
            )
        )
        return q.scalar_one_or_none()
