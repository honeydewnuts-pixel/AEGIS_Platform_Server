"""Market session status for mobile / operators."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.market_hours_service import session_status

router = APIRouter(prefix="/api/market", tags=["Market session"])


@router.get("/session")
async def get_market_session(symbol: str = Query(..., min_length=1)):
    """
    Returns whether uploads/autonomous trading should proceed for this symbol.
    Crypto / volatility-style symbols remain open on weekends.
    """
    return session_status(symbol)
