"""HTTP client — AEGIS V46 cloud brain (same contract as Android)."""
from __future__ import annotations

import io
import time
from typing import Any

import requests

CLIENT_VERSION = "1.46.0"
PLATFORM = "windows"


class AegisClient:
    def __init__(self, base_url: str, api_key: str, account_id: str, device_id: str):
        self.base = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.account_id = account_id.strip()
        self.device_id = device_id.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "X-API-Key": self.api_key,
                "X-Account-Id": self.account_id,
                "X-Device-Id": self.device_id,
                "X-Platform": PLATFORM,
                "X-Client-Version": CLIENT_VERSION,
                "User-Agent": f"AegisCapture-Win/{CLIENT_VERSION}",
            }
        )

    def heartbeat(self) -> dict[str, Any]:
        try:
            r = self.session.post(
                f"{self.base}/api/devices/heartbeat",
                json={
                    "device_id": self.device_id,
                    "account_id": self.account_id,
                    "platform": PLATFORM,
                    "client_version": CLIENT_VERSION,
                    "ts": time.time(),
                },
                timeout=15,
            )
            return {"status": r.status_code, "body": r.text[:500]}
        except Exception as e:
            return {"status": 0, "body": str(e)}

    def upload_screenshot(self, png_bytes: bytes, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        # Mobile + V46 brain expect multipart field "image".
        files = {"image": ("chart.png", io.BytesIO(png_bytes), "image/png")}
        data = {
            "account_id": self.account_id,
            "device_id": self.device_id,
            "platform": PLATFORM,
            "client_version": CLIENT_VERSION,
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

    send_frame = upload_screenshot

    # --- V46 registry (pairs + rulebooks; no indicator templates) ---

    def get_registry_active(self) -> dict[str, Any]:
        try:
            r = self.session.get(f"{self.base}/api/registry/active", timeout=20)
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            return {"http": r.status_code, "body": body}
        except Exception as e:
            return {"http": 0, "body": {"error": str(e)}}

    def list_pairs(self, tradeable_only: bool = True) -> dict[str, Any]:
        try:
            r = self.session.get(
                f"{self.base}/api/registry/pairs",
                params={"tradeable_only": str(tradeable_only).lower()},
                timeout=20,
            )
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            return {"http": r.status_code, "body": body}
        except Exception as e:
            return {"http": 0, "body": {"error": str(e)}}

    def list_rulebooks(self, instrument: str | None = None) -> dict[str, Any]:
        params = {}
        if instrument:
            params["instrument"] = instrument
        try:
            r = self.session.get(f"{self.base}/api/registry/rulebooks", params=params or None, timeout=20)
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            return {"http": r.status_code, "body": body}
        except Exception as e:
            return {"http": 0, "body": {"error": str(e)}}

    def set_risk_preset(self, preset: str) -> dict[str, Any]:
        try:
            r = self.session.post(
                f"{self.base}/api/account/risk_preset",
                json={"account_id": self.account_id, "risk_preset": preset},
                timeout=20,
            )
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            return {"http": r.status_code, "body": body}
        except Exception as e:
            return {"http": 0, "body": {"error": str(e)}}

    def get_account_status(self) -> dict[str, Any]:
        try:
            r = self.session.get(
                f"{self.base}/api/account/status",
                params={"account_id": self.account_id},
                timeout=20,
            )
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            return {"http": r.status_code, "body": body}
        except Exception as e:
            return {"http": 0, "body": {"error": str(e)}}
