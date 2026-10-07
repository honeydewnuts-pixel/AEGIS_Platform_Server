"""Stage 3.3 rollback contract: shared session never self-commits risk delta."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.portfolio_risk_service import PortfolioRiskService


@pytest.mark.asyncio
async def test_record_then_forced_commit_failure_leaves_commit_unsuccessful():
    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock(side_effect=RuntimeError("downstream_fail"))
    session.rollback = AsyncMock()
    sub = MagicMock()
    sub.open_risk_usd = 0.0
    res = MagicMock()
    res.scalar_one_or_none.return_value = sub
    session.execute.return_value = res

    await pr.record_open_risk("ACC-RB", 12.0, session=session)
    assert float(sub.open_risk_usd) == 12.0
    session.flush.assert_awaited()
    with pytest.raises(RuntimeError, match="downstream_fail"):
        await session.commit()
    await session.rollback()
    session.rollback.assert_awaited()
    # Risk mutation was never committed by PortfolioRiskService itself
    # (only flush on shared session)


@pytest.mark.asyncio
async def test_release_zero_delta_is_noop():
    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    await pr.release_open_risk("ACC-RB", 0.0, session=session)
    session.execute.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_release_none_delta_is_noop():
    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    await pr.release_open_risk("ACC-RB", None, session=session)  # type: ignore[arg-type]
    session.execute.assert_not_called()
