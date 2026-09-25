"""AEGIS AI support chat — no trade execution."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import AuthContext, require_account_match, verify_api_key

router = APIRouter(prefix="/api/ai", tags=["AEGIS AI"])


class AskBody(BaseModel):
    account_id: str
    message: str = Field(..., min_length=1, max_length=2000)


@router.get("/history")
async def ai_history(
    request: Request,
    account_id: str,
    limit: int = 40,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "aegis_ai", None)
    if svc is None:
        raise HTTPException(503, "AEGIS AI unavailable")
    return {"messages": await svc.history(account_id, limit=limit)}


@router.post("/chat")
async def ai_chat(
    body: AskBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = getattr(request.app.state, "aegis_ai", None)
    if svc is None:
        raise HTTPException(503, "AEGIS AI unavailable")
    try:
        return await svc.ask(body.account_id, body.message)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
