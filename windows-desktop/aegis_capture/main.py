"""
AEGIS Capture for Windows — draggable chart region + cloud analysis + Color Guide.
Packaged as AEGIS_Capture.exe via PyInstaller.
"""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import uuid

from api_client import AegisClient
from capture_loop import CaptureLoop
from config import load, save


def _resource_path(*parts: str) -> Path:
    """Works in PyInstaller bundle and plain Python."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)


class RegionOverlay(tk.Toplevel):
    """Semi-transparent resizable frame to select MT5 chart area."""

    def __init__(self, master, on_lock):
        super().__init__(master)
        self.on_lock = on_lock
        self.attributes("-alpha", 0.35)
        self.attributes("-topmost", True)
        self.geometry("640x400+200+150")
        self.title("AEGIS — drag over MT5 chart, then Lock")
        self.configure(bg="#00c8c8")
        tk.Label(
            self,
            text="Drag & resize over MT5 chart only\nThen click LOCK REGION",
            bg="#003333",
            fg="white",
            font=("Segoe UI", 11, "bold"),
        ).pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(self, text="LOCK REGION", command=self._lock, bg="#00aa88", fg="white").pack(pady=8)

    def _lock(self):
        geo = self.geometry()
        parts = geo.replace("x", "+").split("+")
        w, h, x, y = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        self.on_lock({"left": x, "top": y, "width": w, "height": h})
        self.destroy()


class ColorGuideWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("AEGIS MT5 Color Match Guide")
        self.configure(bg="#0b1220")
        self.attributes("-topmost", True)
        path = _resource_path("assets", "mt5_color_match_guide.jpg")
        if not path.exists():
            path = _resource_path("guides", "mt5_color_match_guide.jpg")
        tk.Label(
            self,
            text="Install indicators in this exact order and RGB colors (dark theme).",
            bg="#0b1220",
            fg="#e2e8f0",
            font=("Segoe UI", 10),
        ).pack(pady=8)
        if path.exists():
            try:
                from PIL import Image, ImageTk

                img = Image.open(path)
                img.thumbnail((720, 1100))
                self._photo = ImageTk.PhotoImage(img)
                tk.Label(self, image=self._photo, bg="#0b1220").pack(padx=8, pady=8)
            except Exception as e:
                tk.Label(self, text=f"Could not load guide image: {e}", fg="red", bg="#0b1220").pack()
        else:
            tk.Label(self, text=f"Guide not found at {path}", fg="#fbbf24", bg="#0b1220").pack(padx=12, pady=12)
        tk.Button(self, text="Close", command=self.destroy).pack(pady=8)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AEGIS Capture — Windows")
        self.geometry("520x640")
        self.configure(bg="#0b1220")
        self.cfg = load()
        if not self.cfg.get("device_id"):
            self.cfg["device_id"] = f"win-{uuid.uuid4().hex[:10]}"
            save(self.cfg)

        self.client: AegisClient | None = None
        self.loop: CaptureLoop | None = None
        self.running = False
        self.vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}
        tk.Label(self, text="AEGIS Capture", font=("Segoe UI", 16, "bold"), bg="#0b1220", fg="#00e0c0").pack(pady=10)
        form = tk.Frame(self, bg="#0b1220")
        form.pack(fill="x", **pad)

        def row(label: str, key: str, show: str | None = None):
            tk.Label(form, text=label, bg="#0b1220", fg="#94a3b8", anchor="w").pack(fill="x")
            var = tk.StringVar(value=str(self.cfg.get(key, "")))
            self.vars[key] = var
            e = tk.Entry(form, textvariable=var, show=show, bg="#1e293b", fg="white", insertbackground="white")
            e.pack(fill="x", pady=2)

        row("Server URL", "server_url")
        row("Account ID", "account_id")
        row("API Key", "api_key", show="*")
        row("Capture interval (sec)", "interval_sec")

        btns = tk.Frame(self, bg="#0b1220")
        btns.pack(fill="x", pady=8, padx=12)
        tk.Button(btns, text="SAVE", command=self._save, bg="#334155", fg="white", width=12).pack(side="left", padx=4)
        tk.Button(btns, text="SELECT CHART REGION", command=self._select_region, bg="#0ea5e9", fg="white").pack(side="left", padx=4)
        tk.Button(btns, text="COLOR GUIDE", command=self._color_guide, bg="#a855f7", fg="white").pack(side="left", padx=4)

        run = tk.Frame(self, bg="#0b1220")
        run.pack(fill="x", padx=12, pady=8)
        self.btn_start = tk.Button(run, text="START", command=self._start, bg="#16a34a", fg="white", width=14, height=2)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = tk.Button(run, text="STOP", command=self._stop, bg="#dc2626", fg="white", width=14, height=2, state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        self.status = tk.StringVar(value="Idle — set credentials, lock chart region, START")
        tk.Label(self, textvariable=self.status, bg="#0b1220", fg="#e2e8f0", wraplength=480, justify="left").pack(fill="x", padx=12, pady=8)
        self.signal_var = tk.StringVar(value="Signal: —")
        tk.Label(self, textvariable=self.signal_var, bg="#0b1220", fg="#fbbf24", font=("Segoe UI", 14, "bold")).pack(pady=4)
        self.diag = tk.StringVar(value="HTTP: — · frames 0 · uploads 0")
        tk.Label(self, textvariable=self.diag, bg="#0b1220", fg="#94a3b8").pack(pady=2)

        reg = self.cfg.get("region") or {}
        self.region_lbl = tk.StringVar(
            value=f"Region: {reg.get('left', '?')},{reg.get('top', '?')} {reg.get('width', '?')}×{reg.get('height', '?')}"
        )
        tk.Label(self, textvariable=self.region_lbl, bg="#0b1220", fg="#64748b").pack(pady=4)

        tk.Label(
            self,
            text="Tip: MT5 chart must be visible under the locked region.\n"
            "BUY/SELL also written to MetaQuotes Common Files\\aegis_signal.txt for the EA.",
            bg="#0b1220",
            fg="#64748b",
            justify="left",
        ).pack(padx=12, pady=8)

    def _save(self):
        for k, var in self.vars.items():
            val = var.get().strip()
            if k == "interval_sec":
                try:
                    self.cfg[k] = float(val)
                except ValueError:
                    self.cfg[k] = 5.0
            else:
                self.cfg[k] = val
        save(self.cfg)
        messagebox.showinfo("AEGIS", "Settings saved.")

    def _select_region(self):
        RegionOverlay(self, self._on_region_locked)

    def _on_region_locked(self, region: dict):
        self.cfg["region"] = region
        save(self.cfg)
        self.region_lbl.set(f"Region: {region['left']},{region['top']} {region['width']}×{region['height']}")

    def _color_guide(self):
        ColorGuideWindow(self)

    def _start(self):
        self._save()
        if not self.cfg.get("api_key") or not self.cfg.get("server_url"):
            messagebox.showerror("AEGIS", "Server URL and API Key are required.")
            return
        self.client = AegisClient(
            self.cfg["server_url"],
            self.cfg["api_key"],
            self.cfg.get("account_id") or "",
            self.cfg.get("device_id") or "win-device",
        )
        self.loop = CaptureLoop(
            self.client,
            self.cfg.get("region") or {},
            float(self.cfg.get("interval_sec") or 5),
            on_result=self._on_result,
        )
        self.loop.start()
        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.status.set("Capturing… keep MT5 chart visible under the locked region.")
        threading.Thread(target=self._hb_loop, daemon=True).start()

    def _stop(self):
        if self.loop:
            self.loop.stop()
            self.loop = None
        self.running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status.set("Stopped.")

    def _on_result(self, result: dict):
        def ui():
            body = result.get("body") or {}
            sig = body.get("signal") or body.get("action") or "—"
            conf = body.get("confidence")
            rule = body.get("rule_name") or ""
            self.signal_var.set(f"Signal: {sig}" + (f"  ({conf})" if conf is not None else ""))
            self.diag.set(
                f"HTTP: {result.get('http')} · frames {result.get('frames')} · uploads {result.get('uploads_ok')} · {rule}"
            )
            if result.get("http") == 200:
                self.status.set("Last upload OK")
            else:
                self.status.set(f"Upload issue HTTP {result.get('http')} — {body}")

        self.after(0, ui)

    def _hb_loop(self):
        while self.running and self.client:
            try:
                self.client.heartbeat()
            except Exception:
                pass
            time.sleep(30)

    def _on_close(self):
        self._stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
