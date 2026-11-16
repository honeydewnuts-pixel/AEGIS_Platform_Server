"""Shared fail-closed operational authorization for Executor delivery.

production_authorized and execution_authorized remain false unless explicitly
set on a durable queue row AND the operational registry association is valid.
This module never elevates authorization flags.
"""
from __future__ import annotations

from typing import Any


def _norm_sym(symbol: str) -> str:
    return (symbol or "").strip().upper().split(".")[0].split("#")[0]


def evaluate_symbol_authorization(
    registry: Any,
    symbol: str,
    *,
    rulebook_id: str | None = None,
    methodology: str | None = None,
    timeframe: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Fail-closed instrument (+ optional rulebook association) check.

    Returns (ok, reason, instrument_row_or_none).
    """
    if registry is None:
        return False, "registry_unavailable_fail_closed", None
    sym = _norm_sym(symbol)
    if not sym:
        return False, "empty_symbol", None
    try:
        rows = registry.list_instruments(tradeable_only=False)
    except Exception:
        return False, "registry_error", None

    match = next(
        (r for r in rows if str(r.get("instrument") or "").upper() == sym),
        None,
    )
    if match is None:
        return False, "unknown_instrument", None
    if match.get("good") is False or not match.get("tradeable"):
        return False, f"not_authorized:{match.get('router_status')}", match

    # If a rulebook identity is known, require full association
    rid = (rulebook_id or "").strip() or None
    if rid:
        try:
            rb = registry.get_rulebook(rid)
        except Exception:
            return False, "registry_error", match
        if not rb:
            return False, "rulebook_not_in_operational_registry", match
        rb_inst = str(rb.get("instrument") or "").upper()
        rb_tf = str(rb.get("timeframe") or "").upper()
        if rb_inst and rb_inst != sym:
            return False, "rulebook_instrument_mismatch", match
        inst_tf = str(match.get("timeframe") or "").upper()
        if timeframe:
            tf = str(timeframe).upper()
            if rb_tf and rb_tf != tf:
                return False, "rulebook_timeframe_mismatch", match
            if inst_tf and inst_tf != tf:
                return False, "instrument_timeframe_mismatch", match
        elif rb_tf and inst_tf and rb_tf != inst_tf:
            return False, "timeframe_mismatch", match
        eligible = [str(x) for x in (match.get("eligible_rulebooks") or [])]
        if rid not in eligible:
            return False, "rulebook_not_in_instrument_eligible_list", match

    # methodology research markers never authorize by themselves
    meth = (methodology or "").strip().lower()
    if meth in {"research", "research_only", "archived", "v31", "v35", "v53.6", "v53_6"}:
        # still require tradeable instrument; research label alone is not enough
        # and does not grant execution — callers must still check queue flags
        pass

    return True, "ok", match


def is_queue_row_execution_authorized(row: dict[str, Any] | None) -> bool:
    """Durable-queue row must carry an explicit execution grant.

    production_authorized OR controlled_demo_authorized may unlock delivery;
    neither is inferred from registry tradeability alone.
    """
    if not row:
        return False
    if row.get("production_authorized") is True:
        return True
    if row.get("controlled_demo_authorized") is True:
        return True
    return False


def filter_actionable_signal(
    registry: Any,
    row: dict[str, Any],
) -> tuple[bool, str]:
    """Combined gate: registry association + explicit queue authorization flags."""
    if not is_queue_row_execution_authorized(row):
        return False, "queue_row_not_execution_authorized"
    ok, reason, _ = evaluate_symbol_authorization(
        registry,
        str(row.get("symbol") or ""),
        rulebook_id=row.get("rulebook_id") or row.get("rule_name"),
        methodology=row.get("methodology"),
        timeframe=row.get("timeframe"),
    )
    if not ok:
        return False, reason
    return True, "ok"
