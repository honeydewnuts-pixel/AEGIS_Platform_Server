"""Live Universal Router acceptance probes (read-only, fail-closed)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.universal_router import UniversalRouter

router = APIRouter(prefix="/api/router", tags=["UniversalRouter"])

# Canonical acceptance matrix for V40 / V46 baseline
ACCEPTANCE_MATRIX = [
    ("GBPUSD", "M5", "ROUTABLE_RESEARCH", False),
    ("AUDUSD", "M5", "ROUTABLE_RESEARCH", False),
    ("USDCHF", "M5", "ROUTABLE_RESEARCH", False),
    ("NZDUSD", "M5", "ROUTABLE_RESEARCH", False),
    ("EURUSD", "M5", "TRADING_DISABLED", False),
    ("USDJPY", "M5", "TRADING_DISABLED", False),
    ("EURJPY", "M5", "TRADING_DISABLED", False),
    ("GBPJPY", "M5", "TRADING_DISABLED", False),
]


def _router() -> UniversalRouter:
    return UniversalRouter()


@router.get("/resolve")
async def resolve_route(
    instrument: str = Query(...),
    timeframe: str = Query("M5"),
    production_requested: bool = Query(False),
    spread_available: bool = Query(True),
):
    decision = _router().resolve(
        instrument,
        timeframe,
        production_requested=production_requested,
        spread_available=spread_available,
    )
    return decision.to_dict()


@router.get("/acceptance")
async def run_acceptance():
    """Run the full V40 matrix + production authorization refusal checks."""
    ur = _router()
    results = []
    all_ok = True
    for instrument, timeframe, expected, prod in ACCEPTANCE_MATRIX:
        d = ur.resolve(instrument, timeframe, production_requested=prod)
        ok = d.state.value == expected
        if not ok:
            all_ok = False
        results.append(
            {
                "instrument": instrument,
                "timeframe": timeframe,
                "expected": expected,
                "actual": d.state.value,
                "ok": ok,
                "rulebook_ids": list(d.rulebook_ids),
                "reason": d.reason,
            }
        )

    # Production must be refused for every research-eligible pair
    prod_checks = []
    for instrument in ("GBPUSD", "AUDUSD", "USDCHF", "NZDUSD"):
        d = ur.resolve(instrument, "M5", production_requested=True)
        ok = d.state.value == "PRODUCTION_AUTHORIZATION_REQUIRED"
        if not ok:
            all_ok = False
        prod_checks.append(
            {
                "instrument": instrument,
                "expected": "PRODUCTION_AUTHORIZATION_REQUIRED",
                "actual": d.state.value,
                "ok": ok,
                "reason": d.reason,
            }
        )

    return {
        "suite": "V46_UNIVERSAL_ROUTER_ACCEPTANCE",
        "passed": all_ok,
        "matrix": results,
        "production_authorization": prod_checks,
    }
