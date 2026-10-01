"""Persistence layer for Hybrid Ratchet withdrawal management.

Module is gated by settings.WITHDRAWAL_MODULE_ENABLED (default False).
Does not call the trading path or alter V53.6 signals.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import WithdrawalAccount, WithdrawalLedger, WithdrawalRequest
from app.services.hybrid_ratchet import HybridRatchetEngine, RatchetConfig, RatchetState


def module_enabled() -> bool:
    return bool(getattr(settings, "WITHDRAWAL_MODULE_ENABLED", False))


def _engine() -> HybridRatchetEngine:
    return HybridRatchetEngine(
        RatchetConfig(
            withdraw_pct=float(getattr(settings, "WITHDRAWAL_WITHDRAW_PCT", 0.70)),
            retain_pct=float(getattr(settings, "WITHDRAWAL_RETAIN_PCT", 0.30)),
            arm_multiple=float(getattr(settings, "WITHDRAWAL_ARM_MULTIPLE", 2.0)),
            pause_dd_from_cap=float(getattr(settings, "WITHDRAWAL_PAUSE_DD_FROM_CAP", 0.20)),
        )
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_state(row: WithdrawalAccount, processed: set[str] | None = None) -> RatchetState:
    st = RatchetState(
        account_id=row.account_id,
        start_equity=float(row.start_equity),
        mode=row.mode,
        risk_per_trade_pct=float(row.risk_per_trade_pct),
        symbol=row.symbol,
        equity=float(row.equity),
        cap=float(row.cap),
        armed=bool(row.armed),
        paused=bool(row.paused),
        cumulative_withdrawn=float(row.cumulative_withdrawn),
        eligible_balance=float(row.eligible_balance),
        retained_profit_total=float(row.retained_profit_total),
        realized_trading_pnl=float(row.realized_trading_pnl),
        processed_trade_ids=processed or set(),
    )
    return st


def _apply_state(row: WithdrawalAccount, st: RatchetState) -> None:
    row.equity = st.equity
    row.cap = st.cap
    row.armed = st.armed
    row.paused = st.paused
    row.cumulative_withdrawn = st.cumulative_withdrawn
    row.eligible_balance = st.eligible_balance
    row.retained_profit_total = st.retained_profit_total
    row.realized_trading_pnl = st.realized_trading_pnl
    row.updated_at = _now()


class WithdrawalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.engine = _engine()

    async def configure_account(
        self,
        account_id: str,
        start_equity: float,
        *,
        mode: str = "portfolio",
        risk_per_trade_pct: float = 0.5,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        # Any positive account equity is allowed (not limited to cash-test ladder).
        se = float(start_equity)
        if se <= 0 or se > 50_000_000:
            raise ValueError("start_equity must be a positive amount (USD account equity)")
        risk = float(risk_per_trade_pct)
        if risk <= 0 or risk > 50:
            raise ValueError("risk_per_trade_pct must be between 0 exclusive and 50 inclusive")

        q = select(WithdrawalAccount).where(WithdrawalAccount.account_id == account_id)
        if mode == "per_pair":
            q = q.where(WithdrawalAccount.symbol == symbol)
        else:
            q = q.where(WithdrawalAccount.symbol.is_(None))
        existing = (await self.session.execute(q)).scalar_one_or_none()
        st = self.engine.seed(
            account_id,
            float(start_equity),
            mode=mode,
            risk_per_trade_pct=float(risk_per_trade_pct),
            symbol=symbol if mode == "per_pair" else None,
        )
        if existing:
            # Allow client to update starting equity / risk label later.
            # Resets CAP/arm/eligible for the new baseline; keeps cumulative_withdrawn history.
            existing.start_equity = st.start_equity
            existing.risk_per_trade_pct = st.risk_per_trade_pct
            existing.mode = st.mode
            existing.symbol = st.symbol
            existing.equity = st.equity
            existing.cap = 0.0
            existing.armed = False
            existing.paused = False
            existing.eligible_balance = 0.0
            existing.retained_profit_total = 0.0
            # realized_trading_pnl and cumulative_withdrawn retained for audit
            existing.enabled = True
            existing.updated_at = _now()
            await self.session.commit()
            await self.session.refresh(existing)
            return self._dashboard(existing)

        row = WithdrawalAccount(
            account_id=account_id,
            symbol=st.symbol,
            mode=st.mode,
            start_equity=st.start_equity,
            risk_per_trade_pct=st.risk_per_trade_pct,
            equity=st.equity,
            cap=0.0,
            armed=False,
            paused=False,
            cumulative_withdrawn=0.0,
            eligible_balance=0.0,
            retained_profit_total=0.0,
            realized_trading_pnl=0.0,
            enabled=True,
            created_at=_now(),
            updated_at=_now(),
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._dashboard(row)

    async def get_dashboard(self, account_id: str, symbol: str | None = None) -> dict[str, Any]:
        row = await self._get_row(account_id, symbol)
        if not row:
            return {"configured": False, "account_id": account_id, "module_enabled": module_enabled()}
        return self._dashboard(row)

    def _dashboard(self, row: WithdrawalAccount) -> dict[str, Any]:
        st = _row_to_state(row)
        snap = st.snapshot()
        return {
            "configured": True,
            "module_enabled": module_enabled(),
            "account_id": row.account_id,
            "symbol": row.symbol,
            "mode": row.mode,
            "start_equity": row.start_equity,
            "current_equity": row.equity,
            "equity": row.equity,  # alias for clients
            "cap": row.cap,
            "armed": row.armed,
            "paused": row.paused,
            "realized_trading_pnl": row.realized_trading_pnl,
            "eligible_balance": row.eligible_balance,
            "retained_profit": row.retained_profit_total,
            "cumulative_withdrawals": row.cumulative_withdrawn,
            "total_withdrawn": row.cumulative_withdrawn,  # alias for clients
            "total_value": snap["total_value"],
            "drawdown_from_cap_pct": snap["drawdown_from_cap_pct"],
            "drawdown_from_start_pct": snap["drawdown_from_start_pct"],
            "risk_per_trade_pct": row.risk_per_trade_pct,
            "enabled": row.enabled,
            "note": "Trading PnL and withdrawals are tracked separately; withdrawals are not trading losses.",
        }

    async def _get_row(self, account_id: str, symbol: str | None = None) -> WithdrawalAccount | None:
        q = select(WithdrawalAccount).where(WithdrawalAccount.account_id == account_id)
        if symbol:
            q = q.where(WithdrawalAccount.symbol == symbol)
        else:
            q = q.where(WithdrawalAccount.symbol.is_(None))
        return (await self.session.execute(q)).scalar_one_or_none()

    async def apply_realized_trade(
        self,
        account_id: str,
        trade_id: str,
        realized_pnl: float,
        *,
        symbol: str | None = None,
        equity_after: float | None = None,
    ) -> dict[str, Any]:
        if not module_enabled():
            return {"applied": False, "reason": "module_disabled"}

        row = await self._get_row(account_id, symbol)
        if not row or not row.enabled:
            return {"applied": False, "reason": "not_configured"}

        # Idempotency via unique ledger constraint
        existing = (
            await self.session.execute(
                select(WithdrawalLedger).where(
                    WithdrawalLedger.account_id == account_id,
                    WithdrawalLedger.trade_id == trade_id,
                    WithdrawalLedger.event_type == "realized_trade",
                )
            )
        ).scalar_one_or_none()
        if existing:
            return {"applied": False, "reason": "duplicate_trade_id", "dashboard": self._dashboard(row)}

        processed = set()
        st = _row_to_state(row, processed)
        res = self.engine.apply_realized_trade(
            st, trade_id=trade_id, realized_pnl=float(realized_pnl), equity_after=equity_after
        )
        _apply_state(row, st)
        self.session.add(
            WithdrawalLedger(
                account_id=account_id,
                symbol=row.symbol,
                trade_id=trade_id,
                event_type="realized_trade",
                realized_pnl=float(realized_pnl),
                excess=res.excess,
                to_eligible=res.to_eligible,
                to_cap=res.to_cap,
                equity_after=st.equity,
                cap_after=st.cap,
                detail=res.reason,
                created_at=_now(),
            )
        )
        await self.session.commit()
        return {
            "applied": res.applied,
            "reason": res.reason,
            "excess": res.excess,
            "to_eligible": res.to_eligible,
            "to_cap": res.to_cap,
            "dashboard": self._dashboard(row),
        }

    async def create_withdrawal_request(
        self,
        account_id: str,
        amount: float,
        idempotency_key: str,
        *,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        if not module_enabled():
            raise RuntimeError("withdrawal module disabled")

        # Idempotent request
        prior = (
            await self.session.execute(
                select(WithdrawalRequest).where(WithdrawalRequest.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if prior:
            return {
                "id": prior.id,
                "status": prior.status,
                "amount": prior.amount,
                "idempotent": True,
            }

        row = await self._get_row(account_id, symbol)
        if not row:
            raise ValueError("not_configured")

        st = _row_to_state(row)
        res = self.engine.request_withdrawal(st, float(amount))
        if not res.applied:
            raise ValueError(res.reason)

        _apply_state(row, st)
        req_id = str(uuid.uuid4())
        req = WithdrawalRequest(
            id=req_id,
            account_id=account_id,
            amount=float(amount),
            status="pending",
            idempotency_key=idempotency_key,
            detail="Reserved from eligible balance; transfer not executed by AEGIS",
            created_at=_now(),
            updated_at=_now(),
        )
        self.session.add(req)
        self.session.add(
            WithdrawalLedger(
                account_id=account_id,
                symbol=row.symbol,
                trade_id=f"wd:{req_id}",
                event_type="withdrawal_request",
                realized_pnl=0.0,
                excess=float(amount),
                to_eligible=-float(amount),
                to_cap=0.0,
                equity_after=st.equity,
                cap_after=st.cap,
                detail="pending",
                created_at=_now(),
            )
        )
        await self.session.commit()
        return {
            "id": req_id,
            "status": "pending",
            "amount": float(amount),
            "idempotent": False,
            "dashboard": self._dashboard(row),
            "note": "Request recorded only. Actual fund transfer requires authorized payment/broker process.",
        }

    async def history(self, account_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(WithdrawalLedger)
                .where(WithdrawalLedger.account_id == account_id)
                .order_by(WithdrawalLedger.id.desc())
                .limit(min(limit, 200))
            )
        ).scalars().all()
        return [
            {
                "trade_id": r.trade_id,
                "event_type": r.event_type,
                "realized_pnl": r.realized_pnl,
                "excess": r.excess,
                "to_eligible": r.to_eligible,
                "to_cap": r.to_cap,
                "equity_after": r.equity_after,
                "cap_after": r.cap_after,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
