"""Rulebook HTTP API — authoritative source is RegistryService (operational CSVs).

The in-process founding_registry() remains empty and is not used here, so
/rulebooks* cannot disagree with /api/registry/*.

production_authorized=false
execution_authorized=false
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/rulebooks", tags=["rulebooks"])


def _svc(request: Request):
    svc = getattr(request.app.state, "templates", None) or getattr(request.app.state, "registry", None)
    if svc is None:
        # Fail closed: construct empty operational service rather than founding snapshot
        from app.services.registry_service import RegistryService
        return RegistryService()
    return svc


@router.get("")
def list_rulebooks(request: Request):
    svc = _svc(request)
    items = svc.list_rulebooks()
    return {
        "rulebook_count": len(items),
        "active_rulebooks": items,
        "rulebooks": items,  # compat alias for clients expecting "rulebooks"
        "production_authorized": False,
        "execution_authorized": False,
        "message": (
            "No approved operational rulebooks are registered. "
            "Research strategies are archived and are not routable."
            if not items
            else "Operational registry listing; production/execution authorization remain false."
        ),
    }


@router.get("/lookup")
def lookup_rulebooks(instrument: str, timeframe: str, request: Request):
    svc = _svc(request)
    items = svc.list_rulebooks(instrument=instrument, timeframe=timeframe)
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "rulebook_count": len(items),
        "active_rulebooks": items,
        "rulebooks": items,
        "production_authorized": False,
        "execution_authorized": False,
    }


@router.get("/{rulebook_id}")
def get_rulebook(rulebook_id: str, request: Request):
    svc = _svc(request)
    item = svc.get_rulebook(rulebook_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NO_QUALIFIED_RULEBOOK",
                "rulebook_id": rulebook_id,
                "message": (
                    "Rulebook not found in the operational registry. "
                    "Archived research rulebooks are not operationally routable."
                ),
            },
        )
    return item
