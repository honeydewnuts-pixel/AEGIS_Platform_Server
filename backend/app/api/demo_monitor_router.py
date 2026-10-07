"""Demo Execution Monitor API — stage-by-stage visibility for demo validation.

Does not force trades. Distinguishes NO_SIGNAL from broken transport.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.security import AuthContext, require_account_match, verify_api_key

router = APIRouter(prefix="/api/demo-monitor", tags=["Demo Execution Monitor"])

@router.get("")
@router.get("/")
async def demo_monitor_root(
    request: Request,
    account_id: str | None = Query(None),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Admin/ops: optional account_id query; otherwise returns monitor availability."""
    mon = getattr(request.app.state, "demo_monitor", None)
    if mon is None:
        raise HTTPException(503, "Demo monitor not initialized")
    if account_id:
        require_account_match(auth, account_id)
        return mon.build(
            account_id=account_id,
            ohlc_stream=getattr(request.app.state, "ohlc_stream", None),
            executor_signals=getattr(request.app.state, "executor_signals", None),
            worker_pool=getattr(request.app.state, "worker_pool", None),
        )
    # Fleet-lite: monitor is up; clients pass account_id for full stages
    return {
        "monitor": "ready",
        "hint": "GET /api/demo-monitor/{account_id} for full 10-stage status",
        "admin": bool(getattr(auth, "is_admin", False) or getattr(auth, "admin", False)),
    }


@router.get("/{account_id}")
async def demo_monitor_status(
    account_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Full 10-stage monitor for one account."""
    require_account_match(auth, account_id)
    mon = getattr(request.app.state, "demo_monitor", None)
    if mon is None:
        raise HTTPException(503, "Demo monitor not initialized")
    return mon.build(
        account_id=account_id,
        ohlc_stream=getattr(request.app.state, "ohlc_stream", None),
        executor_signals=getattr(request.app.state, "executor_signals", None),
        worker_pool=getattr(request.app.state, "worker_pool", None),
    )


@router.get("/{account_id}/events")
async def demo_monitor_events(
    account_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    log = getattr(request.app.state, "trade_event_log", None)
    if log is None:
        return {"account_id": account_id, "events": []}
    return {"account_id": account_id, "events": log.for_account(account_id, limit=limit)}


@router.get("/{account_id}/signal/{signal_id}")
async def demo_monitor_signal_trace(
    account_id: str,
    signal_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Trace one signal_id across stages."""
    require_account_match(auth, account_id)
    log = getattr(request.app.state, "trade_event_log", None)
    events = log.for_signal(signal_id) if log else []
    # filter to account for safety
    events = [e for e in events if e.get("account_id") == account_id or not e.get("account_id")]
    return {"account_id": account_id, "signal_id": signal_id, "events": events}


class ControlledTestSignalBody(BaseModel):
    account_id: str
    symbol: str = "GBPUSD"
    side: str = Field("SELL", description="BUY or SELL")
    volume: float = 0.01
    confidence: float = 0.80
    rule_name: str = "controlled_demo_test"
    details: str = "Controlled demo execution test — not a strategy signal"


@router.post("/controlled-test-signal")
async def publish_controlled_test_signal(
    body: ControlledTestSignalBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Admin or account owner: enqueue a controlled test signal for Executor Test 3.

    Does not bypass broker risk. Does not mark production authorization.
    """
    require_account_match(auth, body.account_id)
    # Prefer admin for safety; allow account owner on demo plans only would need sub lookup —
    # keep owner-allowed so user can self-test demo.
    svc = getattr(request.app.state, "executor_signals", None)
    if svc is None:
        raise HTTPException(503, "Executor signal service not initialized")
    side = body.side.strip().upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(400, "side must be BUY or SELL")
    # Demo-only engineering path: controlled_demo_authorized=True,
    # production_authorized remains False (never promotes production).
    sid = svc.publish(
        account_id=body.account_id,
        symbol=body.symbol,
        side=side,
        confidence=body.confidence,
        rule_name=body.rule_name or "controlled_demo_test",
        volume=body.volume,
        details=body.details,
        methodology="controlled_demo_test",
        production_authorized=False,
        controlled_demo_authorized=True,
    )
    # Stage 5: persist authorized controlled_demo to durable queue
    try:
        from app.db.base import async_session_factory
        from app.services.durable_execution_queue import get_durable_execution_queue
        row = svc.get_pending(body.account_id, body.symbol) if hasattr(svc, "get_pending") else None
        # reconstruct payload from publish args if pending already set
        async with async_session_factory() as session:
            payload = {
                "signal_id": sid,
                "account_id": body.account_id,
                "symbol": body.symbol,
                "side": (body.side or "SELL").upper(),
                "volume": body.volume,
                "methodology": "controlled_demo_test",
                "rule_name": body.rule_name or "controlled_demo_test",
                "production_authorized": False,
                "controlled_demo_authorized": True,
                "confidence": 0.0,
                "details": "controlled_demo_test",
            }
            if row:
                payload.update(row)
                payload["signal_id"] = sid
            await get_durable_execution_queue().enqueue(session, payload)
            await session.commit()
    except Exception:
        pass
    if not sid:
        raise HTTPException(400, "publish failed")
    log = getattr(request.app.state, "trade_event_log", None)
    if log:
        log.record(
            stage="signal_generated",
            account_id=body.account_id,
            status="CONTROLLED_TEST",
            signal_id=sid,
            symbol=body.symbol,
            detail="controlled test signal published to pending queue",
        )
    return {
        "ok": True,
        "signal_id": sid,
        "account_id": body.account_id,
        "symbol": body.symbol.strip().upper(),
        "side": side,
        "volume": body.volume,
        "note": "Signal is pending. Attach Executor with UseServerSignals=true and poll /api/executor/pending-batch.",
    }
