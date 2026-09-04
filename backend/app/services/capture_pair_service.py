"""Persist screenshot + synchronized MT5 M1 snapshot as one capture pair."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", value.strip()) or "UNKNOWN"


class CapturePairService:
    def __init__(self) -> None:
        self.root = Path(settings.CAPTURE_PAIR_DIRECTORY)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, png_bytes: bytes, account_id: str, symbol: str, captured_at_ms: int, market: dict[str, Any]) -> dict[str, Any]:
        dt = datetime.fromtimestamp(captured_at_ms / 1000.0, tz=timezone.utc)
        frame_id = f"{_safe(symbol)}_{dt.strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
        folder = self.root / _safe(account_id)
        folder.mkdir(parents=True, exist_ok=True)
        png_path = folder / f"frame_{frame_id}.png"
        json_path = folder / f"frame_{frame_id}.json"
        payload = {
            "frame_id": frame_id,
            "captured_at_ms": captured_at_ms,
            "captured_at_utc": dt.isoformat(),
            "account_id": account_id,
            "symbol": symbol,
            "timeframe": "M1",
            "screenshot_file": png_path.name,
            "market_snapshot": market,
        }
        png_path.write_bytes(png_bytes)
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "frame_id": frame_id,
            "screenshot_file": str(png_path),
            "market_json_file": str(json_path),
            "market_snapshot": market,
        }
