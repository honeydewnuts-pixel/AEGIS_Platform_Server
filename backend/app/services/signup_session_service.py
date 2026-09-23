"""
Server-issued signup sessions for public demo/checkout.

Prevents anonymous clients from asserting arbitrary account_id ownership.
Sessions live in Redis (short TTL).
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from typing import Any

logger = logging.getLogger("AEGIS.signup_session")

SESSION_TTL_SEC = 3600  # 1 hour
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
        }
        if self._r is not None:
            await self._r.setex(PREFIX + session_id, SESSION_TTL_SEC, json.dumps(payload))
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

    async def consume(self, session_id: str) -> dict[str, Any] | None:
        """Get and delete (one-time use for checkout binding)."""
        data = await self.get(session_id)
        if data and self._r is not None:
            await self._r.delete(PREFIX + session_id)
        return data
