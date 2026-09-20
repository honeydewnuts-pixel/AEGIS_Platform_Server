"""MT5 AEGIS_Executor — poll pending signals (single or multi-pair) and ACK."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.security import verify_api_key, require_account_match, AuthContext

router = APIRouter(prefix="/api/executor", tags=["MT5 Executor"])


def _registry(request: Request):
    return getattr(request.app.state, "registry_service", None) or getattr(
        request.app.state, "registry", None
    )


def _is_symbol_authorized(request: Request, symbol: str) -> tuple[bool, str, dict[str, Any] | None]:
    """Good/tradeable instruments only — research-disabled pairs never reach Executor."""
    reg = _registry(request)
    sym = (symbol or "").strip().upper().split(".")[0].split("#")[0]
    if not reg:
        return True, "registry_unavailable_fail_open_research", None  # still publish; EA/router gates
    try:
        rows = reg.list_instruments(tradeable_only=False)
    except Exception:
        return False, "registry_error", None
    match = next((r for r in rows if str(r.get("instrument") or "").upper() == sym), None)
    if match is None:
        return False, "unknown_instrument", None
    if match.get("good") is False or not match.get("tradeable"):
        return False, f"not_authorized:{match.get('router_status')}", match
    # V2OPT insufficient already sets good=False in registry_service
    return True, "ok", match


class AckBody(BaseModel):
    account_id: str
    signal_id: str
    ticket: int = 0
    order_ticket: int = 0
    deal_ticket: int = 0
    position_ticket: int = 0
    retcode: int = 0
    ok: bool = True
    message: str = ""
    symbol: str = ""
    side: str = ""
    volume: float = 0.0


@router.get("/universe")
async def executor_universe(
    request: Request,
    account_id: str = Query(...),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Symbols this account may execute (Good + tradeable registry)."""
    require_account_match(auth, account_id)
    reg = _registry(request)
    if not reg:
        return {"account_id": account_id, "symbols": [], "note": "registry_unavailable"}
    rows = reg.list_instruments(tradeable_only=False)
    good = [
        {
            "symbol": r.get("instrument"),
            "tradeable": bool(r.get("tradeable")),
            "good": bool(r.get("good")),
            "router_status": r.get("router_status"),
            "eligible_rulebooks": r.get("eligible_rulebooks") or [],
        }
        for r in rows
        if r.get("good") and r.get("tradeable")
    ]
    return {
        "account_id": account_id,
        "symbols": [g["symbol"] for g in good],
        "instruments": good,
        "count": len(good),
        "policy": "one_aegis_position_per_symbol",
        "same_account_multi_pair": True,
    }


@router.get("/pending")
async def get_pending_signal(
    request: Request,
    account_id: str = Query(...),
    symbol: str = Query(..., description="Chart symbol, e.g. EURUSD"),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "executor_signals", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Executor signal service not ready")
    raw = symbol.strip()
    base = raw.split(".")[0].split("#")[0].upper()
    ok, reason, _ = _is_symbol_authorized(request, base)
    if not ok:
        return {
            "has_signal": False,
            "signal": "HOLD",
            "symbol": base,
            "account_id": account_id,
            "authorized": False,
            "reason": reason,
        }
    row = svc.get_pending(account_id, base) or svc.get_pending(account_id, raw.upper())
    if not row:
        return {
            "has_signal": False,
            "signal": "HOLD",
            "symbol": base,
            "account_id": account_id,
            "authorized": True,
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
        "authorized": True,
    }


@router.get("/pending-batch")
async def get_pending_batch(
    request: Request,
    account_id: str = Query(...),
    symbols: str = Query(
        "",
        description="Comma-separated symbols; empty = use registry Good universe",
    ),
    max_symbols: int = Query(24, ge=1, le=64),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Multi-pair poll: one request, many symbols (Option B Executor)."""
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "executor_signals", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Executor signal service not ready")

    if symbols.strip():
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:max_symbols]
    else:
        uni = await executor_universe(request, account_id=account_id, auth=auth)
        sym_list = list(uni.get("symbols") or [])
    sym_list = sym_list[:max_symbols]

    authorized: list[str] = []
    blocked: list[dict[str, str]] = []
    for s in sym_list:
        ok, reason, _ = _is_symbol_authorized(request, s)
        if ok:
            authorized.append(s.split(".")[0].split("#")[0].upper())
        else:
            blocked.append({"symbol": s, "reason": reason})

    pending = svc.get_pending_many(account_id, authorized)
    return {
        "account_id": account_id,
        "polled": authorized,
        "blocked": blocked,
        "count": len(pending),
        "signals": pending,
        "policy": "one_aegis_position_per_symbol",
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
    return {
        "acked": ok,
        "signal_id": body.signal_id,
        "ticket": body.ticket or body.order_ticket,
        "order_ticket": body.order_ticket or body.ticket,
        "deal_ticket": body.deal_ticket,
        "position_ticket": body.position_ticket,
        "retcode": body.retcode,
        "symbol": body.symbol,
        "side": body.side,
        "volume": body.volume,
        "ok": body.ok,
        "message": body.message,
    }
