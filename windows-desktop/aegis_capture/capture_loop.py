"""Periodic region capture using mss."""
from __future__ import annotations

import threading
import time
from typing import Callable

import mss
from PIL import Image


class CaptureLoop:
    def __init__(
        self,
        get_region: Callable[[], dict | None],
        interval_sec: float,
        on_frame: Callable[[bytes], None],
    ):
        self.get_region = get_region
        self.interval_sec = max(1.0, float(interval_sec))
        self.on_frame = on_frame
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.frames = 0
        self.last_error = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        with mss.mss() as sct:
            while not self._stop.is_set():
                region = self.get_region()
                try:
                    if region and region.get("width", 0) > 10:
                        mon = {
                            "left": int(region["left"]),
                            "top": int(region["top"]),
                            "width": int(region["width"]),
                            "height": int(region["height"]),
                        }
                        shot = sct.grab(mon)
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                        buf = __import__("io").BytesIO()
                        img.save(buf, format="PNG")
                        self.frames += 1
                        self.on_frame(buf.getvalue())
                    else:
                        self.last_error = "No region locked"
                except Exception as e:
                    self.last_error = str(e)
                self._stop.wait(self.interval_sec)
