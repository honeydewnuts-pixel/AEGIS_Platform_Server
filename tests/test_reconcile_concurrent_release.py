"""Reconcile risk release must be transactionally idempotent.

DATABASE-BACKED tests use an isolated schema only — never DROP the
application's aegis_position_lifecycle table.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Isolation schema for disposable concurrent tests (not the app table)
_ISOLATION_SCHEMA = "aegis_test_isolation_conc"


def _db_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def _is_safe_test_database(url: str) -> bool:
    """Refuse production / shared unrecognized hosts."""
    u = (url or "").lower()
    if not u.startswith("postgresql"):
        return False
    # Explicit denials
    denied = (
        "prod",
        "production",
        "neon.tech",  # AEGIS production often on Neon — require test DB name
        "render.com",
        "amazonaws.com",
    )
    # Allow localhost / 127.0.0.1 / docker service names used in CI
    if any(h in u for h in ("localhost", "127.0.0.1", "@postgres:", "@postgres/")):
        return True
    # CI-style: database name must contain test
    if re.search(r"/[a-z0-9_]*test[a-z0-9_]*(\?|$)", u):
        # still block neon/render unless name is clearly test-only and not prod keyword
        if "neon.tech" in u or "render.com" in u:
            return "test" in u and "prod" not in u
        return "prod" not in u
    return False


def test_reconcile_source_uses_for_update():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "list_open_for_update" in src
    assert "with_for_update" in src
    assert "open_rows = await self.list_open_for_update" in src
    assert 'if row.state == "RISK_RELEASED":' in src


def test_sequential_reconcile_state_recheck_in_source():
    src = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "RISK_RELEASED" in src
    assert "stale_risk_released" in src


def test_postgres_concurrent_reconcile_single_release():
    """Two concurrent reconciles on the same stale row → one release only.

    DATABASE-BACKED: uses schema aegis_test_isolation_conc only.
    Does NOT drop public.aegis_position_lifecycle.
    """
    db = _db_url()
    if not _is_safe_test_database(db):
        pytest.skip(
            "NOT RUN — DATABASE_URL is not a recognized safe test PostgreSQL "
            f"(refusing shared/production). url_prefix={db[:32]!r}..."
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

        account_id = "CONC-TEST-ACC"
        signal_id = "CONC-SIG-1"
        ticket = 9_000_000_001
        risk = 12.5

        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_ISOLATION_SCHEMA}"'))
                await conn.execute(text(f'SET search_path TO "{_ISOLATION_SCHEMA}", public'))
                # Create lifecycle table only inside isolation schema
                await conn.execute(text(f'DROP TABLE IF EXISTS "{_ISOLATION_SCHEMA}".aegis_position_lifecycle CASCADE'))
                await conn.run_sync(
                    lambda sync_conn: AegisPositionLifecycle.__table__.create(
                        sync_conn, checkfirst=True
                    )
                )
        except Exception as e:
            await engine.dispose()
            pytest.skip(f"NOT RUN — cannot prepare isolation schema: {e}")

        async with Session() as session:
            await session.execute(text(f'SET search_path TO "{_ISOLATION_SCHEMA}", public'))
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
                    open_risk_applied=True,
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
                await session.execute(text(f'SET search_path TO "{_ISOLATION_SCHEMA}", public'))
                dur = DurableLifecycleService()
                summary = await dur.reconcile(session, account_id, [])
                await session.commit()
                results.append(summary)

        await asyncio.gather(one_reconcile(), one_reconcile())

        total_released = sum(float(r.get("stale_risk_released") or 0) for r in results)
        assert abs(total_released - risk) < 1e-9, f"double release? totals={results}"

        async with Session() as session:
            await session.execute(text(f'SET search_path TO "{_ISOLATION_SCHEMA}", public'))
            q = await session.execute(
                select(AegisPositionLifecycle).where(
                    AegisPositionLifecycle.account_id == account_id,
                    AegisPositionLifecycle.signal_id == signal_id,
                )
            )
            final = q.scalar_one()
            assert final.state == "RISK_RELEASED"

        # Tear down isolation schema only — never public app tables
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{_ISOLATION_SCHEMA}" CASCADE'))

        await engine.dispose()

    asyncio.run(_run())


def test_pg_guard_refuses_unsafe_urls():
    """Static guard: production-like URLs are rejected."""
    assert _is_safe_test_database("postgresql://postgres:postgres@localhost:5432/aegis_test")
    assert _is_safe_test_database("postgresql://postgres:postgres@postgres:5432/aegis_test")
    assert not _is_safe_test_database("postgresql://user:pass@ep-x.neon.tech/aegis_prod")
    assert not _is_safe_test_database("postgresql://user:pass@db.render.com/aegis")
    assert not _is_safe_test_database("sqlite:///x.db")
