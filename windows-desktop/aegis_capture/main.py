"""
AEGIS Capture for Windows — draggable chart region + cloud analysis.
Packaged as AEGIS_Capture.exe via PyInstaller.
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

from api_client import AegisClient
from capture_loop import CaptureLoop
from config import load, save


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
        label = tk.Label(
            self,
            text="Drag & resize over MT5 chart only\nThen click LOCK REGION",
            bg="#003333",
            fg="white",
            font=("Segoe UI", 11, "bold"),
        )
        label.pack(fill="both", expand=True, padx=8, pady=8)
        btn = tk.Button(self, text="LOCK REGION", command=self._lock, bg="#00aa88", fg="white")
        btn.pack(pady=8)

    def _lock(self):
        geo = self.geometry()  # WxH+X+Y
        wh, _, xy = geo.partition("+")
        w, h = wh.split("x")
        parts = geo.split("+")
        x, y = int(parts[1]), int(parts[2])
        region = {"left": x, "top": y, "width": int(w), "height": int(h)}
        self.on_lock(region)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AEGIS Capture — Windows")
        self.geometry("480x560")
        self.configure(bg="#0b1220")
        self.cfg = load()
        if not self.cfg.get("device_id"):
            self.cfg["device_id"] = f"win-{uuid.uuid4().hex[:10]}"
            save(self.cfg)

        self.client: AegisClient | None = None
        self.loop: CaptureLoop | None = None
        self.last_signal = "—"
        self.last_http = "—"
        self.running = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        style = {"bg": "#0b1220", "fg": "#e2e8f0", "font": ("Segoe UI", 10)}
        pad = {"padx": 12, "pady": 4}

        tk.Label(self, text="AEGIS Capture", font=("Segoe UI", 16, "bold"), bg="#0b1220", fg="#00e0c0").pack(pady=10)

        form = tk.Frame(self, bg="#0b1220")
        form.pack(fill="x", **pad)

        def row(label, key, show=None):
            tk.Label(form, text=label, **style).pack(anchor="w")
            e = tk.Entry(form, width=52, show=show)
            e.insert(0, str(self.cfg.get(key, "")))
            e.pack(fill="x", pady=2)
            setattr(self, f"ent_{key}", e)

        row("Server URL", "server_url")
        row("Account ID", "account_id")
        row("API Key", "api_key", show="*")
        row("Capture interval (sec)", "interval_sec")

        self.region_lbl = tk.Label(self, text="Region: not locked", **style)
        self.region_lbl.pack(anchor="w", **pad)

        btns = tk.Frame(self, bg="#0b1220")
        btns.pack(fill="x", **pad)
        tk.Button(btns, text="Select chart region", command=self._select_region, bg="#1e3a5f", fg="white").pack(
            side="left", padx=4
        )
        tk.Button(btns, text="Save settings", command=self._save, bg="#334155", fg="white").pack(side="left", padx=4)

        ctrl = tk.Frame(self, bg="#0b1220")
        ctrl.pack(fill="x", **pad)
        self.btn_start = tk.Button(ctrl, text="START", command=self._start, bg="#16a34a", fg="white", width=12)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = tk.Button(ctrl, text="STOP", command=self._stop, bg="#dc2626", fg="white", width=12, state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        self.status = tk.Label(self, text="Idle", **style, justify="left")
        self.status.pack(anchor="w", **pad)
        self.signal_lbl = tk.Label(self, text="Signal: —", font=("Segoe UI", 14, "bold"), bg="#0b1220", fg="#fbbf24")
        self.signal_lbl.pack(anchor="w", **pad)

        tk.Label(
            self,
            text="Tip: Keep MT5 chart visible inside the locked region.\n"
            "Use the same Account ID + API key as the mobile app / portal.",
            bg="#0b1220",
            fg="#94a3b8",
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", **pad)

    def _save(self):
        self.cfg["server_url"] = self.ent_server_url.get().strip()
        self.cfg["account_id"] = self.ent_account_id.get().strip()
        self.cfg["api_key"] = self.ent_api_key.get().strip()
        try:
            self.cfg["interval_sec"] = max(1, int(float(self.ent_interval_sec.get())))
        except ValueError:
            self.cfg["interval_sec"] = 3
        save(self.cfg)
        messagebox.showinfo("AEGIS", "Settings saved.")

    def _select_region(self):
        RegionOverlay(self, self._on_region_locked)

    def _on_region_locked(self, region: dict):
        self.cfg["region"] = region
        save(self.cfg)
        self.region_lbl.config(
            text=f"Region: {region['width']}x{region['height']} @ ({region['left']},{region['top']})"
        )

    def _start(self):
        self._save()
        if not self.cfg.get("api_key") or not self.cfg.get("account_id"):
            messagebox.showerror("AEGIS", "Account ID and API Key required.")
            return
        if not self.cfg.get("region"):
            messagebox.showerror("AEGIS", "Lock a chart region first.")
            return
        self.client = AegisClient(
            self.cfg["server_url"],
            self.cfg["api_key"],
            self.cfg["account_id"],
            self.cfg["device_id"],
        )
        self.loop = CaptureLoop(
            get_region=lambda: self.cfg.get("region"),
            interval_sec=float(self.cfg.get("interval_sec", 3)),
            on_frame=self._on_frame,
        )
        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.loop.start()
        self.status.config(text="Capturing…")
        threading.Thread(target=self._hb_loop, daemon=True).start()

    def _stop(self):
        self.running = False
        if self.loop:
            self.loop.stop()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status.config(text="Stopped")

    def _on_frame(self, png: bytes):
        if not self.client:
            return
        try:
            res = self.client.upload_screenshot(png)
            self.last_http = str(res.get("http"))
            body = res.get("body") or {}
            signal = body.get("signal") or body.get("direction") or body.get("action") or "HOLD"
            rule = body.get("rule") or body.get("rule_name") or ""
            conf = body.get("confidence", "")
            self.last_signal = f"{signal}  conf={conf}  {rule}"
            self.after(0, lambda: self.signal_lbl.config(text=f"Signal: {self.last_signal}"))
            self.after(
                0,
                lambda: self.status.config(
                    text=f"Frames={self.loop.frames if self.loop else 0}  HTTP={self.last_http}"
                ),
            )
            if signal in ("BUY", "SELL"):
                self.after(0, lambda: messagebox.showinfo("AEGIS Signal", f"{signal}\n{rule}"))
        except Exception as e:
            self.after(0, lambda: self.status.config(text=f"Upload error: {e}"))

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
