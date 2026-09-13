"""AEGIS Market Observation Package — validation + acquisition states (V47.2)."""

from __future__ import annotations

from typing import Any
import time

# Explicit acquisition states (mobile + server share vocabulary)
WAITING_FOR_CAPTURE = "WAITING_FOR_CAPTURE"
WAITING_FOR_OHLC = "WAITING_FOR_OHLC"
CAPTURE_COMPLETE = "CAPTURE_COMPLETE"
INSTRUMENT_BLOCKED = "INSTRUMENT_BLOCKED"


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
        "ohlc_valid": ohlc is not None and all(
            k in (ohlc or {}) for k in ("open", "high", "low", "close")
        ),
        "timestamp_aligned": False,
        "sync_skew_ms": None,
    }
    if device_ts_ms is not None and candle_ts_ms is not None:
        skew = abs(int(device_ts_ms) - int(candle_ts_ms))
        flags["sync_skew_ms"] = skew
        flags["timestamp_aligned"] = skew <= 60_000
    elif candle_ts_ms is not None:
        flags["timestamp_aligned"] = True
        flags["sync_skew_ms"] = 0
    return flags


def derive_acquisition_state(
    *,
    obs_flags: dict[str, Any],
    router_state: str | None,
    rule_name: str | None,
) -> dict[str, Any]:
    """
    Map validation + router outcome to an explicit acquisition state.

    WAITING_FOR_OHLC  — screenshot accepted, instrument OK, OHLC not yet synced
    CAPTURE_COMPLETE  — screenshot + OHLC (+ optional time align) present
    INSTRUMENT_BLOCKED — router refused trading (e.g. TRADING_DISABLED)
    """
    checklist = {
        "screenshot": bool(obs_flags.get("screenshot_valid")),
        "ohlc": bool(obs_flags.get("ohlc_valid")),
        "timestamp": bool(obs_flags.get("timestamp_aligned")) or bool(obs_flags.get("candle_ts_ms")),
        "symbol": bool(obs_flags.get("instrument_valid")),
        "m5_sync": bool(obs_flags.get("timestamp_aligned")),
    }

    blocked_states = {
        "TRADING_DISABLED",
        "NO_QUALIFIED_RULEBOOK",
        "UNKNOWN_INSTRUMENT",
        "UNKNOWN_TIMEFRAME",
        "INSUFFICIENT_SPREAD_DATA",
        "RULEBOOK_INTEGRITY_FAILURE",
        "MODEL_LINEAGE_FAILURE",
        "PRODUCTION_AUTHORIZATION_REQUIRED",
    }
    rs = (router_state or "").upper()
    rn = (rule_name or "").lower()

    if rs in blocked_states or rn in {
        "trading_disabled",
        "no_qualified_rulebook",
        "unknown_instrument",
        "instrument_unspecified",
    }:
        state = INSTRUMENT_BLOCKED
        summary = "Instrument/router blocked — observation stored but not tradeable."
    elif checklist["screenshot"] and checklist["ohlc"] and checklist["symbol"]:
        state = CAPTURE_COMPLETE
        summary = "Screenshot + OHLC + symbol synchronized."
    elif checklist["screenshot"] and checklist["symbol"] and not checklist["ohlc"]:
        state = WAITING_FOR_OHLC
        summary = (
            "Screenshot accepted; synchronized MT5 OHLC not yet available "
            "(worker offline or chart not ready). Fail-safe — not forced through."
        )
    elif checklist["screenshot"]:
        state = WAITING_FOR_OHLC
        summary = "Screenshot accepted; set Trade pair in Settings and/or connect MT5 worker for OHLC."
    else:
        state = WAITING_FOR_OHLC
        summary = "Incomplete observation package."

    return {
        "acquisition_state": state,
        "checklist": checklist,
        "summary": summary,
    }


def confidence_presentation(
    *,
    acquisition_state: str | None,
    router_state: str | None,
    rule_name: str | None,
    confidence: float | None,
) -> dict:
    """Avoid showing 0% when no evaluation has occurred."""
    state = (acquisition_state or "").upper()
    rs = (router_state or "").upper()
    rn = (rule_name or "").lower()

    not_evaluated = state in {
        "WAITING_FOR_OHLC",
        "WAITING_FOR_CAPTURE",
        "INSTRUMENT_BLOCKED",
    } or rn in {
        "v40_research_awaiting_ohlc",
        "instrument_unspecified",
        "trading_disabled",
        "no_qualified_rulebook",
        "unknown_instrument",
        "production_authorization_required",
    } or rs in {
        "TRADING_DISABLED",
        "NO_QUALIFIED_RULEBOOK",
        "UNKNOWN_INSTRUMENT",
        "PRODUCTION_AUTHORIZATION_REQUIRED",
    }

    if not_evaluated:
        reason = {
            "WAITING_FOR_OHLC": "WAITING FOR SYNCHRONIZED OHLC",
            "WAITING_FOR_CAPTURE": "WAITING FOR NEXT CAPTURE",
            "INSTRUMENT_BLOCKED": "NO ELIGIBLE RULEBOOK / ROUTER BLOCKED",
        }.get(state, "NOT EVALUATED")
        if rn == "v40_research_awaiting_ohlc":
            reason = "WAITING FOR SYNCHRONIZED OHLC"
        return {
            "confidence_available": False,
            "confidence_display": "N/A",
            "confidence_status": reason,
            # Keep numeric field for backward-compatible clients; UI should use display
            "confidence": 0.0,
        }

    c = float(confidence or 0.0)
    return {
        "confidence_available": True,
        "confidence_display": f"{c * 100:.0f}%",
        "confidence_status": "EVALUATED",
        "confidence": c,
    }
