"""
AEGIS Security Module

Per-account API key authentication and authorization. Replaces the
earlier shared-key-list model (see git history / README changelog) -
that model could authenticate ("is this a real AEGIS client") but
couldn't authorize ("is this client allowed to touch THIS account"),
which is a real vulnerability (OWASP API Security Top 10 #1, Broken
Object Level Authorization) once more than one subscriber exists:
any valid key could act on any account_id, and API keys embedded in a
distributed mobile APK are inherently extractable.

Keys are stored as SHA-256 hashes (see app/db/models.py ApiKey), never
in plaintext, same principle as password storage.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Header, HTTPException, status
from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import ApiKey


def generate_secret_key(length: int = 32) -> str:
    """Generate a cryptographically secure secret key (used for admin/service keys, master keys, etc.)."""
    return secrets.token_urlsafe(length)


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


@dataclass
class AuthContext:
    account_id: str | None   # None only for admin/service keys
    is_admin: bool
    label: str | None


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> AuthContext:
    """
    FastAPI dependency. Validates the key exists, isn't revoked, and
    returns WHO it belongs to - callers must still separately check
    that the account_id in the request matches auth.account_id (or that
    auth.is_admin is True) using require_account_match() below. Just
    calling this dependency authenticates; it does not by itself
    authorize access to any specific account's data.
    """
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header.")

    key_hash = _hash_key(x_api_key)

    async with async_session_factory() as session:
        result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
        row = result.scalar_one_or_none()

        if row is None or row.revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key.")

        row.last_used_at = datetime.now(timezone.utc)
        await session.commit()

        return AuthContext(account_id=row.account_id, is_admin=row.is_admin, label=row.label)


def require_account_match(auth: AuthContext, requested_account_id: str) -> None:
    """
    Call this explicitly in every endpoint that takes an account_id,
    right after both are available. Deliberately not folded into a
    single combined dependency, because account_id shows up in path
    params, query params, and request bodies inconsistently across
    routes - an explicit call at the point of use is clearer and
    harder to accidentally skip than a dependency that has to guess
    where to find the id.
    """
    if auth.is_admin:
        return
    if auth.account_id != requested_account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This API key is not authorized for this account.",
        )


def require_admin(auth: AuthContext) -> None:
    """For endpoints that show fleet-wide data (all devices, all subscriptions) -
    these aren't scoped to one account_id, so require_account_match doesn't
    apply; only an admin key should see across every subscriber."""
    if not auth.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires an admin API key.",
        )


async def issue_api_key(account_id: str | None, is_admin: bool = False, label: str | None = None) -> str:
    """
    Generates a new raw key, stores only its hash, and returns the raw
    key ONCE - same handling as the portal_token pattern. Called when a
    subscription first activates (see SubscriptionService.apply_event)
    to issue that subscriber's own mobile-app key, and at bootstrap for
    the initial admin key (see app/core/startup.py).
    """
    raw_key = secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)

    async with async_session_factory() as session:
        session.add(ApiKey(
            key_hash=key_hash,
            account_id=account_id,
            is_admin=is_admin,
            label=label,
            revoked=False,
            created_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    return raw_key


def application_security_status() -> dict:
    return {
        "authentication": "Per-account API Key (X-API-Key header), SHA-256 hashed at rest",
        "authorization": "Object-level - each key is bound to one account_id (or is_admin) and checked "
                          "per-request via require_account_match()",
        "encryption": "AES-256-GCM for stored broker credentials (CredentialVaultService)",
        "status": "Foundation Ready",
    }
