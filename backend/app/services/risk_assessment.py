"""
AEGIS autonomous per-trade risk assessment.

Layers (must stay distinct):
  A) Client risk tolerance — overall preference ceiling (configured by client).
  B) AEGIS per-trade risk % — calculated here for each proposed trade.
  C) Portfolio / drawdown protection — enforced outside this module.

This is NOT a machine-learning optimizer. Rules are explicit and auditable.
The seven research percentages (0.05%…5%) are NOT client settings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# Platform safety: no single trade may exceed this fraction of client tolerance.
# Example: tolerance 10% → base per-trade ceiling starts at 10% / BASE_DIVISOR.
BASE_DIVISOR = 10.0

# Absolute platform cap on any single trade risk % of equity (independent of client).
PLATFORM_MAX_TRADE_RISK_PCT = 2.0

# Absolute platform floor below which we reject rather than size noise.
PLATFORM_MIN_TRADE_RISK_PCT = 0.05

# When stop distance / ATR exceeds this, scale risk down (wide stop → smaller % risk).
ATR_STOP_SOFT_CAP = 2.0  # stop_distance / atr14
ATR_STOP_HARD_CAP = 4.0  # beyond this → reject or min risk

# Drawdown vs peak: as dd approaches client tolerance budget, scale trade risk down.
DRAWDOWN_SOFT_START = 0.25  # start scaling when used_dd_budget >= 25%
DRAWDOWN_HARD = 1.0         # at 100% of tolerance budget used, trade risk → 0


@dataclass
class RiskAssessment:
    allow: bool
    per_trade_risk_pct: float
    reason: str
    client_tolerance_pct: float
    rules_applied: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def assess_per_trade_risk(
    *,
    client_tolerance_pct: float,
    equity: float,
    open_risk_usd: float = 0.0,
    peak_equity: float | None = None,
    max_concurrent_slots: int = 1,
    open_positions: int = 0,
    stop_distance: float | None = None,
    atr14: float | None = None,
    trading_halted: bool = False,
) -> RiskAssessment:
    """
    Calculate AEGIS-controlled per-trade risk percentage.

    Documented rules (applied in order):

    R0  If halted or equity invalid → reject.
    R1  Base risk % = client_tolerance_pct / BASE_DIVISOR
        (tolerance is a ceiling envelope, not the per-trade %).
    R2  Cap base by PLATFORM_MAX_TRADE_RISK_PCT.
    R3  Slot pressure: multiply by max(0.25, free_slots / max_slots)
        so more open positions → smaller new-trade risk.
    R4  Portfolio utilization: if open_risk / (equity * tolerance/100) is high,
        scale down linearly toward 0 as utilization → 1.
    R5  Drawdown: if (peak - equity) / (equity * tolerance/100) rises,
        scale down between DRAWDOWN_SOFT_START and DRAWDOWN_HARD.
    R6  Volatility / stop width: if stop_distance and atr14 available,
        scale down when stop > ATR_STOP_SOFT_CAP * atr; reject if > HARD_CAP.
    R7  Floor: if result < PLATFORM_MIN_TRADE_RISK_PCT → reject
        (do not force a tiny untradeable risk).
    R8  Final per-trade risk never exceeds client_tolerance_pct.

    Returns RiskAssessment with explicit rules_applied for audit.
    """
    rules: list[str] = []
    details: dict[str, Any] = {}

    if trading_halted:
        return RiskAssessment(False, 0.0, "trading_halted", float(client_tolerance_pct), ["R0"], details)
    if equity is None or float(equity) <= 0:
        return RiskAssessment(False, 0.0, "equity_required", float(client_tolerance_pct or 0), ["R0"], details)
    tol = float(client_tolerance_pct or 0)
    if tol <= 0:
        return RiskAssessment(False, 0.0, "invalid_client_tolerance", tol, ["R0"], details)

    equity_f = float(equity)
    # R1
    risk_pct = tol / BASE_DIVISOR
    rules.append(f"R1_base=tolerance/{BASE_DIVISOR}→{risk_pct:.6f}")
    details["base_risk_pct"] = risk_pct

    # R2
    if risk_pct > PLATFORM_MAX_TRADE_RISK_PCT:
        risk_pct = PLATFORM_MAX_TRADE_RISK_PCT
        rules.append(f"R2_platform_cap→{risk_pct:.6f}")

    # R3 slot pressure
    max_slots = max(1, int(max_concurrent_slots or 1))
    open_n = max(0, int(open_positions or 0))
    free = max(0, max_slots - open_n)
    if free <= 0:
        return RiskAssessment(
            False, 0.0, "no_free_risk_slots", tol, rules + ["R3_no_free_slots"], details
        )
    slot_factor = max(0.25, free / max_slots)
    risk_pct *= slot_factor
    rules.append(f"R3_slot_factor={slot_factor:.4f}→{risk_pct:.6f}")
    details["free_slots"] = free
    details["max_slots"] = max_slots

    # R4 portfolio utilization of tolerance budget
    tol_budget = equity_f * tol / 100.0
    details["tolerance_budget_usd"] = tol_budget
    util = 0.0
    if tol_budget > 0:
        util = min(1.0, max(0.0, float(open_risk_usd or 0.0) / tol_budget))
    util_factor = max(0.0, 1.0 - util)
    risk_pct *= util_factor
    rules.append(f"R4_util={util:.4f} factor={util_factor:.4f}→{risk_pct:.6f}")
    details["open_risk_utilization"] = util

    # R5 drawdown vs peak relative to tolerance budget
    peak = float(peak_equity) if peak_equity is not None else equity_f
    dd = max(0.0, peak - equity_f)
    dd_ratio = (dd / tol_budget) if tol_budget > 0 else 0.0
    details["drawdown_usd"] = dd
    details["drawdown_budget_ratio"] = dd_ratio
    if dd_ratio >= DRAWDOWN_HARD:
        return RiskAssessment(
            False, 0.0, "drawdown_limit_reached", tol, rules + ["R5_hard_dd"], details
        )
    if dd_ratio > DRAWDOWN_SOFT_START:
        # linear scale from 1.0 at soft start to 0 at hard
        span = DRAWDOWN_HARD - DRAWDOWN_SOFT_START
        dd_factor = max(0.0, 1.0 - (dd_ratio - DRAWDOWN_SOFT_START) / span)
        risk_pct *= dd_factor
        rules.append(f"R5_dd_factor={dd_factor:.4f}→{risk_pct:.6f}")
    else:
        rules.append("R5_dd_ok")

    # R6 stop vs ATR
    if stop_distance is not None and atr14 is not None:
        try:
            sd = float(stop_distance)
            atr = float(atr14)
            if atr > 0 and sd > 0:
                ratio = sd / atr
                details["stop_atr_ratio"] = ratio
                if ratio > ATR_STOP_HARD_CAP:
                    return RiskAssessment(
                        False, 0.0, "stop_too_wide_vs_atr", tol, rules + ["R6_hard_atr"], details
                    )
                if ratio > ATR_STOP_SOFT_CAP:
                    # scale from 1 at soft to 0 at hard
                    span = ATR_STOP_HARD_CAP - ATR_STOP_SOFT_CAP
                    atr_factor = max(0.0, 1.0 - (ratio - ATR_STOP_SOFT_CAP) / span)
                    risk_pct *= atr_factor
                    rules.append(f"R6_atr_factor={atr_factor:.4f}→{risk_pct:.6f}")
                else:
                    rules.append("R6_atr_ok")
            else:
                rules.append("R6_atr_skipped_invalid")
        except (TypeError, ValueError):
            rules.append("R6_atr_skipped_error")
    else:
        rules.append("R6_atr_not_provided")

    # R8 never exceed client tolerance
    if risk_pct > tol:
        risk_pct = tol
        rules.append("R8_cap_at_client_tolerance")

    # R7 floor
    if risk_pct < PLATFORM_MIN_TRADE_RISK_PCT:
        return RiskAssessment(
            False,
            0.0,
            "per_trade_risk_below_platform_floor",
            tol,
            rules + [f"R7_below_floor_{PLATFORM_MIN_TRADE_RISK_PCT}"],
            details,
        )

    rules.append(f"final_per_trade_risk_pct={risk_pct:.6f}")
    details["per_trade_risk_pct"] = risk_pct
    return RiskAssessment(True, float(risk_pct), "ok", tol, rules, details)
