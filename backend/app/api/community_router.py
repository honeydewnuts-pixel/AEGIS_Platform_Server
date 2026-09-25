"""Community peer chat API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import AuthContext, require_account_match, verify_api_key

router = APIRouter(prefix="/api/community", tags=["Community"])


class PostBody(BaseModel):
    account_id: str
    body: str = Field(..., min_length=1, max_length=2000)


@router.get("/rooms")
async def list_rooms(
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    return {"rooms": await svc.list_rooms()}


@router.get("/rooms/{room_id}/messages")
async def room_messages(
    room_id: str,
    request: Request,
    limit: int = 50,
    before_id: int | None = None,
    auth: AuthContext = Depends(verify_api_key),
):
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    msgs = await svc.list_messages(room_id, limit=limit, before_id=before_id)
    return {"room_id": room_id, "messages": msgs, "count": len(msgs)}


@router.post("/rooms/{room_id}/messages")
async def post_message(
    room_id: str,
    body: PostBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    try:
        msg = await svc.post_message(room_id, body.account_id, body.body)
    except ValueError as e:
        code = str(e)
        status = 429 if code == "rate_limited" else 400
        raise HTTPException(status, code) from e
    return msg
