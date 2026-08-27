"""Cross-platform telemetry / screenshot metadata intake."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])


class TelemetryBody(BaseModel):
    device_id: str = ""
    account_id: str = ""
    platform: str = Field(default="unknown", pattern="^(android|windows|macos|ios|unknown)$")
    type: str = "heartbeat"
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("")
async def post_telemetry(body: TelemetryBody, request: Request):
    """Accept heartbeat / meta from desktop & mobile. Screenshots still use /aegis/analyze."""
    log = getattr(request.app.state, "logger", None)
    if log:
        log.info(
            "telemetry platform=%s device=%s account=%s type=%s",
            body.platform,
            body.device_id,
            body.account_id,
            body.type,
        )
    return {
        "ok": True,
        "ts": time.time(),
        "platform": body.platform,
        "hint": "Upload chart images via multipart POST /aegis/analyze with same API key",
    }
