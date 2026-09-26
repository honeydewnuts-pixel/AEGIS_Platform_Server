"""Unit tests for billing reminder milestones (no DB/Redis required for pure helpers)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.billing_reminder_service import (
    BillingReminderService,
    _days_until,
    _parse_days_before,
    _parse_dt,
)


def test_parse_days_before_default():
    days = _parse_days_before()
    assert 7 in days and 3 in days and 1 in days


def test_days_until_positive():
    now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    end = now + timedelta(days=3, hours=2)
    assert _days_until(end, now) == 3


def test_parse_dt_iso():
    dt = _parse_dt("2026-10-01T00:00:00Z")
    assert dt is not None
    assert dt.year == 2026


@pytest.mark.asyncio
async def test_run_once_sends_expiring_3d():
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=3, hours=1)
    sub = MagicMock()
    sub.list_all = AsyncMock(
        return_value=[
            {
                "account_id": "ACC-TEST",
                "status": "active",
                "plan": "starter",
                "current_period_end": period_end.isoformat(),
                "grace_period_ends_at": None,
            }
        ]
    )
    notif = MagicMock()
    notif.create = AsyncMock(return_value={"id": 1})
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    svc = BillingReminderService(redis)
    stats = await svc.run_once(sub, notif)
    assert stats["sent"] == 1
    assert notif.create.await_count == 1
    kwargs = notif.create.await_args.kwargs
    assert kwargs["type"] == "SUBSCRIPTION_EXPIRING"
    assert "3 days" in kwargs["title"] or "3" in kwargs["message"]


@pytest.mark.asyncio
async def test_run_once_dedup_skips_second():
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=1, hours=2)
    row = {
        "account_id": "ACC-TEST",
        "status": "active",
        "plan": "pro",
        "current_period_end": period_end.isoformat(),
        "grace_period_ends_at": None,
    }
    sub = MagicMock()
    sub.list_all = AsyncMock(return_value=[row])
    notif = MagicMock()
    notif.create = AsyncMock(return_value={"id": 1})
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=[None, b"1"])
    redis.set = AsyncMock()
    svc = BillingReminderService(redis)
    s1 = await svc.run_once(sub, notif)
    s2 = await svc.run_once(sub, notif)
    assert s1["sent"] == 1
    assert s2["sent"] == 0
    assert notif.create.await_count == 1


@pytest.mark.asyncio
async def test_past_due_reminder():
    now = datetime.now(timezone.utc)
    grace = now + timedelta(days=2)
    sub = MagicMock()
    sub.list_all = AsyncMock(
        return_value=[
            {
                "account_id": "ACC-PD",
                "status": "past_due",
                "plan": "starter",
                "current_period_end": (now - timedelta(days=1)).isoformat(),
                "grace_period_ends_at": grace.isoformat(),
            }
        ]
    )
    notif = MagicMock()
    notif.create = AsyncMock(return_value={"id": 2})
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    svc = BillingReminderService(redis)
    stats = await svc.run_once(sub, notif)
    assert stats["sent"] == 1
    assert notif.create.await_args.kwargs["type"] == "SUBSCRIPTION_PAST_DUE"
