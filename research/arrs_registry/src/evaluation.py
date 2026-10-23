"""Execution-aware evaluation interfaces — no order submission."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionConvention:
    """Class A Bid/Ask conventions."""
    long_entry: str = "ask"
    long_exit: str = "bid"
    short_entry: str = "bid"
    short_exit: str = "ask"
    signal_bar: str = "completed_only"
    entry_timing: str = "next_bar_open"
    # Research must not use signal-bar close as fill


@dataclass
class TradeManagementSpec:
    """Required before trade-level qualification."""
    entry_trigger: str
    initial_stop: str | None
    exit_rule: str | None
    target: str | None = None
    max_hold_bars: int | None = None
    gap_policy: str = "conservative_unfavorable"
    defined: bool = True

    @staticmethod
    def undefined() -> "TradeManagementSpec":
        return TradeManagementSpec(
            entry_trigger="UNSPECIFIED",
            initial_stop=None,
            exit_rule=None,
            defined=False,
        )


@dataclass
class GateResult:
    name: str
    status: str  # PASS FAIL INSUFFICIENT_EVIDENCE NOT_RUN
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def require_trade_management(tm: TradeManagementSpec) -> GateResult:
    if not tm.defined or not tm.initial_stop or not tm.exit_rule:
        return GateResult(
            "trade_management_defined",
            "FAIL",
            "Trade-level qualification requires explicit stop and exit; association-only is insufficient",
        )
    return GateResult("trade_management_defined", "PASS")


def hard_materiality_gate(
    *, abs_mean_bps: float | None, hit_rate: float | None, n: int | None,
    min_bps: float = 10.0, min_hit: float = 0.55, min_n: int = 200,
) -> GateResult:
    if abs_mean_bps is None or hit_rate is None or n is None:
        return GateResult("hard_materiality", "INSUFFICIENT_EVIDENCE", "missing metrics")
    if n < min_n:
        return GateResult("hard_materiality", "INSUFFICIENT_EVIDENCE", f"n={n}<{min_n}")
    if abs_mean_bps > min_bps and hit_rate > min_hit:
        return GateResult("hard_materiality", "PASS", metrics={
            "abs_mean_bps": abs_mean_bps, "hit_rate": hit_rate, "n": n
        })
    return GateResult("hard_materiality", "FAIL", metrics={
        "abs_mean_bps": abs_mean_bps, "hit_rate": hit_rate, "n": n
    })


def aggregate_gates(results: list[GateResult]) -> str:
    """Absence of failure is not a pass — need explicit PASS and no FAIL."""
    if any(r.status == "FAIL" for r in results):
        return "FAIL"
    if any(r.status == "INSUFFICIENT_EVIDENCE" for r in results):
        return "INSUFFICIENT_EVIDENCE"
    if any(r.status == "NOT_RUN" for r in results):
        return "NOT_RUN"
    if results and all(r.status == "PASS" for r in results):
        return "PASS"
    return "INSUFFICIENT_EVIDENCE"
