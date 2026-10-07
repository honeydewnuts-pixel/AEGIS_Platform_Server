"""Stage 6 — durable operational controls (emergency stop, etc.).

Emergency stop blocks NEW executions only. Existing positions continue management.
Survives API restart. Does not alter production_authorized.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AegisOperationalControl, AuditEvent

KEY_EMERGENCY_STOP = "emergency_stop"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperationalControlService:
    async def get(self, session: AsyncSession, key: str) -> str | None:
        q = await session.execute(
            select(AegisOperationalControl).where(AegisOperationalControl.key == key)
        )
        row = q.scalar_one_or_none()
        return None if row is None else str(row.value or "")

    async def is_emergency_stop_on(self, session: AsyncSession) -> bool:
        val = await self.get(session, KEY_EMERGENCY_STOP)
        if val is None:
            return False  # default OFF; missing key is not ON
        return val.strip().lower() in ("1", "true", "on", "yes")

    async def set_emergency_stop(
        self,
        session: AsyncSession,
        *,
        enabled: bool,
        actor: str = "system",
        ip: str | None = None,
    ) -> dict[str, Any]:
        now = _utcnow()
        q = await session.execute(
            select(AegisOperationalControl).where(AegisOperationalControl.key == KEY_EMERGENCY_STOP)
        )
        row = q.scalar_one_or_none()
        new_val = "true" if enabled else "false"
        if row is None:
            row = AegisOperationalControl(
                key=KEY_EMERGENCY_STOP,
                value=new_val,
                updated_at=now,
                updated_by=actor[:128] if actor else None,
            )
            session.add(row)
        else:
            row.value = new_val
            row.updated_at = now
            row.updated_by = actor[:128] if actor else None
        action = "EMERGENCY_STOP_ENABLED" if enabled else "EMERGENCY_STOP_DISABLED"
        session.add(
            AuditEvent(
                created_at=now,
                actor_type="admin_key" if actor and actor != "system" else "system",
                actor_id=actor,
                action=action,
                target_type="operational_control",
                target_id=KEY_EMERGENCY_STOP,
                detail=f"emergency_stop={new_val}",
                ip=ip,
                success=True,
            )
        )
        await session.flush()
        return {
            "emergency_stop": enabled,
            "value": new_val,
            "updated_at": now.isoformat(),
            "updated_by": actor,
            "production_authorized": False,
        }

    async def status(self, session: AsyncSession) -> dict[str, Any]:
        on = await self.is_emergency_stop_on(session)
        q = await session.execute(
            select(AegisOperationalControl).where(AegisOperationalControl.key == KEY_EMERGENCY_STOP)
        )
        row = q.scalar_one_or_none()
        return {
            "emergency_stop": on,
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
            "updated_by": row.updated_by if row else None,
            "production_authorized": False,
            "note": "emergency_stop blocks NEW orders only; open positions continue management",
        }


def get_operational_control_service() -> OperationalControlService:
    return OperationalControlService()
