"""
Server-issued signup sessions for public demo/checkout.

States: CREATED → CHECKOUT_CREATED → (consumed for payment attempt)
Prevents anonymous clients from asserting arbitrary account_id ownership.
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

    async def create(self, *, email: str, plan: str = "demo", purpose: str = "demo") -> dict[str, str]:
        email_n = (email or "").strip().lower()
        if not email_n or "@" not in email_n:
            raise ValueError("valid email required")
        plan = (plan or "demo").strip().lower()
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

    async def mark_checkout_created(self, session_id: str, payment_reference: str | None = None) -> dict[str, Any] | None:
        """
        Transition CREATED → CHECKOUT_CREATED. Idempotent if already CHECKOUT_CREATED
        with the same reference; rejects a second distinct checkout attempt.
        """
        data = await self.get(session_id)
        if not data:
            return None
        state = data.get("state") or "CREATED"
        if state == "CHECKOUT_CREATED":
            # Same session already used for a checkout — do not allow a second concurrent attempt
            if payment_reference and data.get("payment_reference") and data.get("payment_reference") != payment_reference:
                raise ValueError("signup session already has an active checkout; complete or wait for expiry")
            if data.get("payment_reference") and not payment_reference:
                raise ValueError("signup session already used for checkout")
            return data
        if state != "CREATED":
            raise ValueError(f"signup session not available for checkout (state={state})")
        data["state"] = "CHECKOUT_CREATED"
        if payment_reference:
            data["payment_reference"] = payment_reference
        await self._save(session_id, data)
        return data

    async def consume(self, session_id: str) -> dict[str, Any] | None:
        data = await self.get(session_id)
        if data and self._r is not None:
            await self._r.delete(PREFIX + session_id)
        return data

    async def _save(self, session_id: str, payload: dict[str, Any]) -> None:
        if self._r is None:
            return
        await self._r.setex(PREFIX + session_id, SESSION_TTL_SEC, json.dumps(payload))
