"""Autonomous execution must fail closed without credential getter."""
import pytest
import asyncio
from app.services.autonomous_execution_service import AutonomousDemoExecutionService


class _Dummy:
    pass


@pytest.mark.asyncio
async def test_credentials_fail_closed_without_getter():
    svc = AutonomousDemoExecutionService(
        job_queue=_Dummy(), worker_pool=_Dummy(), subscription_service=_Dummy(), trade_limits=_Dummy()
    )
    # no credential_getter attached
    creds = await svc._credentials("ACC-1")
    assert creds.get("execution_enabled") is False
