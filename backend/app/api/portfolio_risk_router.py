"""Client portfolio risk: equity, tolerance %, multi-symbol capacity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import verify_api_key, require_account_match, AuthContext

router = APIRouter(prefix="/api/portfolio", tags=["portfolio-risk"])


class EquityBody(BaseModel):
    account_id: str
    equity_usd: float = Field(..., ge=0)
    source: str = "client"


class ToleranceBody(BaseModel):
    account_id: str
    risk_tolerance_pct: float


class ModeBody(BaseModel):
    account_id: str
    trading_mode: str  # multi_symbol | chart_only


class MinNotionalBody(BaseModel):
    account_id: str
    symbol: str
    min_notional_usd: float = Field(..., gt=0)
    min_lot: float = Field(0.01, gt=0)


@router.get("/status")
async def portfolio_status(
    request: Request,
    account_id: str,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "portfolio_risk", None)
    if svc is None:
        raise HTTPException(503, "Portfolio risk service not ready")
    data = await svc.portfolio_summary(account_id)
    if data.get("error"):
        raise HTTPException(404, data["error"])
    return data


@router.post("/equity")
async def set_equity(
    body: EquityBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    try:
        return await svc.set_equity(body.account_id, body.equity_usd, body.source)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/risk-tolerance")
async def set_tolerance(
    body: ToleranceBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    try:
        return await svc.set_risk_tolerance_pct(body.account_id, body.risk_tolerance_pct)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/trading-mode")
async def set_mode(
    body: ModeBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    try:
        return await svc.set_trading_mode(body.account_id, body.trading_mode)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/min-notional")
async def set_min_notional(
    body: MinNotionalBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """EA/broker reports minimum trade size for a symbol."""
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    await svc.upsert_min_notional(body.symbol, body.min_notional_usd, body.min_lot)
    return {"status": "ok", "symbol": body.symbol.upper().split(".")[0]}


@router.get("/size")
async def size_preview(
    request: Request,
    account_id: str,
    symbol: str,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    svc = request.app.state.portfolio_risk
    sub = request.app.state.subscription_service
    rec = await sub.get_record(account_id) if hasattr(sub, "get_record") else None
    plan = "demo"
    if isinstance(rec, dict):
        plan = rec.get("plan") or "demo"
    return await svc.size_order(account_id, symbol, plan)
