"""AEGIS V3 autonomous demo execution.

The V3 rule engine remains authoritative. A BUY/SELL result from the
screenshot analysis can be executed automatically on the connected MT5
demo terminal. Redis idempotency prevents repeated executions from the
same M1 candle/signature when screenshots arrive every few seconds.
"""
from __future__ import annotations
from typing import Any

from app.config import settings
from app.core.logging import configure_logging
from app.schemas.trading import MarketOrderRequest

class AutonomousDemoExecutionService:
    def __init__(self, job_queue, worker_pool, subscription_service, trade_limits) -> None:
        self.job_queue = job_queue
        self.worker_pool = worker_pool
        self.subscription_service = subscription_service
        self.trade_limits = trade_limits
        self.logger = configure_logging(__name__)

    async def execute_if_signal(
        self,
        account_id: str,
        symbol: str,
        result: dict[str, Any],
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        signal = str(result.get("signal") or "HOLD").upper()
        if not settings.AUTONOMOUS_EXECUTION_ENABLED:
            return {"status": "disabled", "executed": False}
        if signal not in ("BUY", "SELL"):
            return {"status": "no_trade_signal", "executed": False}

        plan = await self.subscription_service.get_plan(account_id)
        if plan != "demo":
            return {"status": "demo_only", "executed": False, "message": "Autonomous execution is restricted to the demo plan in this V3 checkpoint."}

        creds = await self._credentials(account_id)
        if not creds or not creds.get("execution_enabled"):
            return {"status": "execution_disabled", "executed": False}

        if not await self.worker_pool.is_running(account_id):
            return {"status": "worker_not_connected", "executed": False, "message": "MT5 worker is not connected."}

        # Prefer the synchronized M1 candle as the event identity.
        candle = str((market_snapshot or {}).get("candle_time") or "")
        rule = str(result.get("rule_name") or "unknown")
        event_key = f"aegis:v3:auto:{account_id}:{symbol}:{candle}:{signal}:{rule}"
        redis = self.job_queue.get_redis_client()
        if redis is None:
            return {"status": "redis_unavailable", "executed": False}

        # Reserve the event before sending the order to prevent duplicate orders.
        reserved = await redis.set(event_key, "reserved", nx=True, ex=7200)
        if not reserved:
            return {"status": "already_executed_for_signal_event", "executed": False}

        try:
            quota = await self.trade_limits.consume(account_id, 1)
        except Exception as exc:
            await redis.delete(event_key)
            return {"status": "trade_limit_blocked", "executed": False, "message": str(exc)}

        plan_code = plan if isinstance(plan, str) else "demo"
        preset = await self.subscription_service.get_risk_preset(account_id)
        volume = float(self.subscription_service.calculate_lot_size(plan_code, preset))

        request = MarketOrderRequest(
            symbol=symbol.strip(),
            volume=volume,
            order_type=signal,
            account_id=account_id,
            comment=f"AEGIS V3 {rule}",
        )

        try:
            job = await self.job_queue.submit_and_wait(
                account_id, "market_order", request.model_dump(mode="json"),
                timeout_seconds=settings.WORKER_JOB_TIMEOUT_SECONDS,
            )
            if job is None:
                await redis.delete(event_key)
                return {"status": "execution_timeout", "executed": False, "message": "MT5 worker did not return an execution result."}
            if not job.get("success"):
                await redis.delete(event_key)
                return {"status": "execution_failed", "executed": False, "message": job.get("message", "MT5 execution failed.")}
            broker_result = job.get("result")
            if isinstance(broker_result, dict) and not broker_result.get("success", False):
                await redis.delete(event_key)
                return {"status": "broker_rejected", "executed": False, "message": broker_result.get("message", "Broker rejected order.")}
            return {
                "status": "executed",
                "executed": True,
                "signal": signal,
                "rule": rule,
                "symbol": symbol,
                "volume": volume,
                "trade_quota": quota,
                "broker_result": broker_result,
            }
        except Exception as exc:
            await redis.delete(event_key)
            self.logger.exception("Autonomous V3 demo execution failed for %s %s", account_id, symbol)
            return {"status": "execution_exception", "executed": False, "message": str(exc)}

    async def _credentials(self, account_id: str):
        # Vault is not directly available here; this check is supplied by the
        # caller through app state in the route. Kept as a late-bound hook.
        getter = getattr(self, "credential_getter", None)
        if getter:
            return await getter(account_id)
        return {"execution_enabled": True}
