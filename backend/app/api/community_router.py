"""Community peer chat API — rooms, messages, profile, presence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import AuthContext, require_account_match, verify_api_key

router = APIRouter(prefix="/api/community", tags=["Community"])


class PostBody(BaseModel):
    account_id: str
    body: str = Field(..., min_length=1, max_length=2000)


class ProfileBody(BaseModel):
    account_id: str
    display_name: str = Field(..., min_length=3, max_length=24)


class PresenceBody(BaseModel):
    account_id: str


@router.get("/rooms")
async def list_rooms(
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    online = await svc.list_online(limit=50)
    return {"rooms": await svc.list_rooms(), "online_count": len(online), "online": online}


@router.get("/rooms/{room_id}/messages")
async def room_messages(
    room_id: str,
    request: Request,
    limit: int = 50,
    before_id: int | None = None,
    after_id: int | None = None,
    auth: AuthContext = Depends(verify_api_key),
):
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    try:
        msgs = await svc.list_messages(
            room_id, limit=limit, before_id=before_id, after_id=after_id
        )
    except ValueError as e:
        raise HTTPException(404 if str(e) == "room_not_found" else 400, str(e)) from e
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


@router.get("/profile")
async def get_profile(
    request: Request,
    account_id: str,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    return await svc.get_profile(account_id)


@router.put("/profile")
async def put_profile(
    body: ProfileBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    try:
        return await svc.set_display_name(body.account_id, body.display_name)
    except ValueError as e:
        raise HTTPException(409 if str(e) == "display_name_taken" else 400, str(e)) from e


@router.post("/presence")
async def presence(
    body: PresenceBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    profile = await svc.heartbeat(body.account_id)
    online = await svc.list_online(limit=50)
    return {"profile": profile, "online_count": len(online), "online": online}


@router.get("/online")
async def online_list(
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    online = await svc.list_online(limit=50)
    return {"online_count": len(online), "online": online}
