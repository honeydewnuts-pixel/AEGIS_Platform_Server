"""Subscriber notification inbox APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.security import AuthContext, require_account_match, verify_api_key

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(
    request: Request,
    account_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    svc = request.app.state.notifications
    rows = await svc.list_for_account(account_id, limit=limit, unread_only=unread_only)
    unread = await svc.unread_count(account_id)
    return {"account_id": account_id, "unread_count": unread, "notifications": rows, "count": len(rows)}


@router.get("/unread-count")
async def unread_count(
    request: Request,
    account_id: str = Query(...),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    n = await request.app.state.notifications.unread_count(account_id)
    return {"account_id": account_id, "unread_count": n}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    request: Request,
    account_id: str = Query(...),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    ok = await request.app.state.notifications.mark_read(account_id, notification_id)
    return {"ok": ok, "id": notification_id}


@router.post("/read-all")
async def read_all(
    request: Request,
    account_id: str = Query(...),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    n = await request.app.state.notifications.mark_all_read(account_id)
    return {"ok": True, "marked": n}


@router.post("/{notification_id}/acknowledge")
async def acknowledge(
    notification_id: int,
    request: Request,
    account_id: str = Query(...),
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    require_account_match(auth, account_id)
    ok = await request.app.state.notifications.acknowledge(account_id, notification_id)
    return {"ok": ok, "id": notification_id}
