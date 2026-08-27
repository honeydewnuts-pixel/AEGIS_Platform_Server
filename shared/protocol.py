"""
AEGIS shared wire protocol — used by Android, Windows, macOS, iOS clients.
All platforms speak the same JSON envelope to the cloud brain.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

Platform = Literal["android", "windows", "macos", "ios"]
MessageType = Literal[
    "screenshot",
    "trade_signal",
    "heartbeat",
    "auth",
    "analysis_result",
    "device_bind",
]


class Envelope(TypedDict, total=False):
    device_id: str
    account_id: str
    platform: Platform
    type: MessageType
    api_key: str
    ts: float
    payload: dict[str, Any]


# REST paths (HTTP multipart still used for screenshots on mobile/desktop)
PATH_ANALYZE = "/aegis/analyze"
PATH_TELEMETRY = "/api/telemetry"
PATH_AUTH_LOGIN = "/api/auth/login"
PATH_DEVICES_ME = "/api/devices/me"
PATH_HEARTBEAT = "/api/devices/heartbeat"
WS_SIGNALS = "/ws/signals"


def make_heartbeat(device_id: str, account_id: str, platform: Platform) -> Envelope:
    return {
        "device_id": device_id,
        "account_id": account_id,
        "platform": platform,
        "type": "heartbeat",
        "ts": __import__("time").time(),
        "payload": {"status": "online"},
    }


def make_screenshot_meta(
    device_id: str,
    account_id: str,
    platform: Platform,
    interval_ms: int,
    region: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "account_id": account_id,
        "platform": platform,
        "interval_ms": interval_ms,
        "region": region or {},
    }
