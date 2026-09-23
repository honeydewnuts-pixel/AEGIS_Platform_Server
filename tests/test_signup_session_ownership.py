"""Signup session helpers (unit)."""

import asyncio

import pytest

from app.services.signup_session_service import SignupSessionService


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)


@pytest.mark.asyncio
async def test_signup_session_creates_server_account():
    svc = SignupSessionService(FakeRedis())
    payload = await svc.create(email="trader@example.com", plan="starter", purpose="checkout")
    assert payload["account_id"].startswith("ACC-")
    assert payload["email"] == "trader@example.com"
    got = await svc.get(payload["session_id"])
    assert got["account_id"] == payload["account_id"]


@pytest.mark.asyncio
async def test_demo_purpose_prefix():
    svc = SignupSessionService(FakeRedis())
    payload = await svc.create(email="a@b.co", purpose="demo")
    assert payload["account_id"].startswith("DEMO-")
