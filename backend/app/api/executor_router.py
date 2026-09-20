"""MT5 AEGIS_Executor.mq5 — poll pending signals and ACK fills."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.security import verify_api_key, require_account_match, AuthContext

router = APIRouter(prefix="/api/executor", tags=["MT5 Executor"])


class AckBody(BaseModel):
    account_id: str
    signal_id: str
    ticket: int = 0
    ok: bool = True
    message: str = ""
    symbol: str = ""
    side: str = ""


@router.get("/pending")
async def get_pending_signal(
    request: Request,
    account_id: str = Query(...),
    symbol: str = Query(..., description="Chart symbol, e.g. EURUSD or EURUSD.r"),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "executor_signals", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Executor signal service not ready")
    # Strip broker suffix e.g. EURUSD.r -> EURUSD for match; also try raw
    raw = symbol.strip()
    base = raw.split(".")[0].split("#")[0].upper()
    row = svc.get_pending(account_id, base) or svc.get_pending(account_id, raw.upper())
    if not row:
        return {
            "has_signal": False,
            "signal": "HOLD",
            "symbol": base,
            "account_id": account_id,
        }
    return {
        "has_signal": True,
        "signal": row["side"],
        "side": row["side"],
        "signal_id": row["signal_id"],
        "symbol": row["symbol"],
        "account_id": account_id,
        "confidence": row.get("confidence"),
        "rule_name": row.get("rule_name"),
        "volume": row.get("volume"),
        "stop_loss": row.get("stop_loss"),
        "take_profit": row.get("take_profit"),
        "created_at_ms": row.get("created_at_ms"),
        "details": row.get("details"),
    }


@router.post("/ack")
async def ack_signal(
    body: AckBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, body.account_id)
    svc = getattr(request.app.state, "executor_signals", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Executor signal service not ready")
    ok = svc.ack(
        body.account_id,
        body.signal_id,
        ticket=body.ticket,
        ok=body.ok,
        message=body.message,
    )
    return {"acked": ok, "signal_id": body.signal_id, "ticket": body.ticket}
