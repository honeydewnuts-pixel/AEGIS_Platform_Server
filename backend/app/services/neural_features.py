"""
Phase A — Feature vector extraction from indicator frame history.

Pure functions, no ML framework required. Vectors are stable-length floats
suitable for a small scoring network or future ONNX model.
"""

from __future__ import annotations

from typing import Any

FEATURE_DIM = 24
FEATURE_NAMES = [
    "n_frames",
    "bands_ok",
    "b1_width",
    "b2_width",
    "b1_mid",
    "b2_mid",
    "band_mid_delta",
    "ma4",
    "cci5",
    "rsi6",
    "williams3",
    "ma4_vs_b1m",
    "rsi_vs_b1u",
    "cci_vs_b1m",
    "b2m_vs_b1u",
    "price_close",
    "price_band7_mid",
    "price_band8_mid",
    "d_b1_mid",
    "d_b2_mid",
    "d_ma4",
    "d_rsi6",
    "d_cci5",
    "completeness",
]


def _band(fr: dict[str, Any], key: str) -> dict[str, float] | None:
    v = fr.get(key)
    return v if isinstance(v, dict) and all(k in v for k in ("U", "M", "L")) else None


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _norm_y(y: float | None, scale: float = 400.0) -> float:
    """Map pixel Y roughly to 0..1 (chart coords vary by device)."""
    if y is None:
        return 0.0
    return max(0.0, min(1.0, _f(y) / scale))


def extract_feature_vector(history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a fixed-length feature vector from history (oldest → newest).
    Missing indicators → zeros + lower completeness.
    """
    n = len(history)
    cur = history[-1] if n else {}
    prev = history[-2] if n >= 2 else {}

    b1 = _band(cur, "band1")
    b2 = _band(cur, "band2")
    pb1 = _band(prev, "band1")
    pb2 = _band(prev, "band2")
    bands_ok = 1.0 if (b1 and b2) else 0.0

    b1_width = _norm_y((b1["L"] - b1["U"]) if b1 else 0.0)
    b2_width = _norm_y((b2["L"] - b2["U"]) if b2 else 0.0)
    b1_mid = _norm_y(b1["M"] if b1 else None)
    b2_mid = _norm_y(b2["M"] if b2 else None)
    band_mid_delta = b2_mid - b1_mid

    ma4 = _norm_y(cur.get("ma4"))
    cci5 = _norm_y(cur.get("cci5"))
    rsi6 = _norm_y(cur.get("rsi6"))
    williams3 = _norm_y(cur.get("williams3"))

    ma4_vs_b1m = ma4 - b1_mid
    rsi_vs_b1u = rsi6 - _norm_y(b1["U"] if b1 else None)
    cci_vs_b1m = cci5 - b1_mid
    b2m_vs_b1u = b2_mid - _norm_y(b1["U"] if b1 else None)

    price_close = _norm_y(cur.get("price_close"))
    p7 = _band(cur, "price_band7")
    p8 = _band(cur, "price_band8")
    price_band7_mid = _norm_y(p7["M"] if p7 else None)
    price_band8_mid = _norm_y(p8["M"] if p8 else None)

    d_b1_mid = b1_mid - _norm_y(pb1["M"] if pb1 else None)
    d_b2_mid = b2_mid - _norm_y(pb2["M"] if pb2 else None)
    d_ma4 = ma4 - _norm_y(prev.get("ma4"))
    d_rsi6 = rsi6 - _norm_y(prev.get("rsi6"))
    d_cci5 = cci5 - _norm_y(prev.get("cci5"))

    present = 0
    keys = ("band1", "band2", "ma4", "cci5", "rsi6", "williams3")
    for k in keys:
        v = cur.get(k)
        if v is None:
            continue
        if isinstance(v, dict) or isinstance(v, (int, float)):
            present += 1
    completeness = present / float(len(keys))

    vec = [
        min(1.0, n / 12.0),
        bands_ok,
        b1_width,
        b2_width,
        b1_mid,
        b2_mid,
        band_mid_delta,
        ma4,
        cci5,
        rsi6,
        williams3,
        ma4_vs_b1m,
        rsi_vs_b1u,
        cci_vs_b1m,
        b2m_vs_b1u,
        price_close,
        price_band7_mid,
        price_band8_mid,
        d_b1_mid,
        d_b2_mid,
        d_ma4,
        d_rsi6,
        d_cci5,
        completeness,
    ]
    assert len(vec) == FEATURE_DIM
    return {
        "vector": vec,
        "names": FEATURE_NAMES,
        "n_frames": n,
        "bands_ok": bool(bands_ok),
        "completeness": completeness,
    }
