"""Client portfolio risk: equity, tolerance %, account/broker specs, multi-symbol capacity."""

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
    trading_mode: str


class MinNotionalBody(BaseModel):
    account_id: str
    symbol: str
    min_notional_usd: float = Field(..., gt=0)
    min_lot: float = Field(0.01, gt=0)


class AccountProfileBody(BaseModel):
    account_id: str
    account_type: str | None = Field(None, description="standard | micro | custom")
    account_currency: str | None = None
    broker_id: str | None = None


class InstrumentSpecBody(BaseModel):
    account_id: str
    symbol: str
    account_type: str = "standard"
    broker_id: str = "default"
    contract_size: float = Field(..., gt=0)
    volume_min: float = Field(..., gt=0)
    volume_max: float = Field(..., gt=0)
    volume_step: float = Field(..., gt=0)
    tick_size: float = Field(..., gt=0)
    tick_value: float | None = None
    margin_per_lot: float | None = None
    base_currency: str = "USD"
    quote_currency: str = "USD"
    profit_currency: str | None = None
    min_notional_usd: float | None = None
    source: str = "mt5"


class SizePreviewBody(BaseModel):
    account_id: str
    symbol: str
    side: str = "SELL"
    entry_price: float = Field(..., gt=0)
    stop_loss: float
    atr14: float | None = None
    available_margin: float | None = None


@router.get("/status/{account_id}")
async def portfolio_status(
    account_id: str,
    request: Request,
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


@router.post("/account-profile")
async def set_account_profile(
    body: AccountProfileBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Set broker account type (standard/micro/custom) and currency — not risk tolerance."""
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    try:
        return await svc.set_account_profile(
            body.account_id,
            account_type=body.account_type,
            account_currency=body.account_currency,
            broker_id=body.broker_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/instrument-spec")
async def set_instrument_spec(
    body: InstrumentSpecBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """MT5 EA/Feed posts SymbolInfo contract specifications for sizing."""
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    try:
        return await svc.upsert_instrument_spec(
            body.symbol,
            account_type=body.account_type,
            broker_id=body.broker_id,
            contract_size=body.contract_size,
            volume_min=body.volume_min,
            volume_max=body.volume_max,
            volume_step=body.volume_step,
            tick_size=body.tick_size,
            tick_value=body.tick_value,
            margin_per_lot=body.margin_per_lot,
            base_currency=body.base_currency,
            quote_currency=body.quote_currency,
            profit_currency=body.profit_currency,
            min_notional_usd=body.min_notional_usd,
            source=body.source,
        )
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
    """Legacy EA path: min notional + min lot only."""
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    await svc.upsert_min_notional(body.symbol, body.min_notional_usd, body.min_lot)
    return {"status": "ok", "symbol": body.symbol.upper().split(".")[0]}


@router.post("/size")
async def size_preview(
    body: SizePreviewBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Preview sizing with entry/stop (fail-closed if risk/spec invalid)."""
    require_account_match(auth, body.account_id)
    svc = request.app.state.portfolio_risk
    sub = request.app.state.subscription_service
    rec = await sub.get_record(body.account_id) if hasattr(sub, "get_record") else None
    plan = "demo"
    if isinstance(rec, dict):
        plan = rec.get("plan") or "demo"
    return await svc.size_order(
        body.account_id,
        body.symbol,
        plan,
        entry_price=body.entry_price,
        stop_loss=body.stop_loss,
        side=body.side,
        atr14=body.atr14,
        available_margin=body.available_margin,
    )


@router.get("/size")
async def size_preview_get(
    request: Request,
    account_id: str,
    symbol: str,
    auth: AuthContext = Depends(verify_api_key),
):
    """Legacy GET without entry/stop — returns explicit rejection (no silent default lots)."""
    require_account_match(auth, account_id)
    svc = request.app.state.portfolio_risk
    sub = request.app.state.subscription_service
    rec = await sub.get_record(account_id) if hasattr(sub, "get_record") else None
    plan = "demo"
    if isinstance(rec, dict):
        plan = rec.get("plan") or "demo"
    return await svc.size_order(account_id, symbol, plan)
