"""Registry APIs (rulebooks + tradeable pairs). Indicator templates retired."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import verify_api_key, require_admin, AuthContext

router = APIRouter(prefix="/api/templates", tags=["Registry"])


@router.get("/active")
async def get_active_templates(request: Request):
    """Mobile/portal: active registry snapshot. No indicator install checklist."""
    svc = getattr(request.app.state, "templates", None) or getattr(request.app.state, "registry", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Registry not ready")
    return svc.get_active_bundle()


@router.get("/indicator-stacks")
async def list_stacks(request: Request, auth: AuthContext = Depends(verify_api_key)):
    """Retired — always empty."""
    require_admin(auth)
    return []


@router.get("/indicator-stacks/{version}")
async def get_stack(version: str, request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_admin(auth)
    return {
        "version": version,
        "status": "retired",
        "install_order": [],
        "message": "Indicator stacks retired. No MT5 indicators required.",
    }


@router.get("/rulebooks")
async def list_books(request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_admin(auth)
    svc = request.app.state.templates
    return svc.list_rulebooks()


@router.get("/rulebooks/{version}")
async def get_book(version: str, request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_admin(auth)
    svc = request.app.state.templates
    item = svc.get_rulebook(version)
    if item is None:
        # try version as rulebook_id
        raise HTTPException(status_code=404, detail=f"Rulebook not found: {version}")
    return item


class ActivateRequest(BaseModel):
    rulebook_version: str = Field(..., examples=["registry", "v3"])
    registry_version: str = Field("v40", examples=["v40"])
    # Accepted but ignored — clients may still send it
    indicator_stack_version: str | None = Field(None, description="Ignored; indicators retired")


@router.post("/activate")
async def activate_profile(
    body: ActivateRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_admin(auth)
    svc = request.app.state.templates
    ptr = svc.activate(body.rulebook_version, body.registry_version)
    audit = getattr(request.app.state, "audit_service", None)
    if audit:
        await audit.record(
            action="registry.activate",
            actor_type="admin_key",
            actor_id=str(auth.key_id) if auth.key_id else None,
            actor_label=auth.label,
            detail=f"rulebook={ptr.get('rulebook_version')} registry={ptr.get('registry_version')}",
            ip=request.client.host if request.client else None,
        )
    return {"status": "activated", **ptr}
