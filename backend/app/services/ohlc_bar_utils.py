"""Closed-bar isolation utilities for strategy evaluation."""
from __future__ import annotations
from typing import Any


def closed_bars_only(
    bars: list[dict[str, Any]] | None,
    *,
    closed_bar: dict[str, Any] | None = None,
    current_bar: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not bars:
        return []
    out = [b for b in bars if isinstance(b, dict)]
    if not out:
        return []

    def _t(b: dict) -> int:
        try:
            return int(b.get("time") or b.get("bar_time") or 0)
        except (TypeError, ValueError):
            return 0

    cur_t = _t(current_bar) if isinstance(current_bar, dict) else 0
    if cur_t and _t(out[-1]) == cur_t:
        out = out[:-1]

    if isinstance(closed_bar, dict) and closed_bar:
        ct = _t(closed_bar)
        if ct and out and _t(out[-1]) != ct:
            if _t(out[-1]) < ct:
                out = list(out) + [dict(closed_bar)]
        elif ct and not out:
            out = [dict(closed_bar)]
    return out
