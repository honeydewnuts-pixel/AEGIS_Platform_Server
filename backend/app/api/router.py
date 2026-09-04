"""
AEGIS Main API Router

Autonomous Enterprise Global Intelligence System
Company: Honeydewnuts Nigerian Limited
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import verify_api_key, require_admin, AuthContext

router = APIRouter()

# NOTE: upload_router is registered directly in main.py - it used to
# also be nested here, which registered every /upload/* route twice.

# ------------------------------------------------------------------
# Root API Endpoint
# ------------------------------------------------------------------

@router.get("/")
async def api_root():
    return {
        "application": "AEGIS",
        "description": "Autonomous Enterprise Global Intelligence System",
        "company": "Honeydewnuts Nigerian Limited",
        "version": "0.1.0",
        "status": "Running"
    }


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "AEGIS Backend",
        "version": "0.1.0"
    }


# ------------------------------------------------------------------
# Mode switch: DEMO_VERIFY <-> LIVE_TRADE
# ------------------------------------------------------------------
# Deliberately at the bare /api/set_mode path (not nested under
# /api/subscriptions/, even though the logic lives in
# SubscriptionService) since that's the exact path requested for this
# to be a clearly separate, top-level concept from subscription billing
# mechanics - even though under the hood it's powered by the same plan
# catalog and Subscription row.
#
# "Auto-switch on payment" does NOT route through this HTTP endpoint -
# see the comment on SubscriptionService.apply_event() for why: the
# payment webhook resolves and applies the correct plan directly via a
# normal internal method call, since looping a webhook back through the
# server's own HTTP API would be pointless indirection. Both paths
# (this endpoint, and the webhook) call into the same
# plan_catalog.resolve_plan()/mode_for_plan() logic, so they can never
# disagree about what mode an account is in.
#
# This endpoint is for everything that ISN'T a completed payment:
# admin/support overrides (comping an account, manually reverting
# someone to demo, QA/testing), or any future self-service
# downgrade-to-demo flow.

class SetModeRequest(BaseModel):
    account_id: str
    mode: str = Field(description="'DEMO_VERIFY' or 'LIVE_TRADE'")


@router.post("/api/set_mode", tags=["Mode"])
async def set_mode(
    body: SetModeRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_admin(auth)
    sub = request.app.state.subscription_service
    try:
        result = await sub.set_mode(body.account_id, body.mode, actor=f"admin:{auth.label or auth.key_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if hasattr(request.app.state, "audit_service"):
        await request.app.state.audit_service.record(
            action="subscription.set_mode",
            actor_type="admin_key",
            actor_id=str(auth.key_id) if auth.key_id else None,
            actor_label=auth.label,
            account_id=body.account_id,
            detail=f"mode={result['mode']} plan={result['plan']}",
            ip=request.client.host if request.client else None,
        )
    return result

