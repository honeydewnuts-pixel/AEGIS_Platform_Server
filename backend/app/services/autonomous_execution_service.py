"""Autonomous demo market-order path — portfolio sizing required (fail-closed)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger("AEGIS.autonomous_exec")


class AutonomousDemoExecutionService:
    def __init__(
        self,
        job_queue: Any = None,
        worker_pool: Any = None,
        subscription_service: Any = None,
        trade_limits: Any = None,
    ) -> None:
        self.job_queue = job_queue
        self.worker_pool = worker_pool
        self.subscription_service = subscription_service
        self.trade_limits = trade_limits
        self.credential_getter: Callable[..., Awaitable[Any]] | None = None
        self.portfolio_risk: Any = None


    async def _credentials(self, account_id: str) -> dict[str, Any]:
        """Fail closed when no credential getter is wired (demo/autonomous path)."""
        getter = self.credential_getter
        if getter is None:
            return {
                "account_id": account_id,
                "execution_enabled": False,
                "reason": "no_credential_getter",
            }
        try:
            data = await getter(account_id)
            if not isinstance(data, dict):
                return {
                    "account_id": account_id,
                    "execution_enabled": False,
                    "reason": "invalid_credential_payload",
                }
            # Explicit opt-in only
            enabled = bool(data.get("execution_enabled"))
            out = dict(data)
            out["account_id"] = account_id
            out["execution_enabled"] = enabled
            return out
        except Exception as e:
            logger.exception("credential_getter failed")
            return {
                "account_id": account_id,
                "execution_enabled": False,
                "reason": f"credential_error:{e}",
            }

    async def execute_if_signal(
        self,
        *,
        account_id: str,
        symbol: str,
        result: dict[str, Any],
        market_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        side = str(result.get("signal") or "").upper()
        if side not in ("BUY", "SELL"):
            return {"executed": False, "reason": "no_signal"}

        sym = (symbol or "").upper().split(".")[0]
        plan_code = "demo"
        preset = "standard"
        if self.subscription_service is not None:
            try:
                st = await self.subscription_service.get_status(account_id)
                if isinstance(st, dict):
                    plan_code = (st.get("plan") or "demo").lower()
                    preset = (st.get("risk_preset") or "standard").lower()
            except Exception:
                pass

        try:
            px = float(
                result.get("entry_price")
                or result.get("close")
                or (market_snapshot or {}).get("close")
                or (result.get("ohlc") or {}).get("close")
                or 0
            )
        except (TypeError, ValueError):
            px = 0.0

        sl = result.get("stop_loss") or result.get("sl")
        atr = result.get("atr14")
        mult = float(result.get("initial_stop_atr_mult") or 1.5)
        if (not sl or float(sl or 0) <= 0) and px > 0 and atr is not None:
            try:
                af = float(atr)
                if af > 0:
                    sl = px + mult * af if side == "SELL" else px - mult * af
            except (TypeError, ValueError):
                pass

        if self.portfolio_risk is None:
            return {"executed": False, "reason": "portfolio_risk_unavailable", "volume": 0.0}
        if px <= 0 or not sl or float(sl) <= 0:
            return {
                "executed": False,
                "reason": "entry_or_stop_missing_for_sizing",
                "volume": 0.0,
            }

        atr_f = None
        try:
            if atr is not None:
                atr_f = float(atr)
        except (TypeError, ValueError):
            atr_f = None

        try:
            sized = await self.portfolio_risk.size_order(
                account_id,
                sym,
                plan_code,
                entry_price=px,
                stop_loss=float(sl),
                side=side,
                atr14=atr_f,
            )
        except Exception as e:
            logger.exception("size_order failed")
            return {"executed": False, "reason": f"sizing_error:{e}", "volume": 0.0}

        if not sized.get("allow"):
            return {
                "executed": False,
                "reason": sized.get("reason") or "risk_blocked",
                "volume": 0.0,
                "portfolio_risk": sized,
            }
        try:
            volume = float(sized.get("volume") or 0)
        except (TypeError, ValueError):
            volume = 0.0
        if volume <= 0:
            return {
                "executed": False,
                "reason": "invalid_volume_after_sizing",
                "volume": 0.0,
                "portfolio_risk": sized,
            }

        out: dict[str, Any] = {
            "executed": False,
            "side": side,
            "symbol": sym,
            "volume": volume,
            "stop_loss": float(sl),
            "portfolio_risk": sized,
            "plan": plan_code,
            "risk_preset": preset,
        }
        try:
            if self.job_queue is not None and hasattr(self.job_queue, "enqueue_market_order"):
                await self.job_queue.enqueue_market_order(
                    account_id=account_id,
                    symbol=sym,
                    side=side,
                    volume=volume,
                    stop_loss=float(sl),
                )
                out["executed"] = True
                out["reason"] = "enqueued"
            elif self.worker_pool is not None and hasattr(self.worker_pool, "submit_market_order"):
                await self.worker_pool.submit_market_order(
                    account_id=account_id,
                    symbol=sym,
                    side=side,
                    volume=volume,
                    stop_loss=float(sl),
                )
                out["executed"] = True
                out["reason"] = "submitted"
            else:
                out["executed"] = False
                out["reason"] = "no_execution_backend"
        except Exception as e:
            out["executed"] = False
            out["reason"] = f"submit_error:{e}"
        return out
