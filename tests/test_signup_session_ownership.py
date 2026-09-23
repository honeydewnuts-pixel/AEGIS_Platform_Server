"""Signup session helpers (unit)."""

import pytest

from app.services.signup_session_service import SignupSessionService
from app.services.plan_catalog import normalize_checkout_plan


class _FakePipe:
    def __init__(self, redis: "FakeRedis"):
        self._r = redis
        self._watched = None
        self._ops = []

    async def watch(self, key):
        self._watched = key

    def multi(self):
        self._ops = []

    def setex(self, key, ttl, value):
        self._ops.append(("setex", key, ttl, value))

    async def execute(self):
        for op in self._ops:
            if op[0] == "setex":
                await self._r.setex(op[1], op[2], op[3])
        return True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)

    def pipeline(self, transaction=True):
        return _FakePipe(self)


@pytest.mark.asyncio
async def test_signup_session_creates_server_account():
    svc = SignupSessionService(FakeRedis())
    payload = await svc.create(email="trader@example.com", plan="starter", purpose="checkout")
    assert payload["account_id"].startswith("ACC-")
    assert payload["email"] == "trader@example.com"
    assert payload["plan"] == "starter"
    got = await svc.get(payload["session_id"])
    assert got["account_id"] == payload["account_id"]


@pytest.mark.asyncio
async def test_demo_purpose_prefix():
    svc = SignupSessionService(FakeRedis())
    payload = await svc.create(email="a@b.co", purpose="demo")
    assert payload["account_id"].startswith("DEMO-")
    assert payload["plan"] == "demo"


@pytest.mark.asyncio
async def test_checkout_state_blocks_second_attempt():
    svc = SignupSessionService(FakeRedis())
    payload = await svc.create(email="a@b.co", plan="pro", purpose="checkout")
    sid = payload["session_id"]
    await svc.try_begin_checkout(sid)
    with pytest.raises(ValueError):
        await svc.try_begin_checkout(sid)


@pytest.mark.asyncio
async def test_invalid_checkout_plan_rejected():
    svc = SignupSessionService(FakeRedis())
    with pytest.raises(ValueError):
        await svc.create(email="a@b.co", plan="foobar", purpose="checkout")
    with pytest.raises(ValueError):
        await svc.create(email="a@b.co", plan="demo", purpose="checkout")


@pytest.mark.asyncio
async def test_monthly_alias_to_starter():
    svc = SignupSessionService(FakeRedis())
    payload = await svc.create(email="a@b.co", plan="monthly", purpose="checkout")
    assert payload["plan"] == "starter"


def test_normalize_checkout_plan():
    assert normalize_checkout_plan("pro") == "pro"
    assert normalize_checkout_plan("monthly") == "starter"
    with pytest.raises(ValueError):
        normalize_checkout_plan("foobar")
    with pytest.raises(ValueError):
        normalize_checkout_plan("enterprise")
