"""Stage 6.5: enqueue fails closed when emergency-stop state is unavailable."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_enqueue_fails_closed_when_stop_lookup_raises():
    from app.services.durable_execution_queue import DurableExecutionQueueService

    session = AsyncMock()
    payload = {
        "signal_id": "sig-stop-fail",
        "account_id": "ACC-TEST",
        "symbol": "EURUSD",
        "side": "SELL",
        "volume": 0.01,
        "methodology": "controlled_demo_test",
        "rule_name": "controlled_demo_test",
        "controlled_demo_authorized": True,
        "production_authorized": False,
    }

    with patch(
        "app.services.executor_signal_service.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ), patch(
        "app.services.operational_control_service.get_operational_control_service"
    ) as gocs:
        svc_mock = MagicMock()
        svc_mock.is_emergency_stop_on = AsyncMock(side_effect=RuntimeError("db down"))
        gocs.return_value = svc_mock
        out = await DurableExecutionQueueService().enqueue(session, payload)
        assert out is None
        session.add.assert_not_called()
        session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_blocks_when_stop_on():
    from app.services.durable_execution_queue import DurableExecutionQueueService

    session = AsyncMock()
    payload = {
        "signal_id": "sig-stop-on",
        "account_id": "ACC-TEST",
        "symbol": "EURUSD",
        "side": "SELL",
        "volume": 0.01,
        "methodology": "controlled_demo_test",
        "rule_name": "controlled_demo_test",
        "controlled_demo_authorized": True,
        "production_authorized": False,
    }

    with patch(
        "app.services.executor_signal_service.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ), patch(
        "app.services.operational_control_service.get_operational_control_service"
    ) as gocs:
        svc_mock = MagicMock()
        svc_mock.is_emergency_stop_on = AsyncMock(return_value=True)
        gocs.return_value = svc_mock
        out = await DurableExecutionQueueService().enqueue(session, payload)
        assert out is None
