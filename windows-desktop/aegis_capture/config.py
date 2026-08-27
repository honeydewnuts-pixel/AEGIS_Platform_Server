"""Local settings for AEGIS Capture (Windows)."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".aegis" / "capture_config.json"

DEFAULTS = {
    "server_url": "https://aegis-api-0z1p.onrender.com",
    "account_id": "",
    "api_key": "",
    "device_id": "",
    "interval_sec": 3,
    "region": None,  # {left, top, width, height}
    "auto_start": False,
}


def load() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data}
    return dict(DEFAULTS)


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
