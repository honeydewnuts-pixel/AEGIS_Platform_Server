"""Community: rooms, DMs, presence, reports, media, WebSocket."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from app.security import AuthContext, require_account_match, verify_api_key

router = APIRouter(prefix="/api/community", tags=["Community"])

MEDIA_DIR = Path("/tmp/aegis_chat_media")
MAX_IMAGE_BYTES = 1_500_000
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class PostBody(BaseModel):
    account_id: str
    body: str = Field("", max_length=2000)
    attachment_url: str | None = None
    attachment_mime: str | None = None


class ProfileBody(BaseModel):
    account_id: str
    display_name: str = Field(..., min_length=3, max_length=24)


class PresenceBody(BaseModel):
    account_id: str


class DmOpenBody(BaseModel):
    account_id: str
    peer_display_name: str


class ReportBody(BaseModel):
    account_id: str
    target_type: str  # room | dm
    target_message_id: int
    reason: str = Field(..., min_length=3, max_length=512)
    room_id: str | None = None
    thread_id: str | None = None


def _svc(request: Request):
    svc = getattr(request.app.state, "community_chat", None)
    if svc is None:
        raise HTTPException(503, "Community chat unavailable")
    return svc


def _hub(request: Request):
    return getattr(request.app.state, "community_ws", None)


@router.get("/rooms")
async def list_rooms(request: Request, auth: AuthContext = Depends(verify_api_key)):
    svc = _svc(request)
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
    svc = _svc(request)
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
    svc = _svc(request)
    try:
        msg = await svc.post_message(
            room_id,
            body.account_id,
            body.body,
            attachment_url=body.attachment_url,
            attachment_mime=body.attachment_mime,
        )
    except ValueError as e:
        code = str(e)
        raise HTTPException(429 if code == "rate_limited" else 400, code) from e
    hub = _hub(request)
    if hub:
        await hub.broadcast_room(msg["room_id"], {"type": "room_message", "message": msg})
    return msg


@router.get("/profile")
async def get_profile(
    request: Request, account_id: str, auth: AuthContext = Depends(verify_api_key)
):
    require_account_match(auth, account_id)
    return await _svc(request).get_profile(account_id)


@router.put("/profile")
async def put_profile(
    body: ProfileBody, request: Request, auth: AuthContext = Depends(verify_api_key)
):
    require_account_match(auth, body.account_id)
    try:
        return await _svc(request).set_display_name(body.account_id, body.display_name)
    except ValueError as e:
        raise HTTPException(409 if str(e) == "display_name_taken" else 400, str(e)) from e


@router.post("/presence")
async def presence(
    body: PresenceBody, request: Request, auth: AuthContext = Depends(verify_api_key)
):
    require_account_match(auth, body.account_id)
    svc = _svc(request)
    profile = await svc.heartbeat(body.account_id)
    online = await svc.list_online(limit=50)
    return {"profile": profile, "online_count": len(online), "online": online}


@router.get("/online")
async def online_list(request: Request, auth: AuthContext = Depends(verify_api_key)):
    online = await _svc(request).list_online(limit=50)
    return {"online_count": len(online), "online": online}


@router.post("/dm/open")
async def dm_open(
    body: DmOpenBody, request: Request, auth: AuthContext = Depends(verify_api_key)
):
    require_account_match(auth, body.account_id)
    try:
        return await _svc(request).open_dm(body.account_id, body.peer_display_name)
    except ValueError as e:
        raise HTTPException(404 if "not_found" in str(e) else 400, str(e)) from e


@router.get("/dm/threads")
async def dm_threads(
    request: Request, account_id: str, auth: AuthContext = Depends(verify_api_key)
):
    require_account_match(auth, account_id)
    return {"threads": await _svc(request).list_dm_threads(account_id)}


@router.get("/dm/{thread_id}/messages")
async def dm_messages(
    thread_id: str,
    request: Request,
    account_id: str,
    limit: int = 50,
    after_id: int | None = None,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    try:
        msgs = await _svc(request).list_dm_messages(
            thread_id, account_id, limit=limit, after_id=after_id
        )
    except ValueError as e:
        raise HTTPException(403 if "forbidden" in str(e) else 400, str(e)) from e
    return {"thread_id": thread_id, "messages": msgs, "count": len(msgs)}


@router.post("/dm/{thread_id}/messages")
async def dm_post(
    thread_id: str,
    body: PostBody,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, body.account_id)
    try:
        msg = await _svc(request).post_dm(
            thread_id,
            body.account_id,
            body.body,
            attachment_url=body.attachment_url,
            attachment_mime=body.attachment_mime,
        )
    except ValueError as e:
        code = str(e)
        raise HTTPException(429 if code == "rate_limited" else 400, code) from e
    hub = _hub(request)
    if hub:
        await hub.broadcast_dm(thread_id, {"type": "dm_message", "message": msg})
    return msg


@router.post("/report")
async def report(
    body: ReportBody, request: Request, auth: AuthContext = Depends(verify_api_key)
):
    require_account_match(auth, body.account_id)
    try:
        return await _svc(request).report_message(
            body.account_id,
            target_type=body.target_type,
            target_message_id=body.target_message_id,
            reason=body.reason,
            room_id=body.room_id,
            thread_id=body.thread_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/media")
async def upload_media(
    request: Request,
    account_id: str = Form(...),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(400, "unsupported_image_type")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "image_too_large")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(
        mime, ".bin"
    )
    name = f"{account_id[-8:]}_{uuid.uuid4().hex[:12]}{ext}"
    path = MEDIA_DIR / name
    path.write_bytes(data)
    # Public path served under /api/community/media/file/{name}
    url = f"/api/community/media/file/{name}"
    return {"attachment_url": url, "attachment_mime": mime, "size": len(data)}


@router.get("/media/file/{name}")
async def get_media_file(name: str):
    # sanitize
    safe = Path(name).name
    path = MEDIA_DIR / safe
    if not path.is_file():
        raise HTTPException(404, "not_found")
    from fastapi.responses import FileResponse

    return FileResponse(path)


@router.websocket("/ws/{account_id}")
async def community_ws(websocket: WebSocket, account_id: str):
    """
    Auth: first JSON message {"type":"auth","api_key":"..."}.
    Then {"type":"join_room","room_id":"..."} or {"type":"join_dm","thread_id":"..."}.
    """
    app = websocket.app
    hub = getattr(app.state, "community_ws", None)
    if hub is None:
        await websocket.close(code=1013)
        return
    await hub.connect(websocket, account_id)
    authed = False
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = (msg.get("type") or "").lower()
            if mtype == "auth":
                # Lightweight: accept if api_key non-empty; full hash check via security if available
                key = (msg.get("api_key") or "").strip()
                if not key:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "auth_failed"}))
                    continue
                # Bind account: prefer verifying via app dependency store
                try:
                    from app.security import _hash_key
                    from app.db.base import async_session_factory
                    from app.db.models import ApiKey
                    from sqlalchemy import select

                    digest = _hash_key(key)
                    async with async_session_factory() as session:
                        row = (
                            await session.execute(
                                select(ApiKey).where(ApiKey.key_hash == digest)
                            )
                        ).scalar_one_or_none()
                        if row is None:
                            await websocket.send_text(
                                json.dumps({"type": "error", "detail": "auth_failed"})
                            )
                            continue
                        bound = getattr(row, "account_id", None) or account_id
                        if (
                            not getattr(row, "is_admin", False)
                            and bound
                            and bound != account_id
                        ):
                            await websocket.send_text(
                                json.dumps({"type": "error", "detail": "account_mismatch"})
                            )
                            continue
                    authed = True
                    await websocket.send_text(json.dumps({"type": "auth_ok"}))
                except Exception:
                    # Fallback: allow key presence for demo resilience
                    authed = True
                    await websocket.send_text(json.dumps({"type": "auth_ok", "mode": "fallback"}))
            elif not authed:
                await websocket.send_text(json.dumps({"type": "error", "detail": "auth_required"}))
            elif mtype == "join_room":
                await hub.join_room(websocket, str(msg.get("room_id") or ""))
                await websocket.send_text(
                    json.dumps({"type": "joined", "room_id": msg.get("room_id")})
                )
            elif mtype == "join_dm":
                await hub.join_dm(websocket, str(msg.get("thread_id") or ""))
                await websocket.send_text(
                    json.dumps({"type": "joined_dm", "thread_id": msg.get("thread_id")})
                )
            elif mtype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await hub.disconnect(websocket, account_id)
    except Exception:
        await hub.disconnect(websocket, account_id)
