"""Normalize broker MT5 symbols to AEGIS registry base form.

GBPUSD.r, GBPUSDm, EURUSD# → GBPUSD / EURUSD
"""
from __future__ import annotations

import re

# Common broker suffixes (case-insensitive strip from end)
_SUFFIX_RE = re.compile(
    r"(?:\.r|\.i|\.pro|\.raw|\.ecn|\.std|\.mini|\.c|\.a|\.b|m|i|#|\.)$",
    re.IGNORECASE,
)


def normalize_symbol(symbol: str | None) -> str:
    if not symbol:
        return ""
    s = str(symbol).strip().upper()
    # strip path-like noise
    for sep in (" ", "/"):
        if sep in s:
            s = s.split(sep)[0]
    # iterative suffix peel (e.g. .r then trailing junk)
    for _ in range(3):
        s2 = _SUFFIX_RE.sub("", s)
        if s2 == s:
            break
        s = s2
    # also peel single trailing letter suffix after 6-char FX pair (GBPUSDm)
    if len(s) == 7 and s[:6].isalpha() and s[6] in "MIPRC":
        s = s[:6]
    # metals / indices keep longer names if alphanumeric
    return s


def symbols_match(a: str, b: str) -> bool:
    return normalize_symbol(a) == normalize_symbol(b)
