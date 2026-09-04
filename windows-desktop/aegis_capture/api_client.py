"""HTTP client — same brain endpoints as the Android app."""
from __future__ import annotations

import io
import time
from typing import Any

import requests


class AegisClient:
    def __init__(self, base_url: str, api_key: str, account_id: str, device_id: str):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.account_id = account_id
        self.device_id = device_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "X-API-Key": api_key,
                "X-Account-Id": account_id,
                "X-Device-Id": device_id,
                "X-Platform": "windows",
            }
        )

    def heartbeat(self) -> dict[str, Any]:
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

    def upload_screenshot(self, png_bytes: bytes, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        files = {"file": ("chart.png", io.BytesIO(png_bytes), "image/png")}
        data = {
            "account_id": self.account_id,
            "device_id": self.device_id,
            "platform": "windows",
        }
        if meta:
            data.update({k: str(v) for k, v in meta.items()})
        r = self.session.post(f"{self.base}/aegis/analyze", files=files, data=data, timeout=45)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:800]}
        return {"http": r.status_code, "body": body}
