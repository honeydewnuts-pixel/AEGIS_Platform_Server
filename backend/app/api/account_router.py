"""Account-facing endpoints (risk presets, status)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.security import verify_api_key, require_account_match, AuthContext

router = APIRouter(prefix="/api/account", tags=["Account"])


class RiskPresetRequest(BaseModel):
    account_id: str
    risk_preset: str


@router.post("/risk_preset")
async def set_risk_preset(
    body: RiskPresetRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    sub = request.app.state.subscription_service
    try:
        return await sub.set_risk_preset(body.account_id, body.risk_preset)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid risk_preset")


@router.get("/status")
async def account_status(
    account_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """GET /api/account/status?account_id=... — includes risk_preset + calculated lot."""
    require_account_match(auth, account_id)
    sub = request.app.state.subscription_service
    record = await sub.get_status(account_id)
    if not record:
        raise HTTPException(status_code=404, detail="No subscription found for this account.")
    return record
