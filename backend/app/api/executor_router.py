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
        return False, "registry_unavailable_fail_closed", None  # Stage 2.5: never authorize on missing registry
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
        # Stage 5: durable queue survives API restart
        try:
            from app.db.base import async_session_factory
            from app.services.durable_execution_queue import get_durable_execution_queue
            async with async_session_factory() as session:
                row = await get_durable_execution_queue().get_pending(session, account_id, base)
                if row:
                    await session.commit()
                    # hydrate memory so subsequent polls are fast
                    with svc._lock:
                        svc._pending[svc._key(account_id, base)] = dict(row)
        except Exception:
            row = None
    if not row:
        return {
            "has_signal": False,
            "signal": "HOLD",
            "symbol": base,
            "account_id": account_id,
            "authorized": True,
        }
    # Stage 6: emergency stop blocks NEW order delivery to Executor
    try:
        from app.db.base import async_session_factory
        from app.services.operational_control_service import get_operational_control_service
        async with async_session_factory() as session:
            if await get_operational_control_service().is_emergency_stop_on(session):
                return {
                    "has_signal": False,
                    "signal": "HOLD",
                    "symbol": base,
                    "account_id": account_id,
                    "authorized": True,
                    "reason": "emergency_stop",
                    "emergency_stop": True,
                }
    except Exception:
        pass
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
        "atr14": row.get("atr14"),
        "initial_stop_atr_mult": row.get("initial_stop_atr_mult", 1.5),
        "max_hold_bars": row.get("max_hold_bars", 72),
        "trail_atr_mult": row.get("trail_atr_mult", 0.75),
        "methodology": row.get("methodology") or "",
        "take_profit": row.get("take_profit"),
        "created_at_ms": row.get("created_at_ms"),
        "details": row.get("details"),
        "authorized": (row.get("production_authorized") is True),
        "production_authorized": (row.get("production_authorized") is True),
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
    # Stage 5: fill gaps from durable queue after restart
    try:
        from app.db.base import async_session_factory
        from app.services.durable_execution_queue import get_durable_execution_queue
        have = {str(s.get("symbol") or "").upper() for s in pending}
        missing = [s for s in authorized if s.upper() not in have]
        if missing:
            async with async_session_factory() as session:
                dq = get_durable_execution_queue()
                for sym in missing:
                    drow = await dq.get_pending(session, account_id, sym)
                    if drow:
                        pending.append(drow)
                        with svc._lock:
                            svc._pending[svc._key(account_id, sym)] = dict(drow)
                await session.commit()
    except Exception:
        pass
    pending = [
        s for s in pending
        if getattr(svc, "is_execution_authorized", lambda r: r.get("production_authorized") is True)(s)
    ]
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
    result = svc.ack(
        body.account_id,
        body.signal_id,
        ticket=body.ticket,
        order_ticket=body.order_ticket,
        deal_ticket=body.deal_ticket,
        position_ticket=body.position_ticket,
        retcode=body.retcode,
        ok=body.ok,
        message=body.message,
        symbol=body.symbol,
        side=body.side,
        volume=body.volume,
    )
    # Stage 5: durable queue terminal state (idempotent)
    try:
        from app.db.base import async_session_factory
        from app.services.durable_execution_queue import get_durable_execution_queue
        async with async_session_factory() as session:
            await get_durable_execution_queue().ack(
                session,
                account_id=body.account_id,
                signal_id=body.signal_id,
                ok=bool(body.ok),
                position_ticket=int(body.position_ticket or body.ticket or 0),
                order_ticket=int(body.order_ticket or 0),
                deal_ticket=int(body.deal_ticket or 0),
                message=body.message or "",
            )
            await session.commit()
    except Exception:
        pass
    # Durable lifecycle: ACK is not open risk unless position_ticket > 0 and risk known
    try:
        from app.db.base import async_session_factory
        from app.services.durable_lifecycle_service import DurableLifecycleService
        from app.services.position_lifecycle_service import get_lifecycle_service
        life_mem = get_lifecycle_service()
        ok_flag = bool(body.ok if body.ok is not None else result.get("ok", True))
        pos_ticket = int(body.position_ticket or 0)
        risk_usd = result.get("risk_usd_at_open")
        if risk_usd is None:
            risk_usd = result.get("estimated_monetary_risk")
        if not result.get("idempotent"):
            async with async_session_factory() as session:
                dur = DurableLifecycleService()
                row, should_risk = await dur.on_ack(
                    session,
                    account_id=body.account_id,
                    signal_id=body.signal_id,
                    ok=ok_flag,
                    position_ticket=pos_ticket,
                    order_ticket=int(body.order_ticket or body.ticket or 0),
                    deal_ticket=int(body.deal_ticket or 0),
                    symbol=str(body.symbol or result.get("symbol") or ""),
                    side=str(body.side or result.get("side") or ""),
                    volume=float(body.volume or 0.0) if body.volume is not None else None,
                    risk_usd=float(risk_usd) if risk_usd is not None else None,
                )
                if should_risk and risk_usd is not None:
                    pr = getattr(request.app.state, "portfolio_risk", None)
                    if pr is not None:
                        # Stage 3.3: same session as lifecycle (atomic with commit below)
                        await pr.record_open_risk(
                            body.account_id, float(risk_usd), session=session
                        )
                    await dur.mark_risk_recorded(
                        session, account_id=body.account_id, signal_id=body.signal_id, risk_usd=float(risk_usd)
                    )
                await session.commit()
                result = {
                    **result,
                    "lifecycle": (row.state if row else "UNKNOWN"),
                    "reconciliation_required": bool(row and row.state == "BROKER_CONFIRMED_OPEN" and row.risk_usd_at_open is None),
                }
        # Mirror in-memory for gates (non-authoritative)
        life_mem.on_ack(
            account_id=body.account_id,
            signal_id=body.signal_id,
            ok=ok_flag,
            position_ticket=pos_ticket,
            order_ticket=int(body.order_ticket or body.ticket or 0),
            deal_ticket=int(body.deal_ticket or 0),
            symbol=str(body.symbol or result.get("symbol") or ""),
            side=str(body.side or result.get("side") or ""),
            volume=float(body.volume or 0.0),
            risk_usd=float(risk_usd) if risk_usd is not None else None,
            idempotent=bool(result.get("idempotent")),
        )
        if ok_flag and pos_ticket > 0 and risk_usd is not None and not result.get("idempotent"):
            life_mem.mark_open_risk_recorded(body.account_id, body.signal_id, float(risk_usd))
    except Exception as exc:
        result = {
            **result,
            "lifecycle_accounting_error": str(exc)[:300],
            "reconciliation_required": True,
        }
        try:
            from app.services.position_lifecycle_service import get_lifecycle_service
            get_lifecycle_service().record_accounting_failure({
                "type": "ack_lifecycle_exception",
                "account_id": body.account_id,
                "signal_id": body.signal_id,
                "error": str(exc)[:300],
            })
        except Exception:
            pass
        # Additive: subscriber notification inbox (does not change ack semantics)
    try:
        notif = getattr(request.app.state, "notifications", None)
        if notif is not None and not result.get("idempotent"):
            await notif.emit_execution(
                body.account_id,
                signal_id=body.signal_id,
                symbol=str(body.symbol or result.get("symbol") or ""),
                side=str(body.side or result.get("side") or ""),
                volume=body.volume if body.volume is not None else result.get("volume"),
                ok=bool(body.ok if body.ok is not None else result.get("ok", True)),
                message=str(body.message or ""),
            )
    except Exception:
        pass
    return result




class CloseBody(BaseModel):
    account_id: str
    signal_id: str = ""
    position_ticket: int = 0
    symbol: str = ""
    side: str = ""
    realized_pnl: float | None = None
    risk_usd_at_open: float | None = None
    reason: str = "broker_confirmed_close"


@router.post("/position-closed")
async def position_closed(
    body: CloseBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Broker-confirmed close → release open risk (idempotent)."""
    require_account_match(auth, body.account_id)
    from app.db.base import async_session_factory
    from app.services.durable_lifecycle_service import DurableLifecycleService
    from app.services.position_lifecycle_service import get_lifecycle_service
    released = 0.0
    status = "RECONCILIATION_REQUIRED"
    async with async_session_factory() as session:
        dur = DurableLifecycleService()
        risk_to_release, status = await dur.on_close(
            session,
            account_id=body.account_id,
            signal_id=body.signal_id,
            position_ticket=int(body.position_ticket or 0),
            symbol=str(body.symbol or ""),
            close_reason=str(body.reason or ""),
        )
        if status == "RISK_RELEASED" and risk_to_release and risk_to_release > 0:
            pr = getattr(request.app.state, "portfolio_risk", None)
            if pr is not None:
                # Stage 3.3: same session as lifecycle transition
                await pr.release_open_risk(
                    body.account_id, float(risk_to_release), session=session
                )
            released = float(risk_to_release)
        await session.commit()
    # Mirror memory (idempotent)
    get_lifecycle_service().on_broker_close(
        account_id=body.account_id,
        signal_id=body.signal_id,
        position_ticket=int(body.position_ticket or 0),
        symbol=str(body.symbol or ""),
        risk_usd=None,
    )
    return {
        "ok": status in ("RISK_RELEASED", "ALREADY_RELEASED"),
        "lifecycle": status,
        "released_risk_usd": released,
        "reconciliation_required": status == "RECONCILIATION_REQUIRED",
    }


@router.post("/reconcile-positions")
async def reconcile_positions(
    body: dict[str, Any],
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Restart-safe: broker positions vs durable lifecycle; release closed risk once."""
    account_id = str(body.get("account_id") or "")
    require_account_match(auth, account_id)
    positions = body.get("positions") or []
    from app.db.base import async_session_factory
    from app.services.durable_lifecycle_service import DurableLifecycleService
    from app.services.position_lifecycle_service import get_lifecycle_service
    async with async_session_factory() as session:
        dur = DurableLifecycleService()
        summary = await dur.reconcile(session, account_id, positions)
        stale = float(summary.get("stale_risk_released") or 0.0)
        if stale > 0:
            pr = getattr(request.app.state, "portfolio_risk", None)
            if pr is not None:
                # Stage 3.3: same session as reconcile lifecycle updates
                await pr.release_open_risk(account_id, stale, session=session)
        await session.commit()
    get_lifecycle_service().reconcile_from_broker(account_id, positions)
    auto = getattr(request.app.state, "autonomous_ohlc", None)
    if auto is None:
        try:
            from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService
            auto = AutonomousOhlcSignalService()
        except Exception:
            auto = None
    if auto is not None and hasattr(auto, "replace_sides_from_broker"):
        auto.replace_sides_from_broker(account_id, positions)
    return {"ok": True, **summary}


@router.get("/executions/recent")
async def recent_executions(
    request: Request,
    account_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Mobile/desktop poll: fills executed by MT5 Executor on VPS/PC."""
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "executor_signals", None)
    if svc is None:
        return {"account_id": account_id, "executions": [], "count": 0}
    rows = svc.recent_executions(account_id, limit)
    return {"account_id": account_id, "executions": rows, "count": len(rows)}
