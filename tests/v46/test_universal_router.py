from pathlib import Path

from backend.app.universal_router.router import RouteState, UniversalRouter

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "registry" / "v40" / "AEGIS_V40_RULEBOOK_REGISTRY.csv"
INST = ROOT / "registry" / "v40" / "AEGIS_V40_INSTRUMENT_REGISTRY.csv"


def _ur():
    return UniversalRouter(instrument_csv=INST, rulebook_csv=REGISTRY)


def test_qualified_research_route():
    r = _ur().resolve("AUDUSD", "M5")
    assert r.state == RouteState.ROUTABLE_RESEARCH
    assert len(r.rulebook_ids) >= 1
    assert r.production_authorized is False
    assert not any("V2OPT" in x for x in r.rulebook_ids)


def test_v2opt_only_instrument_disabled():
    """EURUSD is V2-OPT-only with insufficient gates — not research-tradeable."""
    r = _ur().resolve("EURUSD", "M5")
    assert r.state == RouteState.TRADING_DISABLED
    assert r.production_authorized is False
    r_prod = _ur().resolve("EURUSD", "M5", production_requested=True)
    assert r_prod.state in (
        RouteState.TRADING_DISABLED,
        RouteState.PRODUCTION_AUTHORIZATION_REQUIRED,
    )
    assert r_prod.production_authorized is False


def test_production_request_cannot_promote_research_candidate():
    r = _ur().resolve("USDCHF", "M5", production_requested=True)
    assert r.state == RouteState.PRODUCTION_AUTHORIZATION_REQUIRED
