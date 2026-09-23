"""
Subscriber notification inbox + optional multi-channel delivery via AlertService.

Additive to SignalHistory (audit). Does not alter MT5/OHLC/executor trading logic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update, func

from app.db.base import async_session_factory
from app.db.models import Notification

logger = logging.getLogger("AEGIS.notifications")

# Default: do not spam HOLD/low-confidence to external channels
DEFAULT_MIN_CONFIDENCE_EXTERNAL = 0.55
ACTIONABLE_SIGNALS = {"BUY", "SELL"}


class NotificationService:
    def __init__(self, alert_service: Any | None = None) -> None:
        self._alerts = alert_service

    def set_alert_service(self, alert_service: Any) -> None:
        self._alerts = alert_service

    async def create(
        self,
        *,
        account_id: str,
        type: str,
        title: str,
        message: str,
        severity: str = "info",
        pair: str | None = None,
        signal: str | None = None,
        confidence: float | None = None,
        rule_name: str | None = None,
        details: str | None = None,
        deliver_external: bool | None = None,
        channels: list[str] | None = None,
        min_confidence_external: float = DEFAULT_MIN_CONFIDENCE_EXTERNAL,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = Notification(
            account_id=account_id,
            type=type,
            severity=severity,
            title=title[:240],
            message=message[:2000],
            pair=(pair or None),
            signal=(signal or None),
            confidence=confidence,
            rule_name=(rule_name or None),
            details=(details[:4000] if details else None),
            delivery_status="pending",
            delivery_channels=None,
            created_at=now,
        )
        async with async_session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            nid = row.id

        # External delivery (email/telegram/…) — ops + subscriber-facing when configured
        should = deliver_external
        if should is None:
            sig = (signal or "").upper()
            conf = float(confidence) if confidence is not None else 0.0
            should = sig in ACTIONABLE_SIGNALS and conf >= min_confidence_external
            if type.startswith("ORDER_") or type.startswith("POSITION_") or type.endswith("_ERROR"):
                should = True
            if type in ("MT5_DISCONNECTED", "OHLC_FEED_ERROR", "SERVER_OFFLINE", "SUBSCRIPTION_EXPIRING"):
                should = True

        delivery: dict[str, Any] = {}
        status = "inbox_only"
        if should and self._alerts is not None:
            try:
                delivery = await self._alerts.send(
                    title,
                    message,
                    severity=severity,
                    channels=channels,
                )
                status = "delivered" if any(v == "sent" for v in delivery.values()) else "attempted"
            except Exception as exc:  # noqa: BLE001
                logger.exception("external alert failed")
                delivery = {"error": str(exc)}
                status = "failed"

        ch_json = json.dumps(delivery) if delivery else None
        async with async_session_factory() as session:
            await session.execute(
                update(Notification)
                .where(Notification.id == nid)
                .values(delivery_status=status, delivery_channels=ch_json)
            )
            await session.commit()

        return {
            "id": nid,
            "account_id": account_id,
            "type": type,
            "severity": severity,
            "title": title,
            "message": message,
            "pair": pair,
            "signal": signal,
            "confidence": confidence,
            "rule_name": rule_name,
            "delivery_status": status,
            "created_at": now.isoformat(),
        }

    async def emit_signal(
        self,
        account_id: str,
        signal: str,
        confidence: float,
        rule_name: str,
        details: str,
        pair: str | None = None,
    ) -> dict[str, Any] | None:
        sig = (signal or "HOLD").upper()
        # Always inbox for BUY/SELL; HOLD only if confidence high enough to be interesting
        if sig == "HOLD" and float(confidence or 0) < 0.70:
            return None
        severity = "info"
        if sig in ("BUY", "SELL"):
            severity = "high"
        title = f"{sig} {pair or ''}".strip()
        message = f"{sig} · confidence={confidence:.0%} · rule={rule_name}"
        if details:
            message = f"{message}\n{details[:500]}"
        return await self.create(
            account_id=account_id,
            type="SIGNAL_GENERATED",
            title=title,
            message=message,
            severity=severity,
            pair=pair,
            signal=sig,
            confidence=float(confidence or 0),
            rule_name=rule_name,
            details=details,
        )

    async def emit_execution(
        self,
        account_id: str,
        *,
        signal_id: str,
        symbol: str,
        side: str,
        volume: float | None = None,
        ok: bool = True,
        message: str = "",
    ) -> dict[str, Any]:
        typ = "ORDER_FILLED" if ok else "ORDER_REJECTED"
        severity = "high" if ok else "critical"
        title = f"{'Filled' if ok else 'Rejected'}: {side} {symbol}"
        body = message or f"signal_id={signal_id} volume={volume}"
        return await self.create(
            account_id=account_id,
            type=typ,
            title=title,
            message=body,
            severity=severity,
            pair=symbol,
            signal=side,
            details=f"signal_id={signal_id}",
            deliver_external=True,
        )

    async def list_for_account(
        self,
        account_id: str,
        *,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 200)
        async with async_session_factory() as session:
            q = select(Notification).where(Notification.account_id == account_id)
            if unread_only:
                q = q.where(Notification.read_at.is_(None))
            q = q.order_by(Notification.created_at.desc()).limit(limit)
            rows = (await session.execute(q)).scalars().all()
            return [self._row(r) for r in rows]

    async def unread_count(self, account_id: str) -> int:
        async with async_session_factory() as session:
            q = (
                select(func.count())
                .select_from(Notification)
                .where(Notification.account_id == account_id, Notification.read_at.is_(None))
            )
            return int((await session.execute(q)).scalar() or 0)

    async def mark_read(self, account_id: str, notification_id: int) -> bool:
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            result = await session.execute(
                update(Notification)
                .where(
                    Notification.id == notification_id,
                    Notification.account_id == account_id,
                )
                .values(read_at=now)
            )
            await session.commit()
            return (result.rowcount or 0) > 0

    async def mark_all_read(self, account_id: str) -> int:
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            result = await session.execute(
                update(Notification)
                .where(Notification.account_id == account_id, Notification.read_at.is_(None))
                .values(read_at=now)
            )
            await session.commit()
            return int(result.rowcount or 0)

    async def acknowledge(self, account_id: str, notification_id: int) -> bool:
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            result = await session.execute(
                update(Notification)
                .where(
                    Notification.id == notification_id,
                    Notification.account_id == account_id,
                )
                .values(acknowledged_at=now, read_at=now)
            )
            await session.commit()
            return (result.rowcount or 0) > 0

    @staticmethod
    def _row(r: Notification) -> dict[str, Any]:
        return {
            "id": r.id,
            "account_id": r.account_id,
            "type": r.type,
            "severity": r.severity,
            "title": r.title,
            "message": r.message,
            "pair": r.pair,
            "signal": r.signal,
            "confidence": r.confidence,
            "rule_name": r.rule_name,
            "details": r.details,
            "delivery_status": r.delivery_status,
            "delivery_channels": r.delivery_channels,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "read_at": r.read_at.isoformat() if r.read_at else None,
            "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
            "unread": r.read_at is None,
        }
