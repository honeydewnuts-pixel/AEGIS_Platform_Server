"""
Server-issued signup sessions for public demo/checkout.

States: CREATED → CHECKOUT_CREATED
Prevents anonymous clients from asserting arbitrary account_id ownership.
Checkout transition is atomic via Redis WATCH/MULTI to avoid concurrent double checkout.
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from typing import Any

logger = logging.getLogger("AEGIS.signup_session")

SESSION_TTL_SEC = 3600
PREFIX = "aegis:signup_session:"


class SignupSessionService:
    def __init__(self, redis_client: Any) -> None:
        self._r = redis_client

    async def create(self, *, email: str, plan: str = "starter", purpose: str = "demo") -> dict[str, str]:
        email_n = (email or "").strip().lower()
        if not email_n or "@" not in email_n:
            raise ValueError("valid email required")
        plan = (plan or "demo" if purpose == "demo" else "starter").strip().lower()
        purpose = (purpose or "demo").strip().lower()
        if purpose == "checkout":
            from app.services.plan_catalog import normalize_checkout_plan
            plan = normalize_checkout_plan(plan)
        elif purpose == "demo":
            plan = "demo"
        account_id = f"{'DEMO' if purpose == 'demo' else 'ACC'}-{uuid.uuid4().hex[:10].upper()}"
        session_id = secrets.token_urlsafe(32)
        payload = {
            "session_id": session_id,
            "account_id": account_id,
            "email": email_n,
            "plan": plan,
            "purpose": purpose,
            "state": "CREATED",
            "payment_reference": None,
        }
        await self._save(session_id, payload)
        return payload

    async def get(self, session_id: str) -> dict[str, Any] | None:
        if not session_id or self._r is None:
            return None
        raw = await self._r.get(PREFIX + session_id)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def try_begin_checkout(self, session_id: str) -> dict[str, Any]:
        """
        Atomically transition CREATED → CHECKOUT_CREATED before contacting the
        payment provider. Concurrent callers: only one wins; others get ValueError.
        """
        if not session_id or self._r is None:
            raise ValueError("signup session unavailable")
        key = PREFIX + session_id
        last_err = "signup session not available for checkout"
        for _ in range(8):
            try:
                async with self._r.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)
                    raw = await self._r.get(key)
                    if not raw:
                        raise ValueError("Invalid or expired signup_session_id")
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    data = json.loads(raw)
                    state = data.get("state") or "CREATED"
                    if state == "CHECKOUT_CREATED":
                        raise ValueError(
                            "signup session already has an active checkout; complete payment or wait for expiry"
                        )
                    if state != "CREATED":
                        raise ValueError(f"signup session not available for checkout (state={state})")
                    data["state"] = "CHECKOUT_CREATED"
                    data["payment_reference"] = None
                    pipe.multi()
                    pipe.setex(key, SESSION_TTL_SEC, json.dumps(data))
                    await pipe.execute()
                    return data
            except ValueError:
                raise
            except Exception as e:
                # WatchError / concurrent modification → retry
                last_err = str(e) or last_err
                continue
        raise ValueError(last_err)

    async def set_payment_reference(self, session_id: str, payment_reference: str) -> dict[str, Any] | None:
        data = await self.get(session_id)
        if not data:
            return None
        data["payment_reference"] = payment_reference
        await self._save(session_id, data)
        return data

    async def mark_checkout_created(
        self, session_id: str, payment_reference: str | None = None
    ) -> dict[str, Any] | None:
        """
        Legacy helper: prefer try_begin_checkout + set_payment_reference.
        Still atomic for sequential callers; concurrent use should call try_begin_checkout.
        """
        if payment_reference is None:
            return await self.try_begin_checkout(session_id)
        data = await self.get(session_id)
        if not data:
            return None
        state = data.get("state") or "CREATED"
        if state == "CREATED":
            data = await self.try_begin_checkout(session_id)
        elif state == "CHECKOUT_CREATED":
            if data.get("payment_reference") and data.get("payment_reference") != payment_reference:
                raise ValueError(
                    "signup session already has an active checkout; complete or wait for expiry"
                )
            if data.get("payment_reference") and not payment_reference:
                raise ValueError("signup session already used for checkout")
        else:
            raise ValueError(f"signup session not available for checkout (state={state})")
        return await self.set_payment_reference(session_id, payment_reference)

    async def consume(self, session_id: str) -> dict[str, Any] | None:
        data = await self.get(session_id)
        if data and self._r is not None:
            await self._r.delete(PREFIX + session_id)
        return data

    async def _save(self, session_id: str, payload: dict[str, Any]) -> None:
        if self._r is None:
            return
        await self._r.setex(PREFIX + session_id, SESSION_TTL_SEC, json.dumps(payload))
