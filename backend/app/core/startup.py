"""
Project: AEGIS
Company: Honeydewnuts Nigerian Limited

Application startup / shutdown lifecycle events.

Shared singletons (job queue, worker pool manager) are attached to
app.state rather than module-level globals, so they're accessed
through FastAPI's request object / dependency system instead of
relying on import-time ordering.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from app.config import settings
from app.services.job_queue_service import JobQueueService
from app.services.worker_pool_manager import WorkerPoolManager
from app.services.credential_vault_service import CredentialVaultService
from app.services.indicator_history_service import IndicatorHistoryService
from app.services.brain_cv_service import BrainCVService
from app.services.subscription_service import SubscriptionService
from app.services.device_health_service import DeviceHealthService
from app.services.credential_reveal_service import CredentialRevealService
from app.services.signal_history_service import SignalHistoryService
from app.core.metrics import refresh_metrics_loop
from app.security import issue_api_key
from app.db.base import async_session_factory
from app.db.models import ApiKey
from sqlalchemy import select

logger = logging.getLogger("AEGIS")


async def _subscription_sweep_loop(app: FastAPI) -> None:
    """
    Background task: periodically disconnect any account whose grace
    period has expired but is still connected. Without this, an account
    could stay connected indefinitely as long as it never happens to
    call an endpoint that checks subscription status.
    """
    subscription_service: SubscriptionService = app.state.subscription_service
    worker_pool: WorkerPoolManager = app.state.worker_pool

    while True:
        try:
            lapsed = await subscription_service.get_lapsed_accounts()
            for account_id in lapsed:
                if await worker_pool.is_running(account_id):
                    logger.warning("Subscription grace period expired for %s - disconnecting.", account_id)
                    await worker_pool.stop_worker(account_id)
                await subscription_service.mark_suspended(account_id)
        except Exception:
            logger.exception("Subscription sweep iteration failed.")

        await asyncio.sleep(settings.SUBSCRIPTION_SWEEP_INTERVAL_SECONDS)


async def on_startup(app: FastAPI) -> None:
    logger.info("========================================")
    logger.info("AEGIS Backend Starting...")
    logger.info("Company: Honeydewnuts Nigerian Limited")
    logger.info("========================================")

    app.state.vault = CredentialVaultService()
    app.state.subscription_service = SubscriptionService()

    app.state.job_queue = JobQueueService()
    await app.state.job_queue.connect()

    app.state.worker_pool = WorkerPoolManager(app.state.job_queue)

    app.state.brain_cv_service = BrainCVService()
    app.state.indicator_history = IndicatorHistoryService(
        app.state.job_queue.get_redis_client(), app.state.brain_cv_service.config
    )
    app.state.device_health = DeviceHealthService(app.state.job_queue.get_redis_client())
    app.state.credential_reveal = CredentialRevealService(app.state.job_queue.get_redis_client())
    app.state.signal_history = SignalHistoryService()

    app.state.subscription_sweep_task = asyncio.create_task(_subscription_sweep_loop(app))
    app.state.metrics_task = asyncio.create_task(refresh_metrics_loop(app))

    await _bootstrap_admin_key()

    logger.info("Job queue + worker pool manager + indicator history + subscriptions + metrics ready.")


async def _bootstrap_admin_key() -> None:
    """
    Creates the first admin API key on the very first startup, if none
    exists yet. Uses ADMIN_BOOTSTRAP_KEY from env if set (so you control
    the actual key value); otherwise generates one and logs it ONCE -
    copy it immediately, it isn't stored in retrievable form afterward.
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.is_admin == True)  # noqa: E712
        )

        existing_admin = result.scalars().first()

        if existing_admin is not None:
            return  # an admin key already exists - don't create another on every restart

    from app.config import settings
    import hashlib

    if settings.ADMIN_BOOTSTRAP_KEY:
        async with async_session_factory() as session:
            from app.db.models import ApiKey as ApiKeyModel
            from datetime import datetime, timezone

            session.add(
                ApiKeyModel(
                    key_hash=hashlib.sha256(
                        settings.ADMIN_BOOTSTRAP_KEY.encode()
                    ).hexdigest(),
                    account_id=None,
                    is_admin=True,
                    label="bootstrap admin key (from ADMIN_BOOTSTRAP_KEY env)",
                    revoked=False,
                    created_at=datetime.now(timezone.utc),
                )
            )

            await session.commit()

        logger.info("Admin API key registered from ADMIN_BOOTSTRAP_KEY.")

    else:
        raw_key = await issue_api_key(
            account_id=None,
            is_admin=True,
            label="auto-generated bootstrap admin key",
        )

        logger.warning(
            "========================================\n"
            "No admin API key existed - generated one:\n"
            "  %s\n"
            "This is the ONLY time it will be shown in plaintext. Save it now\n"
            "(e.g. in a password manager) - it isn't recoverable from the DB.\n"
            "========================================",
            raw_key,
        )


async def on_shutdown(app: FastAPI) -> None:
    logger.info("AEGIS Backend shutting down...")

    sweep_task = getattr(app.state, "subscription_sweep_task", None)
    if sweep_task is not None:
        sweep_task.cancel()

    metrics_task = getattr(app.state, "metrics_task", None)
    if metrics_task is not None:
        metrics_task.cancel()

    worker_pool: WorkerPoolManager | None = getattr(app.state, "worker_pool", None)
    if worker_pool is not None:
        await worker_pool.stop_all()

    job_queue: JobQueueService | None = getattr(app.state, "job_queue", None)
    if job_queue is not None:
        await job_queue.disconnect()

    logger.info("AEGIS Backend stopped.")
