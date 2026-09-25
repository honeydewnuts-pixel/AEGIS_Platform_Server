"""Independent MT5 OHLC stream ingestion (CopyRates / worker → AEGIS)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import verify_api_key, AuthContext

router = APIRouter(prefix="/api/mt5", tags=["MT5 OHLC Stream"])


class OhlcBar(BaseModel):
    time: int = Field(..., description="Unix seconds bar open time")
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread: int = 0
    bar_status: str = "CLOSED"


class OhlcStreamIn(BaseModel):
    account_id: str = ""
    symbol: str
    timeframe: str = "M5"
    bars: list[OhlcBar]
    current_bar: OhlcBar | None = None
    closed_bar: OhlcBar | None = None
    source: str = "mt5_ea"
    symbol_broker: str | None = None


@router.post("/ohlc/stream")
async def ingest_ohlc_stream(
    request: Request,
    body: OhlcStreamIn,
    auth: AuthContext = Depends(verify_api_key),
):
    account_id = body.account_id or auth.account_id or ""
    if not auth.is_admin:
        if not auth.account_id:
            raise HTTPException(403, "API key not bound to an account")
        account_id = auth.account_id
    svc = getattr(request.app.state, "ohlc_stream", None)
    if svc is None:
        raise HTTPException(503, "OHLC stream service not initialized")
    bars = [b.model_dump() for b in body.bars]
    result = svc.ingest(
        account_id=account_id,
        symbol=body.symbol,
        timeframe=body.timeframe,
        bars=bars,
        source=body.source,
        current_bar=body.current_bar.model_dump() if body.current_bar else None,
        closed_bar=body.closed_bar.model_dump() if body.closed_bar else None,
        symbol_broker=body.symbol_broker,
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "ingest failed")

    # Autonomous MultiSymbol path: CLOSED bar → evaluate → confidence gate → Executor
    # Does NOT depend on mobile app being open or dropdown symbol selection.
    auto_out = None
    try:
        closed = body.closed_bar
        is_closed = closed is not None or any(
            (b.bar_status or "").upper() == "CLOSED" for b in (body.bars or [])[-1:]
        )
        if is_closed or body.closed_bar is not None:
            auto = getattr(request.app.state, "autonomous_ohlc", None)
            if auto is not None:
                # Prefer full payload from stream service
                svc = getattr(request.app.state, "ohlc_stream", None)
                payload = (
                    svc.get(account_id, body.symbol, body.timeframe) if svc else None
                ) or result
                auto_out = await auto.process_closed_bar(
                    app=request.app,
                    account_id=account_id,
                    symbol=body.symbol,
                    timeframe=body.timeframe or "M5",
                    stream_payload=payload if isinstance(payload, dict) else {},
                )
    except Exception as e:
        auto_out = {"published": False, "reason": f"auto_error:{e}"}

    resp = {"status": "ok", **result}
    if auto_out is not None:
        resp["autonomous"] = auto_out
    return resp


@router.get("/ohlc/latest")
async def latest_ohlc(
    request: Request,
    symbol: str,
    timeframe: str = "M5",
    account_id: str = "",
    auth: AuthContext = Depends(verify_api_key),
):
    aid = account_id or auth.account_id or ""
    if not auth.is_admin and auth.account_id:
        aid = auth.account_id
    svc = getattr(request.app.state, "ohlc_stream", None)
    if svc is None:
        raise HTTPException(503, "OHLC stream service not initialized")
    payload = svc.get(aid, symbol, timeframe)
    if not payload:
        raise HTTPException(404, "No OHLC stream for this account/symbol/timeframe")
    return payload


@router.get("/ohlc/status")
async def ohlc_status(
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    svc = getattr(request.app.state, "ohlc_stream", None)
    if svc is None:
        return {"streams": [], "count": 0}
    aid = None if auth.is_admin else auth.account_id
    return svc.status(aid)
