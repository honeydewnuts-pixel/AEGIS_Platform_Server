"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : device_router.py
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.device_health import HeartbeatRequest
from app.security import verify_api_key, require_account_match, require_admin, AuthContext

router = APIRouter(prefix="/api/devices", tags=["Device Health"])


def get_device_health_service(request: Request):
    return request.app.state.device_health


@router.post("/heartbeat")
async def receive_heartbeat(
    heartbeat: HeartbeatRequest,
    device_health=Depends(get_device_health_service),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, heartbeat.account_id)
    await device_health.record_heartbeat(heartbeat.account_id, heartbeat.model_dump(by_alias=False))
    return {"status": "recorded"}


@router.get("/health/{account_id}")
async def get_device_health(
    account_id: str,
    device_health=Depends(get_device_health_service),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    health = await device_health.get_health(account_id)
    if health is None:
        raise HTTPException(status_code=404, detail="No recent heartbeat for this account - device may be offline.")
    return health


@router.get("/health")
async def list_device_health(
    device_health=Depends(get_device_health_service),
    auth: AuthContext = Depends(verify_api_key),
):
    """Operator dashboard endpoint - status of every device. Admin-only,
    since this is fleet-wide data, not scoped to one account."""
    require_admin(auth)
    return await device_health.list_all()
