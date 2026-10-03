"""
Gated APK download for the marketing / portal website.

Requires a download token (issued after subscribe or demo signup).
Tokens are single-use by default so a link cannot be freely shared.
Device binding is enforced later when the app registers ANDROID_ID.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.security import verify_api_key, require_admin, AuthContext

router = APIRouter(prefix="/api/download", tags=["Download"])


@router.get("/apk")
async def download_apk(
    request: Request,
    token: str = Query(..., description="One-time download token from portal/checkout"),
):
    bindings = request.app.state.device_bindings
    consumed = await bindings.consume_download_token(token)
    if consumed is None:
        raise HTTPException(
            status_code=403,
            detail="Invalid, expired, revoked, or already-used download token. Subscribe or request a new link.",
        )

    # Resolve APK relative to common deploy roots (repo root, backend/, cwd)
    candidates = []
    raw = Path(settings.APK_FILE_PATH)
    candidates.append(raw)
    if not raw.is_absolute():
        here = Path(__file__).resolve()
        # backend/app/api -> repo root is parents[3]
        for root in (
            Path.cwd(),
            here.parents[3] if len(here.parents) > 3 else Path.cwd(),
            here.parents[2] if len(here.parents) > 2 else Path.cwd(),
            Path("/opt/render/project/src"),
        ):
            candidates.append(root / raw)
            candidates.append(root / "release" / "aegis-mobile.apk")
    apk_path = next((c for c in candidates if c.exists() and c.is_file()), None)
    if apk_path is None:
        raise HTTPException(
            status_code=500,
            detail="APK file not found on server — build and place it at APK_FILE_PATH (release/aegis-mobile.apk).",
        )

    audit = getattr(request.app.state, "audit_service", None)
    if audit:
        await audit.record(
            action="apk.download",
            actor_type="download_token",
            actor_id=token[:8] + "…",
            account_id=consumed["account_id"],
            target_type="apk",
            target_id=consumed["plan"],
            detail=f"uses={consumed['uses']}/{consumed['max_uses']}",
            ip=request.client.host if request.client else None,
        )

    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename=f"AEGIS-{consumed['plan']}.apk",
        headers={
            "X-AEGIS-Account-Id": consumed["account_id"],
            "X-AEGIS-Plan": consumed["plan"],
        },
    )


class IssueDownloadTokenRequest(BaseModel):
    account_id: str
    plan: str = Field(default="starter", pattern="^(live|demo|starter|pro|business)$")
    max_uses: int = Field(default=1, ge=1, le=5)
    ttl_hours: int = Field(default=48, ge=1, le=720)


@router.post("/token")
async def issue_token(
    body: IssueDownloadTokenRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Admin or active portal flow issues a short-lived download token."""
    require_admin(auth)
    token = await request.app.state.device_bindings.issue_download_token(
        account_id=body.account_id,
        plan=body.plan,
        max_uses=body.max_uses,
        ttl_hours=body.ttl_hours,
    )
    await request.app.state.audit_service.record(
        action="download_token.issue",
        actor_type="admin_key",
        actor_id=str(auth.key_id) if auth.key_id else None,
        actor_label=auth.label,
        account_id=body.account_id,
        target_type="download_token",
        detail=f"plan={body.plan} max_uses={body.max_uses}",
        ip=request.client.host if request.client else None,
    )
    base = str(request.base_url).rstrip("/")
    return {
        "token": token,
        "account_id": body.account_id,
        "plan": body.plan,
        "download_url": f"{base}/api/download/apk?token={token}",
        "note": "Single-use by default. Share only with the subscriber.",
    }


def _release_root() -> Path:
    roots = [
        Path(__file__).resolve().parents[3],
        Path(__file__).resolve().parents[2],
        Path("."),
    ]
    for root in roots:
        if (root / "release").is_dir():
            return root
    return roots[0]


@router.get("/desktop/{artifact}")
async def download_desktop(
    artifact: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Serve MT5 EA sources (Executor / OHLC Feed) for authenticated clients.

    artifact: executor | ohlc-feed | ohlc-feed-v2
    """
    mapping = {
        "executor": ("release/desktop/AEGIS_Executor.mq5", "AEGIS_Executor.mq5", "text/plain"),
        "ohlc-feed": ("release/desktop/AEGIS_OHLC_Feed.mq5", "AEGIS_OHLC_Feed.mq5", "text/plain"),
        "ohlc-feed-v2": ("release/desktop/AEGIS_OHLC_Feed_V2.00.mq5", "AEGIS_OHLC_Feed_V2.00.mq5", "text/plain"),
        "release-notes": ("release/RELEASE_NOTES_STAGE25.md", "RELEASE_NOTES_STAGE25.md", "text/markdown"),
    }
    key = artifact.strip().lower()
    if key not in mapping:
        raise HTTPException(status_code=404, detail="Unknown desktop artifact. Use executor|ohlc-feed|ohlc-feed-v2")
    rel, filename, media = mapping[key]
    root = _release_root()
    path = root / rel
    if not path.is_file():
        path = Path(rel)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {rel}")
    return FileResponse(path=str(path), media_type=media, filename=filename)


@router.get("/bundle-info")
async def bundle_info(auth: AuthContext = Depends(verify_api_key)):
    """List current downloadable release artifacts and versions."""
    root = _release_root()
    items = []
    for label, rel in [
        ("executor", "release/desktop/AEGIS_Executor.mq5"),
        ("ohlc-feed", "release/desktop/AEGIS_OHLC_Feed.mq5"),
        ("apk", "release/aegis-mobile.apk"),
    ]:
        path = root / rel
        if not path.is_file():
            path = Path(rel)
        items.append({
            "id": label,
            "path": rel,
            "present": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
        })
    return {
        "stage": "2.5",
        "executor_version": "2.20",
        "ohlc_feed_version": "2.05",
        "artifacts": items,
        "download_paths": {
            "executor": "/api/download/desktop/executor",
            "ohlc_feed": "/api/download/desktop/ohlc-feed",
            "apk": "/api/download/apk?token=...",
        },
    }

