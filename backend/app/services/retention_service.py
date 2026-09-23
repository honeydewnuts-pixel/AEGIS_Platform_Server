"""Purge old audit + upload diagnostic + notification rows per retention policy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import settings
from app.db.base import async_session_factory
from app.db.models import AuditEvent, UploadDiagnostic, Notification
from app.core.logging import configure_logging

logger = configure_logging(__name__)


async def purge_old_records() -> dict[str, int]:
    days = int(getattr(settings, "AUDIT_RETENTION_DAYS", 90) or 90)
    notif_days = int(getattr(settings, "NOTIFICATION_RETENTION_DAYS", 90) or 90)
    counts = {"audit": 0, "uploads": 0, "notifications": 0}
    async with async_session_factory() as session:
        if days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            a = await session.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
            u = await session.execute(delete(UploadDiagnostic).where(UploadDiagnostic.created_at < cutoff))
            counts["audit"] = a.rowcount or 0
            counts["uploads"] = u.rowcount or 0
        if notif_days > 0:
            ncut = datetime.now(timezone.utc) - timedelta(days=notif_days)
            n = await session.execute(delete(Notification).where(Notification.created_at < ncut))
            counts["notifications"] = n.rowcount or 0
        await session.commit()
    if any(counts.values()):
        logger.info("Retention purge: %s", counts)
    return counts
