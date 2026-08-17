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
    },
    "starter": {
        "label": "Starter",
        "max_devices": 1,
        "max_trades_per_day": 15,
        "live_trading": True,
        "price_usd": 100,
        "price_hint": "$100 / period · 1 phone · 15 trades/day",
    },
    "pro": {
        "label": "Pro",
        "max_devices": 1,
        "max_trades_per_day": 50,
        "live_trading": True,
        "price_usd": 500,
        "price_hint": "$500 / period · 1 phone · 50 trades/day",
    },
    "business": {
        "label": "Business",
        "max_devices": 3,
        "max_trades_per_day": 200,
        "live_trading": True,
        "price_usd": 1000,
        "price_hint": "$1,000 / period · 3 phones · 200 trades/day",
    },
    "enterprise": {
        "label": "Enterprise",
        "max_devices": 10,
        "max_trades_per_day": 0,
        "live_trading": True,
        "price_usd": 0,  # custom quote
        "price_hint": "Custom · 10 phones · unlimited trades",
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
