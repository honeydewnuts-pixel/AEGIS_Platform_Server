"""
Trade Copier API — simple master → slave setup for AEGIS subscribers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import verify_api_key, require_account_match, AuthContext
from app.services.plan_catalog import ADDON_CATALOG

router = APIRouter(prefix="/api/copier", tags=["Trade Copier"])


class ActivateBody(BaseModel):
    account_id: str
    tier: str = Field(default="copier_3", description="copier_3 | copier_10 | copier_25")


class AddSlaveBody(BaseModel):
    account_id: str
    label: str = "Slave"
    server: str
    login: str
    broker_name: str | None = None
    risk_mode: str = "multiplier"
    risk_value: float = 1.0


class SlaveToggleBody(BaseModel):
    account_id: str
    slave_id: int
    enabled: bool = True


@router.get("/catalog")
async def catalog():
    return {"addons": [{**v, "code": k} for k, v in ADDON_CATALOG.items()]}


@router.get("/status/{account_id}")
async def status(account_id: str, request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_account_match(auth, account_id)
    svc = request.app.state.trade_copier
    data = await svc.get_addon(account_id)
    if not data:
        return {"active": False, "account_id": account_id, "catalog": list(ADDON_CATALOG.keys())}
    return {"active": True, **data}


@router.post("/activate")
async def activate(body: ActivateBody, request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_account_match(auth, body.account_id)
    try:
        data = await request.app.state.trade_copier.activate_addon(body.account_id, body.tier)
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e)) from e
    audit = getattr(request.app.state, "audit_service", None)
    if audit:
        await audit.record(
            action="copier.activate",
            actor_type="account_key",
            account_id=body.account_id,
            detail=f"tier={body.tier}",
        )
    return data


@router.post("/slaves")
async def add_slave(body: AddSlaveBody, request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_account_match(auth, body.account_id)
    try:
        slave = await request.app.state.trade_copier.add_slave(
            body.account_id,
            label=body.label,
            server=body.server,
            login=body.login,
            broker_name=body.broker_name,
            risk_mode=body.risk_mode,
            risk_value=body.risk_value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return slave


@router.delete("/slaves/{slave_id}")
async def remove_slave(
    slave_id: int,
    account_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    ok = await request.app.state.trade_copier.remove_slave(account_id, slave_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Slave not found")
    return {"removed": True, "slave_id": slave_id}


@router.post("/slaves/toggle")
async def toggle_slave(body: SlaveToggleBody, request: Request, auth: AuthContext = Depends(verify_api_key)):
    require_account_match(auth, body.account_id)
    ok = await request.app.state.trade_copier.set_slave_enabled(body.account_id, body.slave_id, body.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Slave not found")
    return {"slave_id": body.slave_id, "enabled": body.enabled}
