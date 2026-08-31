"""AEGIS Neural v3 feature extraction.

Mirrors neural_features.py's approach (temporal window -> mean/last/std/
slope per channel) but built on the v3 rulebook's 5-indicator stack
instead of v2's 9-indicator stack.

Channels (11 raw + 2 regime flags = 13), each summarized as
mean/last/std/slope -> 13*4 = 52 deterministic inputs.
"""
from __future__ import annotations

from typing import Any
import numpy as np

FEATURE_DIM = 52
HISTORY_WINDOW = 20  # matches SignalRuleEngineV3's default touch_window

FEATURE_CHANNELS = (
    "p7_u", "p7_m", "p7_l",   # price_band7 (#7 BB34, price panel)
    "p8_u", "p8_m", "p8_l",   # price_band8 (#8 BB17, price panel)
    "rsi6", "ma4",            # #6 RSI9, #4 MA7(on RSI9)
    "b1_u", "b1_m", "b1_l",   # band1 (#1 Bands34 on MA7)
    "contraction", "expansion",
)
FEATURE_NAMES = [f"{c}_{stat}" for c in FEATURE_CHANNELS for stat in ("mean", "last", "std", "slope")]

# Normalizing divisor: v3 indicators live in raw pixel-Y space, which is
# resolution-dependent. 720.0 matches the reference 1440x720 screenshot
# capture used in training - update this if the capture resolution
# changes, or better, switch capture_loop.py to emit a resolution-
# normalized 0-1 Y before this ever reaches the model.
Y_NORM = 720.0


def _value(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _band(frame: dict[str, Any], key: str) -> tuple[float, float, float]:
    b = frame.get(key)
    if not isinstance(b, dict):
        return 0.0, 0.0, 0.0
    return _value(b.get("U")), _value(b.get("M")), _value(b.get("L"))


def _contraction_flag(frame: dict[str, Any]) -> float:
    p7, p8 = frame.get("price_band7"), frame.get("price_band8")
    if not isinstance(p7, dict) or not isinstance(p8, dict):
        return 0.0
    return 1.0 if (_value(p8.get("U")) > _value(p7.get("U")) and _value(p8.get("L")) < _value(p7.get("L"))) else 0.0


def _expansion_flag(frame: dict[str, Any]) -> float:
    p7, p8 = frame.get("price_band7"), frame.get("price_band8")
    if not isinstance(p7, dict) or not isinstance(p8, dict):
        return 0.0
    return 1.0 if (_value(p8.get("U")) < _value(p7.get("U")) and _value(p8.get("L")) > _value(p7.get("L"))) else 0.0


def _frame_channels(frame: dict[str, Any]) -> list[float]:
    p7 = _band(frame, "price_band7")
    p8 = _band(frame, "price_band8")
    b1 = _band(frame, "band1")
    return [
        *[v / Y_NORM for v in p7],
        *[v / Y_NORM for v in p8],
        _value(frame.get("rsi6")) / Y_NORM,
        _value(frame.get("ma4")) / Y_NORM,
        *[v / Y_NORM for v in b1],
        _contraction_flag(frame),
        _expansion_flag(frame),
    ]


def extract_feature_vector(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the v3 temporal feature vector (52 values)."""
    frames = history[-HISTORY_WINDOW:]
    if not frames:
        frames = [{}]
    arr = np.asarray([_frame_channels(f) for f in frames], dtype=np.float32)
    if arr.shape[0] < HISTORY_WINDOW:
        pad = np.repeat(arr[:1], HISTORY_WINDOW - arr.shape[0], axis=0)
        arr = np.vstack([pad, arr])
    x = np.arange(HISTORY_WINDOW, dtype=np.float32)
    features: list[float] = []
    for j in range(arr.shape[1]):
        v = arr[:, j]
        slope = float(np.polyfit(x, v, 1)[0]) if HISTORY_WINDOW > 1 else 0.0
        features.extend((float(v.mean()), float(v[-1]), float(v.std()), slope))
    last = frames[-1] if frames else {}
    bands_ok = bool(
        isinstance(last.get("price_band7"), dict)
        and isinstance(last.get("price_band8"), dict)
        and isinstance(last.get("band1"), dict)
    )
    return {
        "vector": features,
        "names": FEATURE_NAMES,
        "n_frames": len(history),
        "completeness": min(1.0, len(history) / float(HISTORY_WINDOW)),
        "bands_ok": bands_ok,
    }
