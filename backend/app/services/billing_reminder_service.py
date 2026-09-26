"""
Billing reminder engine — subscription lifecycle notices to mobile inbox
and subscriber alert channels (email / Telegram / SMS / WhatsApp).

Does not touch MT5 Feed, rule engine, or Executor.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger("AEGIS.billing_reminders")

# Redis key TTL slightly over 48h so a 7d/3d/1d milestone is not re-fired same period
_DEDUP_TTL_SEC = 60 * 60 * 48


def _parse_days_before() -> list[int]:
    raw = getattr(settings, "BILLING_REMINDER_DAYS_BEFORE", "7,3,1") or "7,3,1"
    out: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            d = int(part)
            if d >= 0:
                out.append(d)
        except ValueError:
            continue
    return sorted(set(out), reverse=True) or [7, 3, 1]


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _days_until(end: datetime, now: datetime) -> int:
    """Whole calendar-ish days remaining (floor of remaining seconds / 86400)."""
    delta = end - now
    return int(delta.total_seconds() // 86400)


class BillingReminderService:
    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    def set_redis(self, redis_client: Any | None) -> None:
        self._redis = redis_client

    async def _already_sent(self, account_id: str, kind: str, anchor: str) -> bool:
        if self._redis is None:
            return False
        key = f"aegis:billing_reminder:{account_id}:{kind}:{anchor}"
        try:
            return bool(await self._redis.get(key))
        except Exception:
            logger.exception("billing dedup read failed")
            return False

    async def _mark_sent(self, account_id: str, kind: str, anchor: str) -> None:
        if self._redis is None:
            return
        key = f"aegis:billing_reminder:{account_id}:{kind}:{anchor}"
        try:
            await self._redis.set(key, "1", ex=_DEDUP_TTL_SEC)
        except Exception:
            logger.exception("billing dedup write failed")

    async def run_once(self, subscription_service: Any, notification_service: Any) -> dict[str, int]:
        """
        Scan all subscriptions and emit at most one reminder per milestone
        per account (deduped in Redis).
        """
        stats = {"scanned": 0, "sent": 0, "skipped": 0, "errors": 0}
        if not getattr(settings, "BILLING_REMINDER_ENABLED", True):
            return stats

        try:
            rows = await subscription_service.list_all()
        except Exception:
            logger.exception("billing reminder list_all failed")
            stats["errors"] += 1
            return stats

        now = datetime.now(timezone.utc)
        thresholds = _parse_days_before()
        portal = (getattr(settings, "PORTAL_BASE_URL", None) or getattr(settings, "FRONTEND_URL", None) or "https://leveragefx.co").rstrip("/")

        for row in rows or []:
            stats["scanned"] += 1
            account_id = row.get("account_id") or ""
            if not account_id:
                stats["skipped"] += 1
                continue
            status = (row.get("status") or "").lower()
            plan = row.get("plan") or "starter"
            period_end = _parse_dt(row.get("current_period_end"))
            grace_end = _parse_dt(row.get("grace_period_ends_at"))

            try:
                if status == "suspended":
                    await self._maybe_notify(
                        notification_service,
                        account_id=account_id,
                        kind="suspended",
                        anchor=grace_end.date().isoformat() if grace_end else "suspended",
                        ntype="SUBSCRIPTION_SUSPENDED",
                        title="Subscription suspended",
                        message=(
                            f"Your AEGIS {plan} subscription is suspended because the grace period ended "
                            f"without a successful renewal. Renew at {portal} to restore access."
                        ),
                        severity="critical",
                        stats=stats,
                    )
                    continue

                if status == "past_due":
                    grace_txt = grace_end.strftime("%Y-%m-%d %H:%M UTC") if grace_end else "soon"
                    await self._maybe_notify(
                        notification_service,
                        account_id=account_id,
                        kind="past_due",
                        anchor=(grace_end.date().isoformat() if grace_end else now.date().isoformat()),
                        ntype="SUBSCRIPTION_PAST_DUE",
                        title="Payment failed — grace period active",
                        message=(
                            f"We could not renew your AEGIS {plan} plan. You still have access until "
                            f"{grace_txt}. Update billing at {portal} to avoid suspension."
                        ),
                        severity="high",
                        stats=stats,
                    )
                    continue

                if status in ("canceled", "cancelled", "none"):
                    stats["skipped"] += 1
                    continue

                if status != "active":
                    stats["skipped"] += 1
                    continue

                if period_end is None:
                    stats["skipped"] += 1
                    continue

                days_left = _days_until(period_end, now)
                end_txt = period_end.strftime("%Y-%m-%d %H:%M UTC")
                anchor = period_end.date().isoformat()

                if days_left < 0:
                    await self._maybe_notify(
                        notification_service,
                        account_id=account_id,
                        kind="expired",
                        anchor=anchor,
                        ntype="SUBSCRIPTION_EXPIRED",
                        title="Subscription period ended",
                        message=(
                            f"Your AEGIS {plan} billing period ended on {end_txt}. "
                            f"Renew at {portal} to keep using the platform without interruption."
                        ),
                        severity="high",
                        stats=stats,
                    )
                    continue

                for d in thresholds:
                    if days_left == d:
                        if d == 0:
                            title = "Subscription ends today"
                            msg = (
                                f"Your AEGIS {plan} plan ends today ({end_txt}). "
                                f"Renew at {portal} to continue without interruption."
                            )
                        elif d == 1:
                            title = "Subscription ends tomorrow"
                            msg = (
                                f"Your AEGIS {plan} plan ends tomorrow ({end_txt}). "
                                f"Renew at {portal} to stay active."
                            )
                        else:
                            title = f"Subscription ends in {d} days"
                            msg = (
                                f"Your AEGIS {plan} plan ends in {d} days ({end_txt}). "
                                f"Renew at {portal} when ready so access is not interrupted."
                            )
                        await self._maybe_notify(
                            notification_service,
                            account_id=account_id,
                            kind=f"expiring_{d}d",
                            anchor=anchor,
                            ntype="SUBSCRIPTION_EXPIRING",
                            title=title,
                            message=msg,
                            severity="info" if d >= 3 else "high",
                            stats=stats,
                        )
                        break
            except Exception:
                logger.exception("billing reminder failed for %s", account_id)
                stats["errors"] += 1

        logger.info(
            "Billing reminder scan: scanned=%s sent=%s skipped=%s errors=%s",
            stats["scanned"],
            stats["sent"],
            stats["skipped"],
            stats["errors"],
        )
        return stats

    async def _maybe_notify(
        self,
        notification_service: Any,
        *,
        account_id: str,
        kind: str,
        anchor: str,
        ntype: str,
        title: str,
        message: str,
        severity: str,
        stats: dict[str, int],
    ) -> None:
        if await self._already_sent(account_id, kind, anchor):
            stats["skipped"] += 1
            return
        await notification_service.create(
            account_id=account_id,
            type=ntype,
            title=title,
            message=message,
            severity=severity,
            deliver_external=True,
            details=f"billing_kind={kind};anchor={anchor}",
        )
        await self._mark_sent(account_id, kind, anchor)
        stats["sent"] += 1
