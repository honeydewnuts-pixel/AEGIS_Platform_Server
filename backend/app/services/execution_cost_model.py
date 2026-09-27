"""
Instrument-aware execution cost model (V53.6 remediation).

Principles:
- Historical reproduction may use legacy fixed 0.085R (research only).
- Operational historical / demo / live must NOT apply that universal deduction.
- Bid/Ask fields already encode spread when entry=AskOpen and exit uses Bid.
- Never invent commission, slippage, or swap; report unavailable when unknown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.rulebooks.evaluators.common import (
    COST_MODE_BID_ASK,
    COST_MODE_CONFIGURED,
    COST_MODE_LEGACY,
    LEGACY_FIXED_COST_R,
)

AccountType = Literal["historical_reproduction", "historical_operational", "demo", "live"]


@dataclass(frozen=True)
class CostModelConfig:
    version: str
    account_type: AccountType
    instrument: str
    cost_mode: str
    spread_source: str
    commission_model: str
    slippage_model: str
    swap_model: str
    fixed_cost_r: float | None
    commission_r: float
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def cost_config_for(
    instrument: str,
    account_type: AccountType = "historical_operational",
    *,
    broker_id: str | None = None,
) -> CostModelConfig:
    """
    Build an explicit cost configuration.

    historical_reproduction → legacy_fixed_r (0.085R) for exact V31/V35 metrics.
    historical_operational / demo / live → bid_ask_only; no fabricated R costs.
    """
    inst = (instrument or "").upper().split(".")[0]
    if account_type == "historical_reproduction":
        return CostModelConfig(
            version="cost_model_v1_legacy",
            account_type=account_type,
            instrument=inst,
            cost_mode=COST_MODE_LEGACY,
            spread_source="embedded_in_ask_entry_bid_exit",
            commission_model=f"legacy_fixed_{LEGACY_FIXED_COST_R}R",
            slippage_model="none_explicit",
            swap_model="not_modeled",
            fixed_cost_r=LEGACY_FIXED_COST_R,
            commission_r=0.0,
            notes=(
                "Research reproduction only. Matches frozen V31/V35 cash metrics. "
                "Not for demo or live P&L attribution."
            ),
        )
    # Operational: no universal fixed R
    return CostModelConfig(
        version="cost_model_v1_operational",
        account_type=account_type,
        instrument=inst,
        cost_mode=COST_MODE_BID_ASK,
        spread_source="historical_bid_ask" if account_type.startswith("historical") else "broker_fill_prices",
        commission_model="unavailable_not_fabricated",
        slippage_model="unavailable_not_fabricated",
        swap_model="unavailable_not_fabricated",
        fixed_cost_r=None,
        commission_r=0.0,
        notes=(
            f"Operational cost model for {account_type}. "
            "Uses Bid/Ask (or broker fills) only; does not apply 0.085R. "
            f"broker={broker_id or 'unspecified'}."
        ),
    )


def assert_no_legacy_cost_on_operational(account_type: AccountType) -> None:
    cfg = cost_config_for("ANY", account_type)
    if account_type != "historical_reproduction" and cfg.cost_mode == COST_MODE_LEGACY:
        raise AssertionError("Operational path must not use legacy_fixed_r")
    if account_type != "historical_reproduction" and cfg.fixed_cost_r:
        raise AssertionError("Operational path must not set fixed_cost_r")


__all__ = [
    "CostModelConfig",
    "cost_config_for",
    "assert_no_legacy_cost_on_operational",
    "COST_MODE_LEGACY",
    "COST_MODE_BID_ASK",
    "COST_MODE_CONFIGURED",
    "LEGACY_FIXED_COST_R",
]
