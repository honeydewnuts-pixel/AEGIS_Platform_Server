"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : app/db/models.py
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Credential(Base):
    __tablename__ = "credentials"

    credential_id: Mapped[str] = mapped_column(String, primary_key=True)
    broker_name: Mapped[str] = mapped_column(String, nullable=False)
    server: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    trading_nonce: Mapped[str] = mapped_column(String, nullable=False)
    trading_ciphertext: Mapped[str] = mapped_column(String, nullable=False)
    investor_nonce: Mapped[str | None] = mapped_column(String, nullable=True)
    investor_ciphertext: Mapped[str | None] = mapped_column(String, nullable=True)

    execution_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # active/past_due/suspended/canceled
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    portal_token: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProcessedPaymentEvent(Base):
    __tablename__ = "processed_payment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_provider_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SignalHistory(Base):
    """
    Persistent log of every signal the rule engine has produced, per
    account - previously nothing stored this at all (BrainCVService's
    rule evaluation was ephemeral, only the Redis frame history persisted
    briefly for the rule engine's own multi-frame analysis). This is what
    powers the client portal's signal history view and gives you an audit
    trail of what fired and why.
    """
    __tablename__ = "signal_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String, nullable=False)          # BUY / SELL / HOLD
    confidence: Mapped[float] = mapped_column(nullable=False)
    rule_name: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ApiKey(Base):
    """
    Each key is bound to exactly one account_id (account_id=None means an
    admin/service key, not tied to a specific subscriber). Keys are stored
    as a SHA-256 hash, never in plaintext - same principle as password
    storage, since this table being read doesn't mean every key should be
    immediately usable by whoever read it.

    This replaces the earlier shared-API_KEYS-list model, which had no way
    to tell "which account is this request allowed to touch" - see
    security.py's verify_api_key for the authorization check this enables.
    """
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    account_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
