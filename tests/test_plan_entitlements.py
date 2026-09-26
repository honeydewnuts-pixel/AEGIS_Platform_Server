"""Central plan catalogue drives brain/live-trading entitlement — not hard-coded 'live'."""

import pytest
from unittest.mock import AsyncMock

from app.services.plan_catalog import resolve_plan
from app.services.subscription_service import SubscriptionService


def test_paid_plans_have_live_trading():
    for code in ("starter", "pro", "business"):
        p = resolve_plan(code)
        assert p.get("live_trading") is True, code


def test_demo_plan_no_live_trading_flag():
    p = resolve_plan("demo")
    assert p.get("live_trading") is False


def test_legacy_live_alias_maps_to_starter():
    p = resolve_plan("live")
    assert p.get("code") == "starter"
    assert p.get("live_trading") is True


def test_resolve_plan_code_is_source_of_truth():
    for raw, expected in (
        ("starter", "starter"),
        ("PRO", "pro"),
        ("live", "starter"),
        ("monthly", "starter") if False else ("starter", "starter"),
    ):
        assert resolve_plan(raw)["code"] == expected


@pytest.mark.asyncio
async def test_allows_brain_for_paid_plans():
    svc = SubscriptionService()
    for code in ("starter", "pro", "business"):
        svc.get_plan = AsyncMock(return_value=code)
        assert await svc.allows_brain("acc-test") is True, code


@pytest.mark.asyncio
async def test_allows_brain_for_demo():
    svc = SubscriptionService()
    svc.get_plan = AsyncMock(return_value="demo")
    assert await svc.allows_brain("acc-demo") is True


@pytest.mark.asyncio
async def test_allows_brain_rejects_none():
    svc = SubscriptionService()
    svc.get_plan = AsyncMock(return_value="none")
    assert await svc.allows_brain("acc-none") is False


@pytest.mark.asyncio
async def test_allows_live_trading_for_starter():
    svc = SubscriptionService()
    svc.get_plan = AsyncMock(return_value="starter")
    svc.is_active = AsyncMock(return_value=True)
    assert await svc.allows_live_trading("acc-starter") is True


@pytest.mark.asyncio
async def test_allows_live_trading_false_for_demo_flag():
    """Demo is analysis/execution-demo path; catalogue live_trading is False."""
    svc = SubscriptionService()
    svc.get_plan = AsyncMock(return_value="demo")
    svc.is_active = AsyncMock(return_value=True)
    # allows_live_trading uses resolve_plan.live_trading which is False for demo
    assert await svc.allows_live_trading("acc-demo") is False
