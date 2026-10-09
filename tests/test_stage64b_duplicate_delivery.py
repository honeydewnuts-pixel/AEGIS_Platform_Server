"""Stage 6.4B — durable claim-on-deliver and fail-closed lease expiry.

MOCKED tests unless labeled DATABASE-BACKED.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import pytest

from app.services.durable_execution_queue import (
    CLAIM_LEASE_SEC,
    DurableExecutionQueueService,
    TERMINAL,
)


def _row(**kwargs):
    r = MagicMock()
    now = datetime.now(timezone.utc)
    defaults = dict(
        signal_id="sig-1",
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        volume=0.01,
        stop_loss=None,
        take_profit=None,
        details="test",
        created_at=now,
        confidence=0.8,
        rule_name="controlled_demo_test",
        atr14=None,
        initial_stop_atr_mult=1.5,
        max_hold_bars=72,
        trail_atr_mult=0.75,
        methodology="controlled_demo_test",
        risk_usd_at_open=None,
        production_authorized=False,
        controlled_demo_authorized=True,
        status="PENDING",
        claim_token=None,
        claimed_at=None,
        attempt_count=0,
        updated_at=now,
        ack_message=None,
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


def _session_with_row(row):
    session = MagicMock()
    session.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result)
    return session


# --- MOCKED ---

@pytest.mark.asyncio
async def test_claim_pending_to_claimed():
    svc = DurableExecutionQueueService()
    row = _row(status="PENDING")
    session = _session_with_row(row)
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        payload = await svc.get_pending(session, "ACC-1", "EURUSD")
    assert payload is not None
    assert row.status == "CLAIMED"
    assert row.claim_token
    assert payload.get("claim_token")


@pytest.mark.asyncio
async def test_second_poll_while_claimed_returns_none():
    svc = DurableExecutionQueueService()
    row = _row(
        status="CLAIMED",
        claimed_at=datetime.now(timezone.utc),
        claim_token="abc",
    )
    session = _session_with_row(row)
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        payload = await svc.get_pending(session, "ACC-1", "EURUSD")
    assert payload is None
    assert row.status == "CLAIMED"  # still held


@pytest.mark.asyncio
async def test_lease_expiry_becomes_submission_uncertain_not_pending():
    svc = DurableExecutionQueueService()
    old = datetime.now(timezone.utc) - timedelta(seconds=CLAIM_LEASE_SEC + 30)
    row = _row(status="CLAIMED", claimed_at=old, claim_token="tok")
    session = _session_with_row(row)
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        payload = await svc.get_pending(session, "ACC-1", "EURUSD")
    assert payload is None
    assert row.status == "SUBMISSION_UNCERTAIN"


@pytest.mark.asyncio
async def test_submission_uncertain_not_redelivered():
    svc = DurableExecutionQueueService()
    row = _row(status="SUBMISSION_UNCERTAIN")
    session = _session_with_row(row)
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        payload = await svc.get_pending(session, "ACC-1", "EURUSD")
    assert payload is None


@pytest.mark.asyncio
async def test_ack_on_claimed_terminals():
    svc = DurableExecutionQueueService()
    row = _row(status="CLAIMED")
    session = _session_with_row(row)
    out = await svc.ack(
        session, account_id="ACC-1", signal_id="sig-1", ok=True, position_ticket=1
    )
    assert out["status"] == "ACKED"
    assert row.status == "ACKED"


@pytest.mark.asyncio
async def test_ack_on_uncertain_terminals():
    svc = DurableExecutionQueueService()
    row = _row(status="SUBMISSION_UNCERTAIN")
    session = _session_with_row(row)
    out = await svc.ack(
        session, account_id="ACC-1", signal_id="sig-1", ok=True, position_ticket=2
    )
    assert out["status"] == "ACKED"


@pytest.mark.asyncio
async def test_duplicate_ack_idempotent():
    svc = DurableExecutionQueueService()
    row = _row(status="ACKED")
    session = _session_with_row(row)
    out = await svc.ack(
        session, account_id="ACC-1", signal_id="sig-1", ok=True, position_ticket=1
    )
    assert out.get("idempotent") is True


@pytest.mark.asyncio
async def test_unauthorized_expires():
    svc = DurableExecutionQueueService()
    row = _row(status="PENDING", controlled_demo_authorized=False, methodology="rsi9")
    session = _session_with_row(row)
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=False,
    ):
        payload = await svc.get_pending(session, "ACC-1", "EURUSD")
    assert payload is None
    assert row.status == "EXPIRED"


def test_terminal_set_unchanged_for_acked():
    assert "ACKED" in TERMINAL
    assert "SUBMISSION_UNCERTAIN" not in TERMINAL


def test_claim_callable_in_service():
    assert hasattr(DurableExecutionQueueService, "claim")
    assert hasattr(DurableExecutionQueueService, "get_pending")


def test_router_prefers_durable_claim():
    from pathlib import Path
    src = Path("backend/app/api/executor_router.py").read_text()
    assert "durable claim-on-deliver is authoritative" in src
    assert "Do not fall back to unclaimed in-memory delivery" in src or "Fail closed" in src


# --- DATABASE-BACKED ---

_ISOLATION_SCHEMA = "aegis_test_isolation_claim"
_ALLOWED = frozenset({"aegis_test", "aegis_test_db", "test", "aegis_ci"})


def _db_name(url: str) -> str:
    try:
        u = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return (urlparse(u).path or "").lstrip("/").split("?")[0].lower()
    except Exception:
        return ""


def _safe_db(url: str) -> bool:
    u = (url or "").lower()
    if not u.startswith("postgresql"):
        return False
    if any(x in u for x in ("production", "/prod", "neon.tech", "render.com", "amazonaws.com")):
        return False
    name = _db_name(u)
    if not name or name in ("postgres", "aegis", "aegis_prod") or "prod" in name:
        return False
    host = (urlparse(u.replace("postgresql+asyncpg://", "postgresql://", 1)).hostname or "").lower()
    if host not in ("localhost", "127.0.0.1", "postgres", "::1"):
        return False
    return name in _ALLOWED or name.startswith("aegis_test") or name.endswith("_test")


def test_postgres_concurrent_claim_only_one_wins():
    """DATABASE-BACKED: two concurrent get_pending → one payload, one CLAIMED."""
    db = os.environ.get("DATABASE_URL", "")
    if not _safe_db(db):
        pytest.skip(
            f"NOT RUN — unsafe or missing test DB (db_name={_db_name(db)!r})"
        )

    async def _run():
        from sqlalchemy import MetaData, event, select, text
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.models import AegisExecutionQueue

        url = db.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_size=5)

        @event.listens_for(engine.sync_engine, "connect")
        def _sp(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute(f'SET search_path TO "{_ISOLATION_SCHEMA}"')
            cur.close()

        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        isolated = AegisExecutionQueue.__table__.to_metadata(
            MetaData(), schema=_ISOLATION_SCHEMA
        )

        account_id = "CLAIM-CONC-ACC"
        signal_id = "CLAIM-CONC-SIG"
        now = datetime.now(timezone.utc)

        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_ISOLATION_SCHEMA}"'))
                await conn.run_sync(lambda c: isolated.create(c, checkfirst=True))

            async with Session() as session:
                await session.execute(
                    text("DELETE FROM aegis_execution_queue WHERE account_id = :a"),
                    {"a": account_id},
                )
                session.add(
                    AegisExecutionQueue(
                        signal_id=signal_id,
                        account_id=account_id,
                        symbol="EURUSD",
                        side="SELL",
                        volume=0.01,
                        methodology="controlled_demo_test",
                        rule_name="controlled_demo_test",
                        production_authorized=False,
                        controlled_demo_authorized=True,
                        status="PENDING",
                        attempt_count=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

            results: list = []

            async def one():
                async with Session() as session:
                    svc = DurableExecutionQueueService()
                    with patch(
                        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
                        return_value=True,
                    ):
                        payload = await svc.get_pending(session, account_id, "EURUSD")
                    await session.commit()
                    results.append(payload)

            await asyncio.gather(one(), one())

            wins = [r for r in results if r is not None]
            assert len(wins) == 1, f"expected exactly one claim winner, got {results!r}"

            async with Session() as session:
                q = await session.execute(
                    select(AegisExecutionQueue).where(
                        AegisExecutionQueue.account_id == account_id,
                        AegisExecutionQueue.signal_id == signal_id,
                    )
                )
                final = q.scalar_one()
                assert final.status == "CLAIMED"
                assert int(final.attempt_count or 0) == 1
        finally:
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f'DROP SCHEMA IF EXISTS "{_ISOLATION_SCHEMA}" CASCADE')
                    )
            except Exception:
                pass
            await engine.dispose()

    asyncio.run(_run())
