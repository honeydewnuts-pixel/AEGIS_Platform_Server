"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : admin_router.py

Aggregate JSON for the admin dashboard - one call instead of the
dashboard having to stitch together /api/devices/health and
/api/subscriptions itself for the summary cards.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.security import verify_api_key, require_admin, AuthContext

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/summary")
async def get_summary(request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_admin(auth)
    device_health = request.app.state.device_health
    subscription_service = request.app.state.subscription_service
    worker_pool = request.app.state.worker_pool

    devices = await device_health.list_all()
    subscriptions = await subscription_service.list_all()

    status_counts: dict[str, int] = {}
    for s in subscriptions:
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

    return {
        "devices": {
            "total": len(devices),
            "online": sum(1 for d in devices if d.get("status") == "online"),
            "offline": sum(1 for d in devices if d.get("status") == "offline"),
        },
        "subscriptions": {
            "total": len(subscriptions),
            "by_status": status_counts,
        },
        "active_workers_this_instance": worker_pool.active_worker_count(),
    }
