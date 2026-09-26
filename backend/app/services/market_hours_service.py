"""
Instrument-aware market session guard.

- WEEKEND_BREAK (most FX + metals): closed roughly Fri 21:00 UTC → Sun 22:00 UTC
- ALWAYS_OPEN (crypto, many volatility indices): never blocked by this guard

Brokers differ; this is a safety default, not a legal trading calendar.
Does not replace broker-side rejects on OrderSend.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Explicit 24/7-style prefixes/names (crypto + synthetic/vol indices common on retail platforms)
_ALWAYS_OPEN_PREFIXES = (
    "BTC", "ETH", "XBT", "LTC", "XRP", "SOL", "DOGE", "ADA", "BNB", "DOT", "AVAX",
    "MATIC", "LINK", "UNI", "ATOM", "NEAR", "APT", "ARB", "OP", "SUI", "PEPE",
    "VOL", "VIX", "STEP", "BOOM", "CRASH", "JUMP", "RANGE", "DFX",
)
_ALWAYS_OPEN_CONTAINS = (
    "BITCOIN", "ETHEREUM", "CRYPTO", "VOLATILITY", "STEP INDEX", "BOOM ", "CRASH ",
)
# Metals typically follow FX-like weekends
_METAL_PREFIXES = ("XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER")

# ISO currency codes for 6-letter FX detection
_CCY = {
    "USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "SEK", "NOK", "DKK",
    "HKD", "SGD", "CNH", "CNY", "MXN", "ZAR", "TRY", "PLN", "HUF", "CZK",
}


def normalize_symbol(symbol: str | None) -> str:
    s = (symbol or "").strip().upper()
    # strip common broker suffixes
    for sep in (".", " "):
        if sep in s:
            s = s.split(sep)[0]
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def classify_session_group(symbol: str | None) -> str:
    """
    Returns ALWAYS_OPEN | WEEKEND_BREAK | UNKNOWN.
    UNKNOWN is treated like WEEKEND_BREAK for safety on autonomous FX-style books.
    """
    base = normalize_symbol(symbol)
    if not base:
        return "UNKNOWN"
    for p in _ALWAYS_OPEN_PREFIXES:
        if base.startswith(p):
            return "ALWAYS_OPEN"
    for frag in _ALWAYS_OPEN_CONTAINS:
        if frag.replace(" ", "") in base:
            return "ALWAYS_OPEN"
    # Volatility 75 / 100 style
    if re.match(r"^V(OL)?\d+", base) or re.match(r"^R_\d+", base):
        return "ALWAYS_OPEN"
    for p in _METAL_PREFIXES:
        if base.startswith(p):
            return "WEEKEND_BREAK"
    # Standard 6-letter FX
    if len(base) == 6 and base[:3] in _CCY and base[3:] in _CCY:
        return "WEEKEND_BREAK"
    # 7-char with m suffix etc already stripped
    if len(base) >= 6 and base[:3] in _CCY and base[3:6] in _CCY:
        return "WEEKEND_BREAK"
    return "UNKNOWN"


def fx_style_session_open(now: datetime | None = None) -> bool:
    """
    Approximate interbank FX window:
    - Closed all Saturday UTC
    - Closed Sunday until 22:00 UTC
    - Closed Friday from 21:00 UTC onward
    - Open Mon–Thu always; Fri before 21:00; Sun from 22:00
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    wd = now.weekday()  # Mon=0 … Sun=6
    hour = now.hour
    if wd == 5:  # Saturday
        return False
    if wd == 6:  # Sunday
        return hour >= 22
    if wd == 4:  # Friday
        return hour < 21
    return True  # Mon–Thu


def session_status(symbol: str | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    group = classify_session_group(symbol)
    if group == "ALWAYS_OPEN":
        return {
            "symbol": normalize_symbol(symbol),
            "session_group": group,
            "market_open": True,
            "pause_uploads": False,
            "allow_autonomous": True,
            "reason": "24/7 instrument (crypto/volatility-style) — market-hours guard does not pause",
            "server_time_utc": now.astimezone(timezone.utc).isoformat(),
        }
    open_ = fx_style_session_open(now)
    if group == "UNKNOWN":
        reason = (
            "Unknown asset class — applying FX-style weekend break for safety. "
            "Classify as crypto/vol on server if it should trade 24/7."
        )
    else:
        reason = (
            "FX/metal-style session open"
            if open_
            else "FX/metal weekend break (approx Fri 21:00 UTC – Sun 22:00 UTC) — uploads/autonomous paused"
        )
    return {
        "symbol": normalize_symbol(symbol),
        "session_group": group,
        "market_open": open_,
        "pause_uploads": not open_,
        "allow_autonomous": open_,
        "reason": reason,
        "server_time_utc": now.astimezone(timezone.utc).isoformat(),
    }


def allow_autonomous_for_symbol(symbol: str | None, now: datetime | None = None) -> tuple[bool, dict[str, Any]]:
    st = session_status(symbol, now)
    return bool(st["allow_autonomous"]), st
