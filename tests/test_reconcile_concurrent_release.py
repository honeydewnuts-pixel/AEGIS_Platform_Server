"""Reconcile risk release must be transactionally idempotent.

Stage 6.4A final isolation correction.

DATABASE-BACKED tests use schema aegis_test_isolation_conc only.
They never DROP, TRUNCATE, or mutate public.aegis_position_lifecycle.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest

_ISOLATION_SCHEMA = "aegis_test_isolation_conc"

# CI Backend workflow uses: postgresql://postgres:postgres@localhost:5432/aegis_test
_ALLOWED_TEST_DB_NAMES = frozenset(
    {
        "aegis_test",
        "aegis_test_db",
        "test",
        "aegis_ci",
    }
)


def _db_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def _database_name(url: str) -> str:
    """Extract DB name without logging credentials."""
    try:
        # strip driver prefix for urlparse
        u = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        path = urlparse(u).path or ""
        name = path.lstrip("/").split("?")[0]
        return name.lower()
    except Exception:
        return ""


def _is_safe_test_database(url: str) -> bool:
    """Fail closed unless positively identified as a disposable test DB.

    Order: deny production-like patterns first, then require an allow rule.
    Host alone (localhost) is never sufficient.
    """
    u = (url or "").lower().strip()
    if not u.startswith("postgresql"):
        return False

    # --- deny first ---
    deny_substrings = (
        "production",
        "/prod",
        "_prod",
        "prod_",
        "aegis_prod",
        "neon.tech",
        "render.com",
        "amazonaws.com",
        "supabase.co",
        "azure.com",
        "cloud.google",
    )
    if any(s in u for s in deny_substrings):
        return False

    db_name = _database_name(u)
    if not db_name:
        return False
    if db_name in ("postgres", "template0", "template1", "aegis", "aegis_platform"):
        return False
    if "prod" in db_name:
        return False

    # --- allow: explicit test DB names on local/CI hosts only ---
    host = ""
    try:
        host = (urlparse(u.replace("postgresql+asyncpg://", "postgresql://", 1)).hostname or "").lower()
    except Exception:
        host = ""

    local_or_ci_host = host in (
        "localhost",
        "127.0.0.1",
        "postgres",  # docker compose service name in CI
        "::1",
    )
    if not local_or_ci_host:
        return False

    if db_name in _ALLOWED_TEST_DB_NAMES:
        return True
    # Also accept names that start with aegis_test or end with _test
    if db_name.startswith("aegis_test") or db_name.endswith("_test"):
        return True

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


def test_pg_guard_refuses_unsafe_urls():
    """Static guard: production-like and non-test names are rejected."""
    # CI / local test DB — allowed
    assert _is_safe_test_database(
        "postgresql://postgres:postgres@localhost:5432/aegis_test"
    )
    assert _is_safe_test_database(
        "postgresql://postgres:postgres@postgres:5432/aegis_test"
    )
    assert _is_safe_test_database(
        "postgresql://u:p@127.0.0.1:5432/myapp_test"
    )

    # localhost alone is NOT enough if DB name is production-like
    assert not _is_safe_test_database(
        "postgresql://postgres:postgres@localhost:5432/aegis_prod"
    )
    assert not _is_safe_test_database(
        "postgresql://postgres:postgres@localhost:5432/aegis"
    )
    assert not _is_safe_test_database(
        "postgresql://postgres:postgres@localhost:5432/postgres"
    )

    # remote / managed
    assert not _is_safe_test_database(
        "postgresql://user:pass@ep-x.neon.tech/aegis_test"
    )
    assert not _is_safe_test_database(
        "postgresql://user:pass@db.render.com/aegis_test"
    )
    assert not _is_safe_test_database("sqlite:///x.db")


def test_postgres_concurrent_reconcile_single_release():
    """Two concurrent reconciles on the same stale row → one release only.

    DATABASE-BACKED. Every connection is bound to schema
    aegis_test_isolation_conc via a connect event listener.
    public.aegis_position_lifecycle is never targeted.
    """
    db = _db_url()
    if not _is_safe_test_database(db):
        pytest.skip(
            "NOT RUN — DATABASE_URL is not a recognized disposable test PostgreSQL "
            f"(db_name={_database_name(db)!r}; host redacted)"
        )

    async def _run():
        from sqlalchemy import MetaData, event, select, text
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.models import AegisPositionLifecycle
        from app.services.durable_lifecycle_service import DurableLifecycleService

        url = db.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_size=5)

        # Bind EVERY pooled connection to the isolation schema (not session-local only)
        @event.listens_for(engine.sync_engine, "connect")
        def _set_search_path(dbapi_conn, connection_record):  # noqa: ARG001
            cursor = dbapi_conn.cursor()
            cursor.execute(f'SET search_path TO "{_ISOLATION_SCHEMA}"')
            cursor.close()

        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        account_id = "CONC-TEST-ACC"
        signal_id = "CONC-SIG-1"
        ticket = 9_000_000_001
        risk = 12.5

        # Schema-qualified copy so create never targets public even if
        # public.aegis_position_lifecycle already exists.
        isolated_table = AegisPositionLifecycle.__table__.to_metadata(
            MetaData(), schema=_ISOLATION_SCHEMA
        )

        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f'CREATE SCHEMA IF NOT EXISTS "{_ISOLATION_SCHEMA}"')
                )
                await conn.run_sync(
                    lambda sync_conn: isolated_table.create(sync_conn, checkfirst=True)
                )

            # Prove public table is not the test target: count isolation schema only
            async with Session() as session:
                schema_check = await session.execute(
                    text(
                        "SELECT table_schema FROM information_schema.tables "
                        "WHERE table_name = 'aegis_position_lifecycle' "
                        "AND table_schema = :s"
                    ),
                    {"s": _ISOLATION_SCHEMA},
                )
                assert schema_check.scalar_one() == _ISOLATION_SCHEMA

                # search_path on this connection (listener already set it)
                sp = await session.execute(text("SHOW search_path"))
                sp_val = sp.scalar_one()
                assert _ISOLATION_SCHEMA in str(sp_val)

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
            search_paths: list[str] = []

            async def one_reconcile():
                async with Session() as session:
                    # Listener sets path; also assert for evidence
                    sp = await session.execute(text("SHOW search_path"))
                    search_paths.append(str(sp.scalar_one()))
                    dur = DurableLifecycleService()
                    summary = await dur.reconcile(session, account_id, [])
                    await session.commit()
                    results.append(summary)

            await asyncio.gather(one_reconcile(), one_reconcile())

            assert all(_ISOLATION_SCHEMA in p for p in search_paths), (
                f"worker search_path not isolated: {search_paths!r}"
            )

            total_released = sum(
                float(r.get("stale_risk_released") or 0) for r in results
            )
            assert abs(total_released - risk) < 1e-9, (
                f"double release? totals={results}"
            )

            async with Session() as session:
                q = await session.execute(
                    select(AegisPositionLifecycle).where(
                        AegisPositionLifecycle.account_id == account_id,
                        AegisPositionLifecycle.signal_id == signal_id,
                    )
                )
                final = q.scalar_one()
                assert final.state == "RISK_RELEASED"

        finally:
            # Tear down isolation schema only — never public app tables
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f'DROP SCHEMA IF EXISTS "{_ISOLATION_SCHEMA}" CASCADE')
                    )
            except Exception:
                pass
            await engine.dispose()

    asyncio.run(_run())
