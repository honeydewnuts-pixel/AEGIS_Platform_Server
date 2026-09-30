"""
Admin / Owner Operations Dashboard API.

Fleet-wide view of market data, clients, signal path, executor, risk, and orders.
Protected by admin API key (require_admin).
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.security import AuthContext, require_admin, verify_api_key

router = APIRouter(prefix="/api/admin", tags=["Admin Ops Dashboard"])


def _age_sec(ms: int | None) -> float | None:
    if not ms:
        return None
    return max(0.0, (time.time() * 1000 - int(ms)) / 1000.0)


@router.get("/ops-dashboard")
async def ops_dashboard(
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Institutional-style trading operations snapshot for owner/admin."""
    require_admin(auth)
    now_ms = int(time.time() * 1000)

    # --- Market data (OHLC streams) ---
    ohlc = getattr(request.app.state, "ohlc_stream", None)
    streams: list[dict[str, Any]] = []
    if ohlc is not None:
        try:
            st = ohlc.status(None)
            streams = list(st.get("streams") or [])
        except Exception as e:  # noqa: BLE001
            streams = []
            market_error = str(e)
        else:
            market_error = None
    else:
        market_error = "ohlc_stream not initialized"

    fresh = [s for s in streams if (s.get("age_sec") is not None and float(s["age_sec"]) <= 600)]
    stale = [s for s in streams if (s.get("age_sec") is not None and float(s["age_sec"]) > 600)]
    symbols = sorted({str(s.get("symbol") or "") for s in streams if s.get("symbol")})

    market_data = {
        "status": "OK" if fresh and not market_error else ("STALE" if streams else "NO_DATA"),
        "streams_total": len(streams),
        "streams_fresh": len(fresh),
        "streams_stale": len(stale),
        "symbols": symbols[:40],
        "error": market_error,
        "samples": streams[:24],
    }

    # --- Clients / devices ---
    devices: list[dict[str, Any]] = []
    try:
        devices = await request.app.state.device_health.list_all()
    except Exception:  # noqa: BLE001
        devices = []
    online = [d for d in devices if d.get("status") == "online"]
    clients = {
        "status": "OK" if online else ("IDLE" if devices else "NONE"),
        "total": len(devices),
        "online": len(online),
        "offline": max(0, len(devices) - len(online)),
        "devices": devices[:30],
    }

    # --- Subscriptions (PMS-style) ---
    subs: list[dict[str, Any]] = []
    try:
        subs = await request.app.state.subscription_service.list_all()
    except Exception:  # noqa: BLE001
        subs = []
    by_status: dict[str, int] = {}
    for s in subs:
        st = str(s.get("status") or "unknown")
        by_status[st] = by_status.get(st, 0) + 1
    pms = {
        "status": "OK",
        "total": len(subs),
        "by_status": by_status,
        "active": by_status.get("active", 0) + by_status.get("trialing", 0),
        "accounts_sample": [
            {
                "account_id": s.get("account_id"),
                "plan": s.get("plan"),
                "status": s.get("status"),
                "period_end": s.get("current_period_end"),
            }
            for s in subs[:20]
        ],
    }

    # --- Signal / OMS path ---
    exec_svc = getattr(request.app.state, "executor_signals", None)
    fleet: dict[str, Any] = {
        "polling_accounts": [],
        "silent_accounts": [],
        "pending_total": 0,
        "pending_by_account": {},
        "recent_acks": [],
    }
    pending_list: list[dict[str, Any]] = []
    if exec_svc is not None:
        if hasattr(exec_svc, "fleet_poll_snapshot"):
            fleet = exec_svc.fleet_poll_snapshot()
        if hasattr(exec_svc, "list_all_pending"):
            pending_list = exec_svc.list_all_pending(80)

    recent_signals: list[dict[str, Any]] = []
    try:
        recent_signals = await request.app.state.signal_history.get_recent(40)
    except Exception:  # noqa: BLE001
        recent_signals = []

    buy_n = sum(1 for s in recent_signals if str(s.get("signal") or "").upper() == "BUY")
    sell_n = sum(1 for s in recent_signals if str(s.get("signal") or "").upper() == "SELL")
    hold_n = sum(1 for s in recent_signals if str(s.get("signal") or "").upper() == "HOLD")

    inbound = {
        "label": "Inbound (OHLC + analysis)",
        "total_streams": len(streams),
        "fresh": len(fresh),
        "stale": len(stale),
        "last_sample_age_sec": min((s.get("age_sec") for s in streams if s.get("age_sec") is not None), default=None),
    }
    pre_trade = {
        "label": "Pre-Trade (signals)",
        "recent": len(recent_signals),
        "buy": buy_n,
        "sell": sell_n,
        "hold": hold_n,
        "pending_queue": fleet.get("pending_total", 0),
    }
    routing = {
        "label": "Routing Engine (Executor)",
        "polling_accounts": len(fleet.get("polling_accounts") or []),
        "silent_accounts": len(fleet.get("silent_accounts") or []),
        "pending": fleet.get("pending_total", 0),
    }

    # --- Risk ---
    worker_pool = getattr(request.app.state, "worker_pool", None)
    workers = 0
    try:
        if worker_pool is not None:
            workers = int(worker_pool.active_worker_count())
    except Exception:  # noqa: BLE001
        workers = 0
    from app.config import settings

    risk = {
        "label": "Risk",
        "active_workers": workers,
        "max_workers": getattr(settings, "MAX_CONCURRENT_WORKERS", None),
        "production_authorized": bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)),
        "demo_only": bool(getattr(settings, "DEMO_ONLY", True)),
        "pending_risk_exposure_signals": fleet.get("pending_total", 0),
    }

    # --- Orders with issues / unacked ---
    acks = fleet.get("recent_acks") or []
    rejected = [a for a in acks if a.get("ok") is False or str(a.get("status") or "").lower() in ("rejected", "fail", "failed")]
    filled = [a for a in acks if a.get("ok") is True]
    unacked = pending_list  # still waiting for executor/broker

    orders_with_issues = {
        "rejected_count": len(rejected),
        "pending_unacked": len(unacked),
        "filled_recent": len(filled),
        "rejected_sample": rejected[:12],
        "unacked_sample": unacked[:12],
    }

    # --- Trade event log ---
    events: list[dict[str, Any]] = []
    tel = getattr(request.app.state, "trade_event_log", None)
    if tel is not None and hasattr(tel, "recent"):
        try:
            events = tel.recent(60)
        except Exception:  # noqa: BLE001
            events = []
    elif tel is not None and hasattr(tel, "all_recent"):
        try:
            events = tel.all_recent(60)
        except Exception:  # noqa: BLE001
            events = []

    # --- Overall pipeline health ---
    if market_error or (not streams):
        overall = "DEGRADED_MARKET_DATA"
        overall_msg = "No fresh OHLC streams — Feed may be offline"
    elif not fleet.get("polling_accounts") and fleet.get("pending_total", 0) > 0:
        overall = "EXECUTOR_SILENT"
        overall_msg = "Signals pending but no Executor is polling"
    elif fleet.get("pending_total", 0) > 0:
        overall = "SIGNAL_FLOWING"
        overall_msg = "Pending signals in queue — Executor active or expected"
    elif fresh:
        overall = "STANDING_BY"
        overall_msg = "Market data live; no pending execution — normal between entries"
    else:
        overall = "UNKNOWN"
        overall_msg = "Inspect stage panels"

    return {
        "generated_at_ms": now_ms,
        "overall": {"code": overall, "message": overall_msg},
        "market_data": market_data,
        "clients": clients,
        "pms": pms,
        "oms": {
            "inbound": inbound,
            "pre_trade": pre_trade,
            "routing": routing,
        },
        "risk": risk,
        "orders_with_issues": orders_with_issues,
        "fleet": fleet,
        "recent_signals": recent_signals[:30],
        "pending_signals": pending_list[:40],
        "recent_events": events[:40],
        "legend": {
            "STANDING_BY": "Healthy idle — data flowing, no trade signal",
            "SIGNAL_FLOWING": "Signals in flight",
            "EXECUTOR_SILENT": "Need Executor EA on VPS",
            "DEGRADED_MARKET_DATA": "Need OHLC Feed",
        },
    }
