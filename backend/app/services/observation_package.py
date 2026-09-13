"""AEGIS Market Observation Package — validation helpers (V47.1)."""

from __future__ import annotations

from typing import Any
import time


def floor_to_m5_ms(ts_ms: int) -> int:
    """Floor device/candle time to M5 boundary (5 * 60 * 1000 ms)."""
    step = 5 * 60 * 1000
    return (int(ts_ms) // step) * step


def next_m5_boundary_ms(after_ms: int | None = None) -> int:
    step = 5 * 60 * 1000
    now = int(after_ms if after_ms is not None else time.time() * 1000)
    return ((now // step) + 1) * step


def build_ohlc_from_form(
    *,
    open_: str | None,
    high: str | None,
    low: str | None,
    close: str | None,
    volume: str | None = None,
    bid: str | None = None,
    ask: str | None = None,
    candle_ts_ms: int | None = None,
) -> dict[str, Any] | None:
    """Build OHLC dict from optional multipart form fields. None if incomplete."""
    try:
        if not (open_ and high and low and close):
            return None
        o = float(open_)
        h = float(high)
        l = float(low)
        c = float(close)
        if min(o, h, l, c) <= 0:
            return None
        out: dict[str, Any] = {
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "source": "client_observation",
        }
        if volume not in (None, ""):
            out["volume"] = float(volume)
        if bid not in (None, ""):
            out["bid"] = float(bid)
        if ask not in (None, ""):
            out["ask"] = float(ask)
            if "bid" in out:
                out["spread"] = abs(out["ask"] - out["bid"])
        if candle_ts_ms is not None:
            out["candle_ts_ms"] = int(candle_ts_ms)
            out["candle_ts_m5_ms"] = floor_to_m5_ms(int(candle_ts_ms))
        return out
    except (TypeError, ValueError):
        return None


def validate_observation(
    *,
    instrument: str,
    timeframe: str,
    screenshot_bytes: bytes,
    ohlc: dict[str, Any] | None,
    device_ts_ms: int | None,
    candle_ts_ms: int | None,
) -> dict[str, Any]:
    """Return validation flags for the observation package."""
    flags = {
        "screenshot_valid": bool(screenshot_bytes) and len(screenshot_bytes) > 100,
        "instrument_valid": bool((instrument or "").strip()),
        "timeframe_valid": bool((timeframe or "").strip()),
        "ohlc_valid": ohlc is not None and all(k in ohlc for k in ("open", "high", "low", "close")),
        "timestamp_aligned": False,
        "sync_skew_ms": None,
    }
    if device_ts_ms is not None and candle_ts_ms is not None:
        skew = abs(int(device_ts_ms) - int(candle_ts_ms))
        flags["sync_skew_ms"] = skew
        flags["timestamp_aligned"] = skew <= 60_000  # within 1 minute
    elif candle_ts_ms is not None:
        flags["timestamp_aligned"] = True
        flags["sync_skew_ms"] = 0
    return flags
