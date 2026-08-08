"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : download_router.py

Gates the mobile app APK behind an active subscription. This assumes
you're distributing the APK directly (not via Play Store) - if you
later publish on Play Store instead, this gating approach doesn't
apply there, since Google controls that download path, not you.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(prefix="/api/download", tags=["Download"])


@router.get("/apk")
async def download_apk(request: Request, account_id: str = Query(...)):
    subscription_service = request.app.state.subscription_service

    if not await subscription_service.is_active(account_id):
        raise HTTPException(
            status_code=402,  # Payment Required
            detail="No active subscription for this account. Subscribe first at /api/subscriptions/checkout/{provider}.",
        )

    apk_path = Path(settings.APK_FILE_PATH)
    if not apk_path.exists():
        raise HTTPException(status_code=500, detail="APK file not found on server - has it been built and placed at APK_FILE_PATH?")

    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename="AEGIS.apk",
    )
