"""
====================================================================
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : subscription_service.py

Tracks subscription status per account and enforces the grace-period
policy when payment fails. Backed by Postgres via SQLAlchemy (async) -
previously SQLite-file-backed; moved for the same multi-instance
reason as CredentialVaultService.

Status lifecycle:
    none -> active -> (payment fails) -> past_due -> (grace period
    expires) -> suspended -> (payment succeeds again) -> active
    active -> (canceled) -> canceled
====================================================================
"""

from __future__ import annotations

from app.services.plan_catalog import get_base_lot, get_max_lot, resolve_plan, resolve_plan, mode_for_plan

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.core.logging import configure_logging
from app.db.base import async_session_factory
from app.db.models import ProcessedPaymentEvent, Subscription
from app.services.payment_providers.base import PaymentEvent, PaymentEventType
from app.security import issue_api_key


class SubscriptionService:

    def __init__(self) -> None:
        self.logger = configure_logging(__name__)

    # ------------------------------------------------------------
    # Idempotency - webhooks can be delivered more than once
    # ------------------------------------------------------------

    async def already_processed(self, provider: str, provider_event_id: str) -> bool:
        async with async_session_factory() as session:
            result = await session.execute(
                select(ProcessedPaymentEvent).where(
                    ProcessedPaymentEvent.provider == provider,
                    ProcessedPaymentEvent.provider_event_id == provider_event_id,
                )
            )
            return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------
    # Event application
    # ------------------------------------------------------------

    async def apply_event(self, event: PaymentEvent) -> dict[str, str] | None:
        """
        Returns {"account_id", "portal_token", "mobile_api_key"} if this
        call represents a FIRST activation (new credentials were just
        issued) - the caller (subscription_router's webhook handler) uses
        this to stash them for one-time reveal via CredentialRevealService.
        Returns None for renewals, failures, or cancellations, since
        there's nothing new to reveal in those cases.
        """
        if not event.account_id:
            self.logger.warning("Payment event with no account_id, ignoring: %s", event.provider_event_id)
            return None

        now = datetime.now(timezone.utc)
        newly_issued: dict[str, str] | None = None

        async with async_session_factory() as session:
            if event.event_type == PaymentEventType.PAYMENT_SUCCEEDED:
                existing = await session.get(Subscription, event.account_id)
                is_first_activation = existing is None
                # Preserve the existing portal token across renewals - only
                # generate a new one the first time this account activates.
                portal_token = existing.portal_token if existing and existing.portal_token else secrets.token_urlsafe(24)

                # THE FIX: resolve which plan this payment is for and apply
                # its tier (devices/trade caps + live_trading eligibility),
                # instead of only touching `status`. Previously this method
                # never set `plan` at all, so an account that signed up for
                # the demo (plan="demo") and then paid stayed on plan="demo"
                # forever unless an admin manually called
                # POST /api/admin/tenants/set-plan - i.e. there was no
                # working DEMO_VERIFY -> LIVE_TRADE auto-switch on payment.
                # event.plan comes from checkout metadata, now threaded
                # through by every adapter's parse_webhook_event (see
                # payment_providers/*.py) - it was already being SENT at
                # checkout, just silently dropped on the webhook side.
                # Fallback order if a provider ever omits it: keep whatever
                # plan the account already had (renewal case), else "starter"
                # (brand-new paid signup with no captured plan - shouldn't
                # normally happen now that all three adapters send it, but
                # fails safe rather than crashing the webhook).
                existing_plan = getattr(existing, "plan", None) if existing else None
                plan_code = event.plan or existing_plan or "starter"
                plan_meta = resolve_plan(plan_code)

                stmt = pg_insert(Subscription).values(
                    account_id=event.account_id,
                    provider=event.provider,
                    provider_customer_id=event.provider_customer_id,
                    provider_subscription_id=event.provider_subscription_id,
                    status="active",
                    plan=plan_meta["code"],
                    max_devices=plan_meta["max_devices"],
                    max_trades_per_day=plan_meta["max_trades_per_day"],
                    current_period_end=event.current_period_end,
                    grace_period_ends_at=None,
                    portal_token=portal_token,
                    updated_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["account_id"],
                    set_={
                        "provider": event.provider,
                        "provider_customer_id": event.provider_customer_id,
                        "provider_subscription_id": event.provider_subscription_id,
                        "status": "active",
                        "plan": plan_meta["code"],
                        "max_devices": plan_meta["max_devices"],
                        "max_trades_per_day": plan_meta["max_trades_per_day"],
                        "current_period_end": event.current_period_end,
                        "grace_period_ends_at": None,
                        "portal_token": portal_token,
                        "updated_at": now,
                    },
                )
                await session.execute(stmt)
                self.logger.info(
                    "Subscription activated/renewed: %s (%s) -> plan=%s mode=%s",
                    event.account_id, event.provider, plan_meta["code"], mode_for_plan(plan_meta["code"]),
                )

                if is_first_activation:
                    # Issued after commit (outside this session) since
                    # issue_api_key opens its own session - keeps the two
                    # concerns (subscription state vs. credential issuance)
                    # decoupled rather than sharing a transaction.
                    await session.commit()
                    mobile_api_key = await issue_api_key(
                        account_id=event.account_id,
                        is_admin=False,
                        label=f"mobile app - {event.account_id}",
                    )
                    newly_issued = {
                        "account_id": event.account_id,
                        "portal_token": portal_token,
                        "mobile_api_key": mobile_api_key,
                    }
                    self.logger.info(
                        "First activation for %s - credentials issued, handed back for one-time reveal staging.",
                        event.account_id,
                    )

            elif event.event_type == PaymentEventType.PAYMENT_FAILED:
                grace_end = now + timedelta(days=settings.SUBSCRIPTION_GRACE_PERIOD_DAYS)
                row = await session.get(Subscription, event.account_id)
                if row is not None:
                    row.status = "past_due"
                    row.grace_period_ends_at = grace_end
                    row.updated_at = now
                self.logger.warning(
                    "Payment failed for %s - grace period until %s", event.account_id, grace_end.isoformat()
                )

            elif event.event_type == PaymentEventType.SUBSCRIPTION_CANCELED:
                row = await session.get(Subscription, event.account_id)
                if row is not None:
                    row.status = "canceled"
                    row.updated_at = now
                self.logger.info("Subscription canceled: %s", event.account_id)

            session.add(ProcessedPaymentEvent(
                provider=event.provider,
                provider_event_id=event.provider_event_id,
                processed_at=now,
            ))
            await session.commit()

        return newly_issued

    # ------------------------------------------------------------
    # Status checks
    # ------------------------------------------------------------

    async def get_status(self, account_id: str) -> dict[str, Any] | None:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)

        if row is None:
            return None

        plan_code = getattr(row, "plan", None) or "starter"
        preset = getattr(row, "risk_preset", None) or "standard"
        lot = self.calculate_lot_size(plan_code, preset)
        return {
            "account_id": row.account_id,
            "provider": row.provider,
            "provider_customer_id": row.provider_customer_id,
            "provider_subscription_id": row.provider_subscription_id,
            "status": row.status,
            "plan": plan_code,
            "mode": mode_for_plan(plan_code),
            "risk_preset": preset,
            "calculated_lot_size": lot,
            "plan_max_lot": get_max_lot(plan_code),
            "plan_base_lot": get_base_lot(plan_code),
            "strategy_sl_points": int(getattr(settings, "STRATEGY_SL_POINTS", 100)),
            "strategy_tp_points": int(getattr(settings, "STRATEGY_TP_POINTS", 180)),
            "current_period_end": row.current_period_end.isoformat() if row.current_period_end else None,
            "grace_period_ends_at": row.grace_period_ends_at.isoformat() if row.grace_period_ends_at else None,
            "updated_at": row.updated_at.isoformat(),
        }

    async def list_all(self) -> list[dict[str, Any]]:
        """Admin-dashboard-facing: every subscription record, most recently updated first."""
        async with async_session_factory() as session:
            result = await session.execute(select(Subscription).order_by(Subscription.updated_at.desc()))
            rows = result.scalars().all()

        return [
            {
                "account_id": r.account_id,
                "provider": r.provider,
                "status": r.status,
                "current_period_end": r.current_period_end.isoformat() if r.current_period_end else None,
                "grace_period_ends_at": r.grace_period_ends_at.isoformat() if r.grace_period_ends_at else None,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]

    async def verify_portal_token(self, account_id: str, token: str) -> bool:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
        if row is None or row.portal_token is None:
            return False
        return secrets.compare_digest(row.portal_token, token)

    async def is_active(self, account_id: str) -> bool:
        """
        True if the account can use the platform right now - either
        a clean 'active' subscription, or 'past_due' but still inside
        the grace period.
        """
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)

        if row is None:
            return False
        if row.status == "active":
            return True
        if row.status == "past_due" and row.grace_period_ends_at:
            return datetime.now(timezone.utc) < row.grace_period_ends_at
        return False

    async def get_lapsed_accounts(self) -> list[str]:
        """Accounts whose grace period has expired but are still 'past_due'."""
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription.account_id).where(
                    Subscription.status == "past_due",
                    Subscription.grace_period_ends_at < now,
                )
            )
            return [row[0] for row in result.all()]

    async def mark_suspended(self, account_id: str) -> None:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is not None:
                row.status = "suspended"
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def mark_canceled(self, account_id: str) -> None:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is not None:
                row.status = "canceled"
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def get_plan(self, account_id: str) -> str:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.account_id == account_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return "none"
        plan = getattr(row, "plan", None) or "live"
        if row.status in ("active", "past_due", "demo"):
            if row.status == "demo":
                return "demo"
            return plan or "starter"
        return "none"

    async def allows_brain(self, account_id: str) -> bool:
        return (await self.get_plan(account_id)) in ("live", "demo")

    async def allows_live_trading(self, account_id: str) -> bool:
        plan_code = await self.get_plan(account_id)
        if plan_code in ("none",):
            return False
        if not await self.is_active(account_id) and plan_code != "demo":
            return False
        return bool(resolve_plan(plan_code).get("live_trading"))

    async def set_mode(self, account_id: str, mode: str, actor: str = "system") -> dict[str, Any]:
        """
        Explicit mode setter backing POST /api/set_mode. This is the SAME
        underlying mechanism apply_event() now uses automatically on a
        successful payment (see the comment there) - both paths resolve a
        plan via plan_catalog and write it the same way, so they can't
        drift out of sync. This method exists for the cases that aren't
        "a payment just succeeded": admin/support overrides (comping a
        client, reverting someone to demo, testing), or any future
        self-service downgrade-to-demo flow.

        mode: "DEMO_VERIFY" or "LIVE_TRADE" (case-insensitive). Maps to
        the "demo" plan or, for LIVE_TRADE, either the account's current
        paid plan if it already has one, or "starter" as the default
        entry-level paid tier.
        """
        mode_norm = (mode or "").strip().upper()
        if mode_norm not in ("DEMO_VERIFY", "LIVE_TRADE"):
            raise ValueError(f"Unknown mode '{mode}' - expected DEMO_VERIFY or LIVE_TRADE")

        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            result = await session.execute(select(Subscription).where(Subscription.account_id == account_id))
            existing = result.scalar_one_or_none()

            if mode_norm == "DEMO_VERIFY":
                plan_code = "demo"
            else:
                current_plan = getattr(existing, "plan", None) if existing else None
                plan_code = current_plan if current_plan and current_plan != "demo" else "starter"
            plan_meta = resolve_plan(plan_code)

            if existing is None:
                portal_token = secrets.token_urlsafe(24)
                session.add(Subscription(
                    account_id=account_id,
                    provider="manual",
                    status="active",
                    plan=plan_meta["code"],
                    max_devices=plan_meta["max_devices"],
                    max_trades_per_day=plan_meta["max_trades_per_day"],
                    portal_token=portal_token,
                    current_period_end=now + timedelta(days=14) if plan_meta["code"] == "demo" else None,
                    updated_at=now,
                ))
            else:
                existing.plan = plan_meta["code"]
                existing.max_devices = plan_meta["max_devices"]
                existing.max_trades_per_day = plan_meta["max_trades_per_day"]
                existing.status = "active"
                existing.updated_at = now
                if plan_meta["code"] == "demo" and not existing.current_period_end:
                    existing.current_period_end = now + timedelta(days=14)
            await session.commit()

        self.logger.info("Mode set for %s -> %s (plan=%s) by %s", account_id, mode_norm, plan_meta["code"], actor)
        return {"account_id": account_id, "mode": mode_norm, "plan": plan_meta["code"]}

    async def activate_demo(self, account_id: str) -> dict[str, str]:
        from datetime import datetime, timedelta, timezone
        import secrets as sec
        now = datetime.now(timezone.utc)
        portal_token = sec.token_urlsafe(24)
        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.account_id == account_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.status = "active"
                existing.plan = "demo"
                existing.max_devices = 1
                existing.max_trades_per_day = 5
                existing.updated_at = now
                existing.current_period_end = now + timedelta(days=14)
                if not existing.portal_token:
                    existing.portal_token = portal_token
                else:
                    portal_token = existing.portal_token
            else:
                session.add(Subscription(
                    account_id=account_id,
                    provider="demo",
                    status="active",
                    plan="demo",
                    max_devices=1,
                    max_trades_per_day=5,
                    portal_token=portal_token,
                    current_period_end=now + timedelta(days=14),
                    updated_at=now,
                ))
            await session.commit()
        # Do NOT mint a new mobile key on every demo click — that caused
        # portal/mobile mismatch (user keeps old key or wrong Account ID).
        # Fresh key only when none exist; portal "Connect mobile" rotates explicitly.
        from app.db.models import ApiKey
        from sqlalchemy import select

        existing_key = False
        async with async_session_factory() as session:
            row = (
                await session.execute(
                    select(ApiKey).where(
                        ApiKey.account_id == account_id,
                        ApiKey.is_admin == False,  # noqa: E712
                        ApiKey.revoked == False,  # noqa: E712
                    )
                )
            ).scalars().first()
            existing_key = row is not None

        mobile_api_key = None
        if not existing_key:
            mobile_api_key = await issue_api_key(
                account_id=account_id,
                is_admin=False,
                label=f"demo mobile key for {account_id}",
                issued_by="demo_signup",
            )
        return {
            "account_id": account_id,
            "portal_token": portal_token,
            "mobile_api_key": mobile_api_key,  # null if key already exists — use Connect mobile to rotate
            "plan": "demo",
            "key_reused": existing_key,
            "note": (
                "Mobile API key already exists for this account. "
                "Use portal Connect mobile to reveal a new key if needed."
                if existing_key
                else "Copy mobile_api_key into the app with this account_id."
            ),
        }

    # ------------------------------------------------------------
    # Risk presets (server is source of truth for lot size)
    # ------------------------------------------------------------

    VALID_RISK_PRESETS = ("conservative", "standard", "aggressive")

    def calculate_lot_size(self, plan_code: str, risk_preset: str) -> float:
        """final_lot = min(base_lot * multiplier, max_lot), rounded to 2 decimals."""
        preset = (risk_preset or "standard").strip().lower()
        multipliers = getattr(settings, "RISK_MULTIPLIERS", None) or {
            "conservative": 0.5,
            "standard": 1.0,
            "aggressive": 1.5,
        }
        mult = float(multipliers.get(preset, 1.0))
        base = get_base_lot(plan_code)
        cap = get_max_lot(plan_code)
        final = min(base * mult, cap)
        return round(final, 2)

    async def get_risk_preset(self, account_id: str) -> str:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
        if row is None:
            return "standard"
        return getattr(row, "risk_preset", None) or "standard"

    async def set_risk_preset(self, account_id: str, risk_preset: str) -> dict:
        preset = (risk_preset or "").strip().lower()
        if preset not in self.VALID_RISK_PRESETS:
            raise ValueError("Invalid risk_preset")
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                # Create minimal subscription row so preset can be stored
                from datetime import datetime, timezone
                row = Subscription(
                    account_id=account_id,
                    status="demo",
                    plan="demo",
                    risk_preset=preset,
                    max_devices=1,
                    max_trades_per_day=5,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(row)
            else:
                row.risk_preset = preset
                from datetime import datetime, timezone
                row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            plan_code = getattr(row, "plan", None) or "demo"
        lot = self.calculate_lot_size(plan_code, preset)
        return {
            "status": "success",
            "risk_preset": preset,
            "calculated_lot_size": lot,
            "plan_max_lot": get_max_lot(plan_code),
            "plan_base_lot": get_base_lot(plan_code),
        }

