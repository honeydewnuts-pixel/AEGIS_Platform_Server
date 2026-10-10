"""Stage 6.4A — real PostgreSQL recovery concurrency and rollback tests."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import pytest

_SCHEMA_REC = "aegis_test_isolation_rec"
_SCHEMA_RB = "aegis_test_isolation_rb"
_ALLOWED = frozenset({"aegis_test", "aegis_test_db", "test", "aegis_ci"})


def _db_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def _db_name(url: str) -> str:
    try:
        u = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return (urlparse(u).path or "").lstrip("/").split("?")[0].lower()
    except Exception:
        return ""


def _is_safe(url: str) -> bool:
    u = (url or "").lower().strip()
    if not u.startswith("postgresql"):
        return False
    deny = (
        "production", "/prod", "_prod", "prod_", "aegis_prod",
        "neon.tech", "render.com", "amazonaws.com", "supabase.co",
    )
    if any(s in u for s in deny):
        return False
    name = _db_name(u)
    if not name or name in ("postgres", "template0", "template1", "aegis", "aegis_platform"):
        return False
    if "prod" in name:
        return False
    host = (urlparse(u.replace("postgresql+asyncpg://", "postgresql://", 1)).hostname or "").lower()
    if host not in ("localhost", "127.0.0.1", "postgres", "::1"):
        return False
    return name in _ALLOWED or name.startswith("aegis_test") or name.endswith("_test")


def test_pg_concurrent_recovery_no_double() -> None:
    """H: two concurrent recovery paths must not double-record (real PG)."""
    db = _db_url()
    if not _is_safe(db):
        pytest.skip(
            "NOT RUN — DATABASE_URL is not a recognized disposable test PostgreSQL "
            f"(db_name={_db_name(db)!r}; host redacted)"
        )

    async def _run():
        from sqlalchemy import MetaData, event, select, text
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from app.db.models import AegisPositionLifecycle, Subscription
        from app.services.durable_lifecycle_service import DurableLifecycleService
        from app.services.portfolio_risk_service import PortfolioRiskService

        url = db.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_size=5)
        schema = _SCHEMA_REC

        @event.listens_for(engine.sync_engine, "connect")
        def _set_search_path(dbapi_conn, connection_record):  # noqa: ARG001
            cursor = dbapi_conn.cursor()
            cursor.execute('SET search_path TO "' + schema + '"')
            cursor.close()

        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        life_t = AegisPositionLifecycle.__table__.to_metadata(MetaData(), schema=schema)
        sub_t = Subscription.__table__.to_metadata(MetaData(), schema=schema)
        account_id = "REC-CONC-ACC"
        signal_id = "REC-CONC-SIG"
        ticket = 9100000001
        risk = 15.0
        now = datetime.now(timezone.utc)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "' + schema + '"'))
                await conn.run_sync(lambda c: life_t.create(c, checkfirst=True))
                await conn.run_sync(lambda c: sub_t.create(c, checkfirst=True))
            async with Session() as session:
                await session.execute(
                    text("DELETE FROM aegis_position_lifecycle WHERE account_id = :a"),
                    {"a": account_id},
                )
                await session.execute(
                    text("DELETE FROM subscriptions WHERE account_id = :a"),
                    {"a": account_id},
                )
                session.add(
                    Subscription(
                        account_id=account_id,
                        status="active",
                        plan="starter",
                        risk_preset="standard",
                        risk_tolerance_pct=25.0,
                        trading_mode="multi_symbol",
                        trading_halted=False,
                        open_risk_usd=0.0,
                        account_type="standard",
                        account_currency="USD",
                        max_devices=1,
                        max_trades_per_day=10,
                        updated_at=now,
                    )
                )
                session.add(
                    AegisPositionLifecycle(
                        account_id=account_id,
                        signal_id=signal_id,
                        position_ticket=ticket,
                        symbol="EURUSD",
                        side="SELL",
                        volume=0.01,
                        risk_usd_at_open=risk,
                        open_risk_applied=False,
                        state="POSITION_OPEN",
                        opened_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

            recovered_amounts = []

            async def one():
                async with Session() as session:
                    dur = DurableLifecycleService()
                    summary = await dur.reconcile(
                        session, account_id, [{"position_ticket": ticket}]
                    )
                    recovered = float(summary.get("open_risk_recovered") or 0.0)
                    ids = list(summary.get("recovered_signal_ids") or [])
                    pr = PortfolioRiskService()
                    if recovered > 0:
                        await pr.record_open_risk(account_id, recovered, session=session)
                        for sid in ids:
                            if sid:
                                await dur.mark_open_risk_applied(
                                    session, account_id=account_id, signal_id=str(sid)
                                )
                    await session.commit()
                    recovered_amounts.append(recovered)

            await asyncio.gather(one(), one())
            assert sum(recovered_amounts) == risk, recovered_amounts

            async with Session() as session:
                final = (
                    await session.execute(
                        select(AegisPositionLifecycle).where(
                            AegisPositionLifecycle.account_id == account_id,
                            AegisPositionLifecycle.signal_id == signal_id,
                        )
                    )
                ).scalar_one()
                assert final.open_risk_applied is True
                sub = (
                    await session.execute(
                        select(Subscription).where(Subscription.account_id == account_id)
                    )
                ).scalar_one()
                assert float(sub.open_risk_usd) == risk
        finally:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE'))
            except Exception:
                pass
            await engine.dispose()

    asyncio.run(_run())


def test_pg_record_open_risk_failure_rolls_back_flag() -> None:
    """E: portfolio write failure rolls back open_risk_applied (real PG)."""
    db = _db_url()
    if not _is_safe(db):
        pytest.skip(
            "NOT RUN — DATABASE_URL is not a recognized disposable test PostgreSQL "
            f"(db_name={_db_name(db)!r}; host redacted)"
        )

    async def _run():
        from sqlalchemy import MetaData, event, select, text
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from app.db.models import AegisPositionLifecycle, Subscription
        from app.services.durable_lifecycle_service import DurableLifecycleService
        from app.services.portfolio_risk_service import PortfolioRiskService

        url = db.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_size=3)
        schema = _SCHEMA_RB

        @event.listens_for(engine.sync_engine, "connect")
        def _set_search_path(dbapi_conn, connection_record):  # noqa: ARG001
            cursor = dbapi_conn.cursor()
            cursor.execute('SET search_path TO "' + schema + '"')
            cursor.close()

        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        life_t = AegisPositionLifecycle.__table__.to_metadata(MetaData(), schema=schema)
        sub_t = Subscription.__table__.to_metadata(MetaData(), schema=schema)
        account_id = "REC-ROLL-ACC"
        signal_id = "REC-ROLL-SIG"
        ticket = 9200000001
        risk = 22.0
        now = datetime.now(timezone.utc)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "' + schema + '"'))
                await conn.run_sync(lambda c: life_t.create(c, checkfirst=True))
                await conn.run_sync(lambda c: sub_t.create(c, checkfirst=True))
            async with Session() as session:
                await session.execute(
                    text("DELETE FROM aegis_position_lifecycle WHERE account_id = :a"),
                    {"a": account_id},
                )
                await session.execute(
                    text("DELETE FROM subscriptions WHERE account_id = :a"),
                    {"a": account_id},
                )
                session.add(
                    Subscription(
                        account_id=account_id,
                        status="active",
                        plan="starter",
                        risk_preset="standard",
                        risk_tolerance_pct=25.0,
                        trading_mode="multi_symbol",
                        trading_halted=False,
                        open_risk_usd=0.0,
                        account_type="standard",
                        account_currency="USD",
                        max_devices=1,
                        max_trades_per_day=10,
                        updated_at=now,
                    )
                )
                session.add(
                    AegisPositionLifecycle(
                        account_id=account_id,
                        signal_id=signal_id,
                        position_ticket=ticket,
                        symbol="EURUSD",
                        side="SELL",
                        volume=0.01,
                        risk_usd_at_open=risk,
                        open_risk_applied=False,
                        state="POSITION_OPEN",
                        opened_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

            async with Session() as session:
                dur = DurableLifecycleService()
                pr = PortfolioRiskService()
                try:
                    await pr.record_open_risk(account_id, risk, session=session)
                    await dur.mark_risk_recorded(
                        session, account_id=account_id, signal_id=signal_id, risk_usd=risk
                    )
                    raise RuntimeError("controlled_test_failure")
                except RuntimeError:
                    await session.rollback()

            async with Session() as session:
                dur = DurableLifecycleService()
                final = (
                    await session.execute(
                        select(AegisPositionLifecycle).where(
                            AegisPositionLifecycle.account_id == account_id,
                            AegisPositionLifecycle.signal_id == signal_id,
                        )
                    )
                ).scalar_one()
                assert final.open_risk_applied is False
                sub = (
                    await session.execute(
                        select(Subscription).where(Subscription.account_id == account_id)
                    )
                ).scalar_one()
                assert float(sub.open_risk_usd) == 0.0
                summary = await dur.reconcile(
                    session, account_id, [{"position_ticket": ticket}]
                )
                assert float(summary.get("open_risk_recovered") or 0.0) == risk
        finally:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE'))
            except Exception:
                pass
            await engine.dispose()

    asyncio.run(_run())
