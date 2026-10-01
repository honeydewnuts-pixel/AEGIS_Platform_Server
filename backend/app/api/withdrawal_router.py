"""Hybrid Ratchet withdrawal API — disabled unless WITHDRAWAL_MODULE_ENABLED=true."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.base import async_session_factory
from app.security import AuthContext, require_account_match, verify_api_key
from app.services.withdrawal_service import WithdrawalService, module_enabled

router = APIRouter(prefix="/api/withdrawal", tags=["Withdrawal Ratchet"])


class ConfigureBody(BaseModel):
    account_id: str
    start_equity: float = Field(..., gt=0, description="Client account equity in USD (any positive amount)")
    mode: str = Field("portfolio", description="portfolio | per_pair")
    risk_per_trade_pct: float = Field(0.5, gt=0, le=50, description="Risk label % for ratchet config (not V53.6 trade risk)")
    symbol: str | None = None


class RealizedBody(BaseModel):
    account_id: str
    trade_id: str
    realized_pnl: float
    symbol: str | None = None
    equity_after: float | None = None


class WithdrawBody(BaseModel):
    account_id: str
    amount: float
    idempotency_key: str
    symbol: str | None = None


@router.get("/status")
async def withdrawal_module_status():
    on = module_enabled()
    return {
        "module_enabled": on,
        "note": (
            "Withdrawal module is ACTIVE."
            if on
            else "Disabled. Set WITHDRAWAL_MODULE_ENABLED=true on the server to activate."
        ),
    }


@router.post("/configure")
async def configure_withdrawal(body: ConfigureBody, auth: AuthContext = Depends(verify_api_key)):
    require_account_match(auth, body.account_id)
    if not module_enabled():
        raise HTTPException(503, "Withdrawal module disabled (WITHDRAWAL_MODULE_ENABLED=false)")
    async with async_session_factory() as session:
        svc = WithdrawalService(session)
        try:
            return await svc.configure_account(
                body.account_id,
                body.start_equity,
                mode=body.mode,
                risk_per_trade_pct=body.risk_per_trade_pct,
                symbol=body.symbol,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@router.get("/dashboard/{account_id}")
async def withdrawal_dashboard(
    account_id: str,
    symbol: str | None = Query(None),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    async with async_session_factory() as session:
        svc = WithdrawalService(session)
        return await svc.get_dashboard(account_id, symbol)


@router.post("/realized-trade")
async def post_realized_trade(body: RealizedBody, auth: AuthContext = Depends(verify_api_key)):
    """Ingest a closed-trade realized net PnL (after broker costs)."""
    require_account_match(auth, body.account_id)
    if not module_enabled():
        raise HTTPException(503, "Withdrawal module disabled")
    async with async_session_factory() as session:
        svc = WithdrawalService(session)
        return await svc.apply_realized_trade(
            body.account_id,
            body.trade_id,
            body.realized_pnl,
            symbol=body.symbol,
            equity_after=body.equity_after,
        )


@router.post("/request")
async def request_withdrawal(body: WithdrawBody, auth: AuthContext = Depends(verify_api_key)):
    require_account_match(auth, body.account_id)
    if not module_enabled():
        raise HTTPException(503, "Withdrawal module disabled")
    async with async_session_factory() as session:
        svc = WithdrawalService(session)
        try:
            return await svc.create_withdrawal_request(
                body.account_id,
                body.amount,
                body.idempotency_key,
                symbol=body.symbol,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from e


@router.get("/history/{account_id}")
async def withdrawal_history(
    account_id: str,
    limit: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    async with async_session_factory() as session:
        svc = WithdrawalService(session)
        return {"account_id": account_id, "entries": await svc.history(account_id, limit)}
