"""Persistent settings for AEGIS Capture (Windows)."""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AEGIS_Capture"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "aegis_config.json"

DEFAULT_CONFIG = {
    "server_url": "https://aegis-api-0z1p.onrender.com",
    "account_id": "",
    "api_key": "",
    "device_id": "",
    "interval_sec": 5.0,
    "region": {"left": 200, "top": 150, "width": 640, "height": 400},
}


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(data)
            # normalize region keys
            reg = cfg.get("region") or {}
            if "x" in reg and "left" not in reg:
                cfg["region"] = {
                    "left": int(reg.get("x", 200)),
                    "top": int(reg.get("y", 150)),
                    "width": int(reg.get("width", 640)),
                    "height": int(reg.get("height", 400)),
                }
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# aliases used by older snippets
load_config = load
save_config = save
