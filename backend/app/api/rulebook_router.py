from fastapi import APIRouter, HTTPException
from app.rulebooks import founding_registry

router = APIRouter(prefix="/rulebooks", tags=["rulebooks"])
_registry = founding_registry()

@router.get("")
def list_rulebooks():
    return [x.to_dict() for x in _registry.all()]

@router.get("/lookup")
def lookup_rulebooks(instrument: str, timeframe: str):
    return [x.to_dict() for x in _registry.lookup(instrument, timeframe, qualified_only=True)]

@router.get("/{rulebook_id}")
def get_rulebook(rulebook_id: str):
    item = _registry.get(rulebook_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NO_QUALIFIED_RULEBOOK")
    return item.to_dict()
