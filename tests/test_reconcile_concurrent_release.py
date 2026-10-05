"""Reconcile risk release must be transactionally idempotent."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


def test_reconcile_source_uses_for_update():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "list_open_for_update" in src
    assert "with_for_update" in src
    assert "open_rows = await self.list_open_for_update" in src
    assert 'if row.state == "RISK_RELEASED":' in src


def test_sequential_reconcile_state_recheck_in_source():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    # After acquiring lock, already-released rows contribute zero
    assert "RISK_RELEASED" in src
    assert "stale_risk_released" in src


def test_postgres_concurrent_reconcile_single_release():
    """Two concurrent reconciles on the same stale row → one release only."""
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith("postgresql"):
        pytest.skip(
            "NOT RUN — DATABASE_URL is not PostgreSQL "
            "(CI provides Postgres; local unit env typically does not)"
        )

    async def _run():
        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        from app.db.models import AegisPositionLifecycle
        from app.services.durable_lifecycle_service import DurableLifecycleService

        url = db.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_size=5)
        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Schema is provided by CI Alembic migrations; do not create_all
        # (conflicts with existing tables). Verify table is reachable.
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy", fromlist=["text"]).text(
                        "SELECT 1 FROM aegis_position_lifecycle LIMIT 0"
                    )
                )
        except Exception as e:
            await engine.dispose()
            pytest.skip(f"NOT RUN — lifecycle table unavailable: {e}")

        account_id = "CONC-TEST-ACC"
        signal_id = "CONC-SIG-1"
        ticket = 9_000_000_001
        risk = 12.5

        async with Session() as session:
            await session.execute(
                text("DELETE FROM aegis_position_lifecycle WHERE account_id = :a"),
                {"a": account_id},
            )
            now = datetime.now(timezone.utc)
            session.add(
                AegisPositionLifecycle(
                    account_id=account_id,
                    signal_id=signal_id,
                    position_ticket=ticket,
                    symbol="EURUSD",
                    side="SELL",
                    volume=0.1,
                    risk_usd_at_open=risk,
                    state="POSITION_OPEN",
                    opened_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        results: list[dict] = []

        async def one_reconcile():
            async with Session() as session:
                dur = DurableLifecycleService()
                summary = await dur.reconcile(session, account_id, [])
                await session.commit()
                results.append(summary)

        await asyncio.gather(one_reconcile(), one_reconcile())

        total_released = sum(float(r.get("stale_risk_released") or 0) for r in results)
        assert abs(total_released - risk) < 1e-9, f"double release? totals={results}"

        async with Session() as session:
            q = await session.execute(
                select(AegisPositionLifecycle).where(
                    AegisPositionLifecycle.account_id == account_id,
                    AegisPositionLifecycle.signal_id == signal_id,
                )
            )
            final = q.scalar_one()
            assert final.state == "RISK_RELEASED"

        await engine.dispose()

    asyncio.run(_run())
