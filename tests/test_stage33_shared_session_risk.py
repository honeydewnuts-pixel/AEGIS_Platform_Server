"""Stage 3.3: lifecycle + portfolio open_risk share one session (flush, caller commits)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_record_open_risk_with_session_does_not_commit():
    from app.services.portfolio_risk_service import PortfolioRiskService

    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    # Simulate no subscription row
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    await pr.record_open_risk("ACC-TEST", 10.0, session=session)
    session.flush.assert_not_called()  # no row → early return
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_record_open_risk_with_session_flushes_only():
    from app.services.portfolio_risk_service import PortfolioRiskService

    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    sub = MagicMock()
    sub.open_risk_usd = 5.0
    result = MagicMock()
    result.scalar_one_or_none.return_value = sub
    session.execute.return_value = result

    await pr.record_open_risk("ACC-TEST", 12.5, session=session)
    assert float(sub.open_risk_usd) == 17.5
    session.flush.assert_awaited()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_release_open_risk_with_session_flushes_only():
    from app.services.portfolio_risk_service import PortfolioRiskService

    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    sub = MagicMock()
    sub.open_risk_usd = 20.0
    result = MagicMock()
    result.scalar_one_or_none.return_value = sub
    session.execute.return_value = result

    await pr.release_open_risk("ACC-TEST", 7.0, session=session)
    assert float(sub.open_risk_usd) == 13.0
    session.flush.assert_awaited()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_release_floors_at_zero_with_session():
    from app.services.portfolio_risk_service import PortfolioRiskService

    pr = PortfolioRiskService()
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    sub = MagicMock()
    sub.open_risk_usd = 3.0
    result = MagicMock()
    result.scalar_one_or_none.return_value = sub
    session.execute.return_value = result

    await pr.release_open_risk("ACC-TEST", 10.0, session=session)
    assert float(sub.open_risk_usd) == 0.0
    session.commit.assert_not_called()
