from fastapi import APIRouter, HTTPException
from app.rulebooks import founding_registry

router = APIRouter(prefix="/rulebooks", tags=["rulebooks"])
_registry = founding_registry()


@router.get("")
def list_rulebooks():
    items = [x.to_dict() for x in _registry.all()]
    return {
        "rulebook_count": len(items),
        "active_rulebooks": items,
        "production_authorized": False,
        "execution_authorized": False,
        "message": (
            "No approved operational rulebooks are registered. "
            "Research strategies are archived and are not routable."
        ),
    }


@router.get("/lookup")
def lookup_rulebooks(instrument: str, timeframe: str):
    items = [
        x.to_dict()
        for x in _registry.lookup(instrument, timeframe, qualified_only=True)
    ]
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "rulebook_count": len(items),
        "active_rulebooks": items,
        "production_authorized": False,
        "execution_authorized": False,
    }


@router.get("/{rulebook_id}")
def get_rulebook(rulebook_id: str):
    item = _registry.get(rulebook_id)
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
    return item.to_dict()
