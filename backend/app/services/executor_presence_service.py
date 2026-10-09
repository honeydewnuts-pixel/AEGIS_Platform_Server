"""Durable AEGIS_Executor presence / last_seen (Stage 6.2I).

Orthogonal to trading: heartbeat must never enqueue, claim, ACK, or size orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AegisExecutorPresence

# Healthy if last_seen within this window (heartbeat default ~30s)
DEFAULT_STALE_AFTER_SEC = 90.0
ALLOWED_CLIENT_TYPES = frozenset({"AEGIS_Executor"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExecutorPresenceService:
    async def upsert_heartbeat(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        client_type: str = "AEGIS_Executor",
        executor_version: str = "",
        execution_mode: str = "",
        chart_symbol: str | None = None,
    ) -> dict[str, Any]:
        aid = (account_id or "").strip()
        if not aid:
            raise ValueError("account_id required")
        ct = (client_type or "AEGIS_Executor").strip() or "AEGIS_Executor"
        if ct not in ALLOWED_CLIENT_TYPES:
            # Normalize unknown to canonical for safety (still authenticated)
            ct = "AEGIS_Executor"
        now = _utcnow()
        q = await session.execute(
            select(AegisExecutorPresence).where(AegisExecutorPresence.account_id == aid)
        )
        row = q.scalar_one_or_none()
        if row is None:
            row = AegisExecutorPresence(
                account_id=aid,
                client_type=ct,
                executor_version=(executor_version or "")[:32],
                execution_mode=(execution_mode or "")[:32],
                last_symbol=(chart_symbol or None),
                last_seen_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.client_type = ct
            row.executor_version = (executor_version or "")[:32]
            row.execution_mode = (execution_mode or "")[:32]
            if chart_symbol:
                row.last_symbol = str(chart_symbol)[:64]
            row.last_seen_at = now
            row.updated_at = now
        await session.flush()
        return {
            "ok": True,
            "account_id": aid,
            "last_seen_at": now.isoformat(),
            "client_type": ct,
        }

    async def get_status(
        self,
        session: AsyncSession,
        account_id: str,
        *,
        stale_after_sec: float = DEFAULT_STALE_AFTER_SEC,
    ) -> dict[str, Any]:
        aid = (account_id or "").strip()
        now = _utcnow()
        base = {
            "ok": True,
            "account_id": aid,
            "exists": False,
            "client_type": None,
            "executor_version": None,
            "execution_mode": None,
            "last_symbol": None,
            "last_seen_at": None,
            "age_sec": None,
            "healthy": False,
            "stale_after_sec": float(stale_after_sec),
            "server_time": now.isoformat(),
            "source": "durable_presence",
            "note": "Distinct from mobile devices and Python worker_registry",
        }
        if not aid:
            return base
        q = await session.execute(
            select(AegisExecutorPresence).where(AegisExecutorPresence.account_id == aid)
        )
        row = q.scalar_one_or_none()
        if row is None:
            return base
        seen = row.last_seen_at
        if seen is not None and seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        age = (now - seen).total_seconds() if seen else None
        healthy = age is not None and age <= float(stale_after_sec)
        return {
            **base,
            "exists": True,
            "client_type": row.client_type,
            "executor_version": row.executor_version,
            "execution_mode": row.execution_mode,
            "last_symbol": row.last_symbol,
            "last_seen_at": seen.isoformat() if seen else None,
            "age_sec": round(age, 1) if age is not None else None,
            "healthy": healthy,
        }


def get_executor_presence_service() -> ExecutorPresenceService:
    return ExecutorPresenceService()
