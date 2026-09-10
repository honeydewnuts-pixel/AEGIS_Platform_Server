"""
AEGIS Capture for Windows — V46 baseline.

- Draggable region over plain MT5 price chart (no indicator pack required)
- Cloud analysis via /aegis/analyze
- Pairs + rulebook registry (/api/registry/*)
- Risk presets (server-side lot sizing)
"""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import uuid

from api_client import AegisClient, CLIENT_VERSION
from capture_loop import CaptureLoop
from config import load, save


def _resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)


class RegionOverlay(tk.Toplevel):
    def __init__(self, master, on_lock):
        super().__init__(master)
        self.on_lock = on_lock
        self.attributes("-alpha", 0.35)
        self.attributes("-topmost", True)
        self.geometry("640x400+200+150")
        self.title("AEGIS V46 — drag over MT5 chart, then Lock")
        self.configure(bg="#00c8c8")
        tk.Label(
            self,
            text="Drag & resize over the MT5 price chart only\n(No indicators required) · then LOCK REGION",
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"AEGIS Capture — macOS V{CLIENT_VERSION}")
        self.configure(bg="#0b1220")
        self.geometry("520x560")
        self.resizable(False, False)

        self.cfg = load()
        if not self.cfg.get("device_id"):
            self.cfg["device_id"] = f"mac-{uuid.uuid4().hex[:12]}"
            save(self.cfg)

        self.client: AegisClient | None = None
        self.loop: CaptureLoop | None = None
        self.running = False

        self.status = tk.StringVar(value="Idle — plain MT5 chart, server rulebooks")
        self.signal_var = tk.StringVar(value="Signal: —")
        self.diag = tk.StringVar(value="HTTP: —")
        self.region_lbl = tk.StringVar(value="Region: not set")
        self.registry_lbl = tk.StringVar(value="Registry: not loaded")

        pad = {"padx": 12, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text=f"AEGIS V46  ·  client {CLIENT_VERSION}", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            frm,
            text="No indicator template. Server pairs + rulebook registry decides analysis.",
            wraplength=480,
        ).pack(anchor="w", **pad)

        grid = ttk.Frame(frm)
        grid.pack(fill="x", pady=8)
        self.url_var = tk.StringVar(value=self.cfg.get("server_url") or "")
        self.acc_var = tk.StringVar(value=self.cfg.get("account_id") or "")
        self.key_var = tk.StringVar(value=self.cfg.get("api_key") or "")
        self.interval_var = tk.StringVar(value=str(self.cfg.get("interval_sec") or 5))
        self.risk_var = tk.StringVar(value=self.cfg.get("risk_preset") or "standard")

        rows = [
            ("Server URL", self.url_var),
            ("Account ID", self.acc_var),
            ("API Key", self.key_var),
            ("Interval (sec)", self.interval_var),
        ]
        for i, (lab, var) in enumerate(rows):
            ttk.Label(grid, text=lab).grid(row=i, column=0, sticky="e", padx=4, pady=2)
            show = "*" if lab == "API Key" else None
            ttk.Entry(grid, textvariable=var, width=42, show=show).grid(row=i, column=1, sticky="we", pady=2)

        ttk.Label(grid, text="Risk preset").grid(row=4, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(
            grid,
            textvariable=self.risk_var,
            values=("conservative", "standard", "aggressive"),
            state="readonly",
            width=20,
        ).grid(row=4, column=1, sticky="w", pady=2)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=2)
        ttk.Button(btns, text="Set chart region", command=self._pick_region).pack(side="left", padx=2)
        ttk.Button(btns, text="Load registry", command=self._load_registry).pack(side="left", padx=2)
        ttk.Button(btns, text="Apply risk", command=self._apply_risk).pack(side="left", padx=2)

        run = ttk.Frame(frm)
        run.pack(fill="x", pady=8)
        self.btn_start = ttk.Button(run, text="START", command=self._start)
        self.btn_start.pack(side="left", padx=2)
        self.btn_stop = ttk.Button(run, text="STOP", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=2)

        ttk.Label(frm, textvariable=self.region_lbl).pack(anchor="w")
        ttk.Label(frm, textvariable=self.registry_lbl, wraplength=480).pack(anchor="w")
        ttk.Label(frm, textvariable=self.signal_var, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=6)
        ttk.Label(frm, textvariable=self.diag).pack(anchor="w")
        ttk.Label(frm, textvariable=self.status, wraplength=480).pack(anchor="w", pady=6)

        if self.cfg.get("region"):
            r = self.cfg["region"]
            self.region_lbl.set(f"Region: {r['left']},{r['top']} {r['width']}×{r['height']}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _save(self):
        self.cfg["server_url"] = self.url_var.get().strip()
        self.cfg["account_id"] = self.acc_var.get().strip()
        self.cfg["api_key"] = self.key_var.get().strip()
        try:
            self.cfg["interval_sec"] = max(2, int(float(self.interval_var.get())))
        except ValueError:
            self.cfg["interval_sec"] = 5
        self.cfg["risk_preset"] = self.risk_var.get().strip() or "standard"
        self.cfg["client_version"] = CLIENT_VERSION
        save(self.cfg)
        self.status.set("Settings saved.")

    def _client(self) -> AegisClient | None:
        self._save()
        if not self.cfg.get("api_key") or not self.cfg.get("server_url"):
            messagebox.showerror("AEGIS", "Server URL and API Key are required.")
            return None
        return AegisClient(
            self.cfg["server_url"],
            self.cfg["api_key"],
            self.cfg.get("account_id") or "",
            self.cfg.get("device_id") or "mac-device",
        )

    def _pick_region(self):
        RegionOverlay(self, self._on_region)

    def _on_region(self, region: dict):
        self.cfg["region"] = region
        save(self.cfg)
        self.region_lbl.set(f"Region: {region['left']},{region['top']} {region['width']}×{region['height']}")

    def _load_registry(self):
        c = self._client()
        if not c:
            return

        def work():
            active = c.get_registry_active()
            pairs = c.list_pairs()
            body = active.get("body") if isinstance(active.get("body"), dict) else {}
            pb = pairs.get("body") if isinstance(pairs.get("body"), dict) else {}
            pair_list = pb.get("pairs") or []
            n = len(pair_list) if isinstance(pair_list, list) else 0
            msg = (
                f"Registry HTTP {active.get('http')}/{pairs.get('http')} · "
                f"tradeable pairs: {n} · indicators_required={pb.get('indicators_required', False)} · "
                f"active={str(body)[:120]}"
            )

            def ui():
                self.registry_lbl.set(msg)
                self.status.set("Registry loaded (V46 pairs + rulebooks).")

            self.after(0, ui)

        threading.Thread(target=work, daemon=True).start()

    def _apply_risk(self):
        c = self._client()
        if not c:
            return
        preset = self.risk_var.get().strip() or "standard"

        def work():
            r = c.set_risk_preset(preset)
            body = r.get("body") if isinstance(r.get("body"), dict) else {}

            def ui():
                lot = body.get("calculated_lot_size")
                mx = body.get("plan_max_lot")
                self.status.set(f"Risk preset '{preset}' → HTTP {r.get('http')} lot={lot} max={mx}")

            self.after(0, ui)

        threading.Thread(target=work, daemon=True).start()

    def _start(self):
        c = self._client()
        if not c:
            return
        if not self.cfg.get("region"):
            messagebox.showwarning("AEGIS", "Set chart region first (drag over MT5 price chart).")
            return
        self.client = c
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
        self.status.set("Capturing… keep MT5 price chart under the locked region.")
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
            rule = body.get("rule_name") or body.get("rule") or ""
            pair = body.get("pair") or body.get("instrument") or ""
            self.signal_var.set(
                f"Signal: {sig}"
                + (f"  ({conf})" if conf is not None else "")
                + (f"  [{pair}]" if pair else "")
            )
            self.diag.set(
                f"HTTP: {result.get('http')} · frames {result.get('frames')} · "
                f"uploads {result.get('uploads_ok')} · {rule}"
            )
            if result.get("http") == 200:
                self.status.set("Last upload OK")
            else:
                self.status.set(f"Upload issue HTTP {result.get('http')}")

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
