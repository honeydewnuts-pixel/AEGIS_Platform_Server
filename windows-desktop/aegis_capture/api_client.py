"""HTTP client — same brain endpoints as the Android app."""
from __future__ import annotations

import io
import time
from typing import Any

import requests


class AegisClient:
    def __init__(self, base_url: str, api_key: str, account_id: str, device_id: str):
        self.base = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.account_id = account_id.strip()
        self.device_id = device_id.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": self.api_key,
                "X-Account-Id": self.account_id,
                "X-Device-Id": self.device_id,
                "X-Platform": "windows",
            }
        )

    def heartbeat(self) -> dict[str, Any]:
        try:
            r = self.session.post(
                f"{self.base}/api/devices/heartbeat",
                json={
                    "device_id": self.device_id,
                    "account_id": self.account_id,
                    "platform": "windows",
                    "ts": time.time(),
                },
                timeout=15,
            )
            return {"status": r.status_code, "body": r.text[:500]}
        except Exception as e:
            return {"status": 0, "body": str(e)}

    def upload_screenshot(self, png_bytes: bytes, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        # Brain expects multipart field name "image" (same as mobile).
        files = {"image": ("chart.png", io.BytesIO(png_bytes), "image/png")}
        data = {
            "account_id": self.account_id,
            "device_id": self.device_id,
            "platform": "windows",
            "captured_at_ms": str(int(time.time() * 1000)),
        }
        if meta:
            data.update({k: str(v) for k, v in meta.items()})
        try:
            r = self.session.post(f"{self.base}/aegis/analyze", files=files, data=data, timeout=60)
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:800]}
            return {"http": r.status_code, "body": body}
        except Exception as e:
            return {"http": 0, "body": {"error": str(e)}}

    # alias used by capture loop
    send_frame = upload_screenshot
