"""Background capture of a locked screen region → AEGIS cloud."""
from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from typing import Any, Callable

import mss
from PIL import Image

from config import load


def _write_signal_file(signal: str) -> None:
    """Drop signal for AEGIS_Executor.mq5 (FILE_COMMON folder on Windows)."""
    try:
        common = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
        common.mkdir(parents=True, exist_ok=True)
        (common / "aegis_signal.txt").write_text(signal.strip().upper() + "\n", encoding="ascii")
    except Exception:
        pass


class CaptureLoop(threading.Thread):
    def __init__(
        self,
        api_client,
        region: dict[str, int],
        interval_sec: float = 5.0,
        on_result: Callable[[dict[str, Any]], None] | None = None,
    ):
        super().__init__(daemon=True)
        self.api_client = api_client
        self.region = region
        self.interval_sec = max(2.0, float(interval_sec))
        self.on_result = on_result
        self._stop = threading.Event()
        self.frames = 0
        self.uploads_ok = 0

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        monitor = {
            "left": int(self.region.get("left", self.region.get("x", 200))),
            "top": int(self.region.get("top", self.region.get("y", 150))),
            "width": max(32, int(self.region.get("width", 640))),
            "height": max(32, int(self.region.get("height", 400))),
        }
        with mss.mss() as sct:
            while not self._stop.is_set():
                t0 = time.time()
                try:
                    shot = sct.grab(monitor)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    png = buf.getvalue()
                    self.frames += 1
                    result = self.api_client.upload_screenshot(png)
                    http = int(result.get("http") or 0)
                    body = result.get("body") or {}
                    if http == 200:
                        self.uploads_ok += 1
                        sig = str(body.get("signal") or body.get("action") or "HOLD").upper()
                        if sig in ("BUY", "SELL", "HOLD"):
                            _write_signal_file(sig)
                    if self.on_result:
                        self.on_result(
                            {
                                "http": http,
                                "body": body,
                                "frames": self.frames,
                                "uploads_ok": self.uploads_ok,
                            }
                        )
                except Exception as e:
                    if self.on_result:
                        self.on_result({"http": 0, "body": {"error": str(e)}, "frames": self.frames, "uploads_ok": self.uploads_ok})
                elapsed = time.time() - t0
                self._stop.wait(max(0.2, self.interval_sec - elapsed))
