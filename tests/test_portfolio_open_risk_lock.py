"""Portfolio open_risk_usd updates must be row-locked / concurrent-safe."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest


def test_source_uses_for_update_on_open_risk():
    src = Path("backend/app/services/portfolio_risk_service.py").read_text()
    assert "async def record_open_risk" in src
    assert "async def release_open_risk" in src
    assert "async def _apply_open_risk_delta" in src
    # Stage 3.3: single helper applies FOR UPDATE for both record and release
    assert "with_for_update" in src
    assert "Subscription.account_id == account_id" in src
    # Both public methods must be able to share a caller session
    assert "session=None" in src or "session: " in src or "session =" in src


def test_postgres_concurrent_release_no_lost_update():
    """Two concurrent releases must both apply (not last-write-wins)."""
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith("postgresql"):
        pytest.skip("NOT RUN — DATABASE_URL is not PostgreSQL")

    async def _run():
        from datetime import datetime, timezone
        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        from app.db.models import Subscription
        from app.services.portfolio_risk_service import PortfolioRiskService

        url = db.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, pool_size=5)
        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        account_id = "RISK-LOCK-ACC"
        now = datetime.now(timezone.utc)

        async with engine.begin() as conn:
            await conn.run_sync(
                lambda c: Subscription.__table__.create(c, checkfirst=True)
            )

        async with Session() as session:
            await session.execute(
                text("DELETE FROM subscriptions WHERE account_id = :a"),
                {"a": account_id},
            )
            session.add(
                Subscription(
                    account_id=account_id,
                    status="active",
                    plan="demo",
                    risk_preset="standard",
                    open_risk_usd=20.0,
                    risk_tolerance_pct=25.0,
                    trading_mode="multi_symbol",
                    trading_halted=False,
                    account_type="standard",
                    account_currency="USD",
                    max_devices=1,
                    max_trades_per_day=10,
                    updated_at=now,
                )
            )
            await session.commit()

        pr = PortfolioRiskService()

        async def rel(amount: float):
            await pr.release_open_risk(account_id, amount)

        await asyncio.gather(rel(5.0), rel(8.0))

        async with Session() as session:
            q = await session.execute(
                select(Subscription).where(Subscription.account_id == account_id)
            )
            row = q.scalar_one()
            # 20 - 5 - 8 = 7
            assert abs(float(row.open_risk_usd) - 7.0) < 1e-6, row.open_risk_usd

        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM subscriptions WHERE account_id = :a"),
                {"a": account_id},
            )
            # CI runs alembic upgrade after pytest — do not leave a pre-created table
            await conn.execute(text("DROP TABLE IF EXISTS subscriptions CASCADE"))

        await engine.dispose()

    asyncio.run(_run())
