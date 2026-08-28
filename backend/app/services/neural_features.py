"""AEGIS Neural v2 feature extraction.

The v2 neural scorer consumes a 12-frame temporal window.  Each frame carries
17 visual channels in the same order used during training:
#1 U/M/L, #2 U/M/L, #3, #4, #5, #6, price close, #7 U/M/L, #8 U/M/L.
Each channel is summarized as mean, latest value, standard deviation and slope,
producing 68 deterministic inputs for the deployed MLP.
"""
from __future__ import annotations

from typing import Any
import numpy as np

FEATURE_DIM = 68
HISTORY_WINDOW = 12
FEATURE_CHANNELS = (
    "b1_u", "b1_m", "b1_l",
    "b2_u", "b2_m", "b2_l",
    "williams3", "ma4", "cci5", "rsi6",
    "price_close",
    "p7_u", "p7_m", "p7_l",
    "p8_u", "p8_m", "p8_l",
)
FEATURE_NAMES = [f"{c}_{stat}" for c in FEATURE_CHANNELS for stat in ("mean", "last", "std", "slope")]


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


def _frame_channels(frame: dict[str, Any]) -> list[float]:
    b1 = _band(frame, "band1")
    b2 = _band(frame, "band2")
    p7 = _band(frame, "price_band7")
    p8 = _band(frame, "price_band8")
    return [
        *[v / 290.0 for v in b1],
        *[v / 290.0 for v in b2],
        _value(frame.get("williams3")) / 290.0,
        _value(frame.get("ma4")) / 290.0,
        _value(frame.get("cci5")) / 290.0,
        _value(frame.get("rsi6")) / 290.0,
        _value(frame.get("price_close")) / 350.0,
        *[v / 350.0 for v in p7],
        *[v / 350.0 for v in p8],
    ]


def extract_feature_vector(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the deployed 68-value temporal feature vector."""
    frames = history[-HISTORY_WINDOW:]
    if not frames:
        frames = [{}]
    arr = np.asarray([_frame_channels(f) for f in frames], dtype=np.float32)
    # Pad the left side so a warming history has the same shape as training.
    if arr.shape[0] < HISTORY_WINDOW:
        pad = np.repeat(arr[:1], HISTORY_WINDOW - arr.shape[0], axis=0)
        arr = np.vstack([pad, arr])
    x = np.arange(HISTORY_WINDOW, dtype=np.float32)
    features: list[float] = []
    for j in range(arr.shape[1]):
        v = arr[:, j]
        slope = float(np.polyfit(x, v, 1)[0]) if HISTORY_WINDOW > 1 else 0.0
        features.extend((float(v.mean()), float(v[-1]), float(v.std()), slope))
    return {
        "vector": features,
        "names": FEATURE_NAMES,
        "n_frames": len(history),
        "completeness": min(1.0, len(history) / float(HISTORY_WINDOW)),
        "bands_ok": bool(history and history[-1].get("band1") and history[-1].get("band2")),
    }
