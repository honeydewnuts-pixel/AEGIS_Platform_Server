"""
====================================================================
Project : AEGIS
Company : Honeydewnuts Nigerian Limited

File    : brain_cv_service.py

Purpose
-------
Screenshot -> signal analysis, now driven by the full rulebook via
SignalRuleEngine + IndicatorHistoryService (see those files for the
"why"). This replaces the earlier #1/#2-cross-only version.

Extraction approach
--------------------
For each indicator color, contours are found across the WHOLE panel
(cropped to price_panel / indicator_panel per colors_config.json's
roi settings, so colors don't leak across panels). Only points near
the rightmost edge of the panel are kept - that's the most recent
reading, since MT5 charts scroll left-to-right. For bands (#1, #2,
#7, #8, which each render 3 lines - U/M/L - in one color), the
rightmost points are sorted by Y and assigned to U/M/L by position.

Known limitation: price_close is approximated from the rightmost
green/red candle body pixels, not read from an OHLC data feed. This
is a heuristic, not a precise value - fine for divergence direction
(which only needs relative highs/lows), less reliable for the exact
#7/#8 "price crosses above/below" filter. Flagging this rather than
overstating precision.
====================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.logging import configure_logging
from app.services.signal_rule_engine import SignalRuleEngine
from app.services.neural_service import NeuralAssistService

CONFIG_PATH = Path(__file__).resolve().parent.parent / "colors_config.json"

# Approximate default candle colors - MT5's common bullish/bearish scheme.
# Override in colors_config.json under "candle_colors" if your theme differs.
DEFAULT_BULLISH_RGB = [0, 200, 0]
DEFAULT_BEARISH_RGB = [220, 30, 30]

RIGHT_EDGE_WINDOW_PX = 18  # how many columns from the right edge count as "current"


class BrainCVService:

    def __init__(self) -> None:
        self.logger = configure_logging(__name__)
        self.config = self._load_config()
        self.rule_engine = SignalRuleEngine(
            divergence_lookback=self.config.get("history", {}).get("divergence_lookback_frames", 12),
            higher_high_lookback=self.config.get("history", {}).get("higher_high_lookback_frames", 8),
        )
        self.neural = NeuralAssistService()
        self.logger.info("BrainCVService loaded config version %s", self.config.get("config_version"))

    def _load_config(self) -> dict:
        # Prefer active versioned template when available
        try:
            from app.services.template_profile_service import TemplateProfileService
            return TemplateProfileService().vision_config_for_brain()
        except Exception:
            if not CONFIG_PATH.exists():
                raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)

    def reload_config(self) -> str:
        self.config = self._load_config()
        self.rule_engine = SignalRuleEngine(
            divergence_lookback=self.config.get("history", {}).get("divergence_lookback_frames", 12),
            higher_high_lookback=self.config.get("history", {}).get("higher_high_lookback_frames", 8),
        )
        self.neural = NeuralAssistService()
        ver = self.config.get("config_version", "?")
        self.logger.info("BrainCVService reloaded config %s", ver)
        return ver

    # ------------------------------------------------------------
    # Panel cropping
    # ------------------------------------------------------------

    def _crop_panel(self, image: np.ndarray, panel: str) -> np.ndarray:
        roi = self.config["roi"][panel]
        h = image.shape[0]
        top = int(h * roi["top_percent"])
        bottom = int(h * roi["bottom_percent"])
        return image[top:bottom, :, :]

    # ------------------------------------------------------------
    # Single-color point extraction
    # ------------------------------------------------------------

    def _find_color_points(self, hsv_image: np.ndarray, rgb: list[int], tolerance: dict) -> list[list[int]]:
        """
        Locate indicator pixels. White/gray lines need low-saturation ranges;
        saturated colours use hue windows. Both paths are more tolerant of
        phone brightness and JPEG compression than the original fixed S>=50 mask
        (which eliminated white Bollinger bands entirely).
        """
        hue_tol = int(tolerance.get("hue", 14))
        sat_tol = int(tolerance.get("saturation", 55))
        val_tol = int(tolerance.get("value", 50))
        hsv_color = cv2.cvtColor(np.uint8([[list(rgb)]]), cv2.COLOR_RGB2HSV)[0][0]
        h0, s0, v0 = int(hsv_color[0]), int(hsv_color[1]), int(hsv_color[2])

        # Near-white / gray (Bands #1 etc.): match on value, ignore hue
        if s0 < 40 or (rgb[0] > 200 and rgb[1] > 200 and rgb[2] > 200):
            lower = np.array([0, 0, max(0, v0 - max(val_tol, 60))])
            upper = np.array([180, max(40, s0 + 40), 255])
        else:
            lower = np.array([
                max(0, h0 - hue_tol),
                max(0, s0 - sat_tol),
                max(0, v0 - val_tol),
            ])
            upper = np.array([
                min(180, h0 + hue_tol),
                255,
                255,
            ])
            # Hue wrap-around (reds near 0/180)
            if h0 - hue_tol < 0 or h0 + hue_tol > 180:
                lower1 = np.array([0, lower[1], lower[2]])
                upper1 = np.array([min(180, h0 + hue_tol), 255, 255])
                lower2 = np.array([max(0, h0 - hue_tol + 180) % 180, lower[1], lower[2]])
                upper2 = np.array([180, 255, 255])
                mask = cv2.bitwise_or(
                    cv2.inRange(hsv_image, lower1, upper1),
                    cv2.inRange(hsv_image, lower2, upper2),
                )
            else:
                mask = cv2.inRange(hsv_image, lower, upper)

        if s0 < 40 or (rgb[0] > 200 and rgb[1] > 200 and rgb[2] > 200):
            mask = cv2.inRange(hsv_image, lower, upper)

        # Light morphological open to drop speckles without killing thin lines
        kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        points = []
        min_area = self.config.get("noise_filter", {}).get("minimum_contour_area", 4)
        for cnt in contours:
            if cv2.contourArea(cnt) >= min_area:
                m = cv2.moments(cnt)
                if m["m00"] != 0:
                    cx = int(m["m10"] / m["m00"])
                    cy = int(m["m01"] / m["m00"])
                    points.append([cx, cy])
        return sorted(points, key=lambda p: p[0])

    def _rightmost_y_values(self, points: list[list[int]], panel_width: int) -> list[int]:
        if not points:
            return []
        max_x = max(p[0] for p in points)
        cutoff = max(0, max_x - RIGHT_EDGE_WINDOW_PX)
        return [p[1] for p in points if p[0] >= cutoff]

    def _single_line_y(self, points: list[list[int]], panel_width: int) -> float | None:
        ys = self._rightmost_y_values(points, panel_width)
        if not ys:
            return None
        return float(np.mean(ys))

    def _band_ulm(self, points: list[list[int]], panel_width: int) -> dict[str, float] | None:
        """Cluster rightmost points of a 3-line band into U/M/L by Y order."""
        ys = sorted(self._rightmost_y_values(points, panel_width))
        if not ys:
            return None
        if len(ys) == 1:
            y = float(ys[0])
            return {"U": y - 4.0, "M": y, "L": y + 4.0}
        if len(ys) == 2:
            return {"U": float(ys[0]), "M": float(sum(ys) / 2), "L": float(ys[1])}
        thirds = np.array_split(ys, 3)
        u, m, l = [float(np.mean(part)) for part in thirds]
        return {"U": u, "M": m, "L": l}

    # ------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------

    def extract_frame_state(self, image: np.ndarray) -> dict[str, Any]:
        indicator_panel = self._crop_panel(image, "indicator_panel")
        price_panel = self._crop_panel(image, "price_panel")

        hsv_indicator = cv2.cvtColor(indicator_panel, cv2.COLOR_BGR2HSV)
        hsv_price = cv2.cvtColor(price_panel, cv2.COLOR_BGR2HSV)

        ind = self.config["indicators"]
        price_ind = self.config.get("price_panel_indicators", {})

        band1_pts = self._find_color_points(hsv_indicator, ind["#1"]["rgb"], ind["#1"]["hsv_tolerance"])
        band2_pts = self._find_color_points(hsv_indicator, ind["#2"]["rgb"], ind["#2"]["hsv_tolerance"])
        williams3_pts = self._find_color_points(hsv_indicator, ind["#3"]["rgb"], ind["#3"]["hsv_tolerance"])
        ma4_pts = self._find_color_points(hsv_indicator, ind["#4"]["rgb"], ind["#4"]["hsv_tolerance"])
        cci5_pts = self._find_color_points(hsv_indicator, ind["#5"]["rgb"], ind["#5"]["hsv_tolerance"])
        rsi6_pts = self._find_color_points(hsv_indicator, ind["#6"]["rgb"], ind["#6"]["hsv_tolerance"])

        w_ind = indicator_panel.shape[1]

        frame_state: dict[str, Any] = {
            "band1": self._band_ulm(band1_pts, w_ind),
            "band2": self._band_ulm(band2_pts, w_ind),
            "williams3": self._single_line_y(williams3_pts, w_ind),
            "ma4": self._single_line_y(ma4_pts, w_ind),
            "cci5": self._single_line_y(cci5_pts, w_ind),
            "rsi6": self._single_line_y(rsi6_pts, w_ind),
        }

        # Price panel #7/#8, if mapped
        w_price = price_panel.shape[1]
        if price_ind.get("#7"):
            pts7 = self._find_color_points(hsv_price, price_ind["#7"]["rgb"], price_ind["#7"]["hsv_tolerance"])
            frame_state["price_band7"] = self._band_ulm(pts7, w_price)
        if price_ind.get("#8"):
            pts8 = self._find_color_points(hsv_price, price_ind["#8"]["rgb"], price_ind["#8"]["hsv_tolerance"])
            frame_state["price_band8"] = self._band_ulm(pts8, w_price)

        # Approximate price close from rightmost candle body pixels.
        candle_cfg = self.config.get("candle_colors", {})
        bull_rgb = candle_cfg.get("bullish_rgb", DEFAULT_BULLISH_RGB)
        bear_rgb = candle_cfg.get("bearish_rgb", DEFAULT_BEARISH_RGB)
        bull_pts = self._find_color_points(hsv_price, bull_rgb, {"hue": 15})
        bear_pts = self._find_color_points(hsv_price, bear_rgb, {"hue": 15})
        all_candle_pts = bull_pts + bear_pts
        frame_state["price_close"] = self._single_line_y(all_candle_pts, w_price)

        return frame_state

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def decode_image(self, image_bytes: bytes) -> np.ndarray:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode image - unsupported or corrupt file.")
        return image

    def evaluate(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        """Rule engine first, then Phase A/B neural assist (confidence / veto)."""
        result = self.rule_engine.evaluate(history)
        conf = 0.85 if result.fired else (0.15 if result.rule_name == "warming_up" else 0.0)
        base = {
            "signal": result.signal or "HOLD",
            "confidence": conf,
            "rule_name": result.rule_name,
            "details": f"{result.rule_name}: {result.reason}",
            "frames_in_history": len(history),
        }
        try:
            return self.neural.apply(history, base)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Neural assist skipped: %s", exc)
            base["neural_applied"] = False
            return base
