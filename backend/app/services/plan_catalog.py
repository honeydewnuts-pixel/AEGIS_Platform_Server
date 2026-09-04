"""
Commercial subscription tiers for AEGIS (global, USD).

max_trades_per_day: 0 means unlimited.
live_trading: false restricts to analysis / demo-style use.
"""

from __future__ import annotations

from typing import Any

# Amounts in USD (major units). Payment adapters convert to provider minor units.
PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "demo": {
        "label": "Demo / Trial",
        "max_devices": 1,
        "max_trades_per_day": 5,
        "live_trading": False,
        "price_usd": 0,
        "price_hint": "Free 14-day trial",
        "base_lot": 0.01,
        "max_lot": 0.01,
    },
    "starter": {
        "label": "Starter",
        "max_devices": 1,
        "max_trades_per_day": 15,
        "live_trading": True,
        "price_usd": 100,
        "price_hint": "$100 / period · 1 phone · 15 trades/day",
        "base_lot": 0.10,
        "max_lot": 0.20,
    },
    "pro": {
        "label": "Pro",
        "max_devices": 1,
        "max_trades_per_day": 50,
        "live_trading": True,
        "price_usd": 500,
        "price_hint": "$500 / period · 1 phone · 50 trades/day",
        "base_lot": 0.50,
        "max_lot": 0.50,
    },
    "business": {
        "label": "Business",
        "max_devices": 3,
        "max_trades_per_day": 200,
        "live_trading": True,
        "price_usd": 1000,
        "price_hint": "$1,000 / period · 3 phones · 200 trades/day",
        "base_lot": 0.50,
        "max_lot": 1.00,
    },
    "enterprise": {
        "label": "Enterprise",
        "max_devices": 10,
        "max_trades_per_day": 0,
        "live_trading": True,
        "price_usd": 0,  # custom quote
        "price_hint": "Custom · 10 phones · unlimited trades",
        "base_lot": 1.00,
        "max_lot": 5.00,
    },
}


def resolve_plan(plan_code: str) -> dict[str, Any]:
    code = (plan_code or "starter").lower().strip()
    if code in ("live",):
        code = "starter"
    base = PLAN_CATALOG.get(code, PLAN_CATALOG["starter"])
    resolved_code = code if code in PLAN_CATALOG else "starter"
    return {**base, "code": resolved_code}


def plan_price_usd(plan_code: str) -> float:
    return float(resolve_plan(plan_code).get("price_usd") or 0)


def mode_for_plan(plan_code: str) -> str:
    """DEMO_VERIFY / LIVE_TRADE is the explicit, client-facing vocabulary
    for what's really just `live_trading` on the resolved plan - kept as a
    thin derived mapping rather than a second stored field, so it can never
    drift out of sync with the plan catalog above. DEMO_VERIFY covers the
    "let a prospect see real autonomous execution before paying" case
    (currently just the demo plan; any future plan with live_trading=False
    would also read as DEMO_VERIFY automatically)."""
    return "LIVE_TRADE" if resolve_plan(plan_code).get("live_trading") else "DEMO_VERIFY"


# Trade Copier add-ons (require an active paid AEGIS plan: starter+)
ADDON_CATALOG: dict[str, dict[str, Any]] = {
    "copier_3": {
        "label": "Trade Copier — 3 slaves",
        "max_slaves": 3,
        "price_usd": 49,
        "price_hint": "$49 / month · mirror master to up to 3 accounts",
    },
    "copier_10": {
        "label": "Trade Copier — 10 slaves",
        "max_slaves": 10,
        "price_usd": 129,
        "price_hint": "$129 / month · up to 10 slave accounts",
    },
    "copier_25": {
        "label": "Trade Copier — 25 slaves",
        "max_slaves": 25,
        "price_usd": 249,
        "price_hint": "$249 / month · up to 25 slave accounts",
    },
}


def resolve_addon(code: str) -> dict[str, Any]:
    c = (code or "copier_3").lower().strip()
    base = ADDON_CATALOG.get(c, ADDON_CATALOG["copier_3"])
    return {**base, "code": c if c in ADDON_CATALOG else "copier_3"}


def addon_price_usd(code: str) -> float:
    return float(resolve_addon(code).get("price_usd") or 0)


def get_base_lot(plan_code: str) -> float:
    """Default lot size for the plan (before risk preset multiplier)."""
    return float(resolve_plan(plan_code).get("base_lot") or 0.01)


def get_max_lot(plan_code: str) -> float:
    """Hard cap on lot size for the plan. Server never exceeds this."""
    return float(resolve_plan(plan_code).get("max_lot") or 0.01)
