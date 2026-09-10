"""Public rulebook + tradeable pairs registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query

router = APIRouter(prefix="/api/registry", tags=["Registry"])


@router.get("/rulebooks")
async def list_rulebooks(
    request: Request,
    instrument: str | None = None,
    timeframe: str | None = None,
):
    svc = getattr(request.app.state, "templates", None)
    if svc is None:
        raise HTTPException(503, "Registry not ready")
    return {"rulebooks": svc.list_rulebooks(instrument=instrument, timeframe=timeframe)}


@router.get("/rulebooks/{rulebook_id}")
async def get_rulebook(rulebook_id: str, request: Request):
    svc = request.app.state.templates
    item = svc.get_rulebook(rulebook_id)
    if not item:
        raise HTTPException(404, "NO_QUALIFIED_RULEBOOK")
    return item


@router.get("/pairs")
async def list_pairs(request: Request, tradeable_only: bool = Query(True)):
    svc = request.app.state.templates
    return {
        "pairs": svc.list_instruments(tradeable_only=tradeable_only),
        "indicators_required": False,
    }


@router.get("/active")
async def active(request: Request):
    return request.app.state.templates.get_active_bundle()
