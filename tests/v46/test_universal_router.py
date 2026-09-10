from pathlib import Path

from backend.app.universal_router.router import RouteState, UniversalRouter

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "registry" / "v40" / "AEGIS_V40_RULEBOOK_REGISTRY.csv"


def test_qualified_research_route():
    r = UniversalRouter(REGISTRY).resolve("AUDUSD", "M5")
    assert r.state == RouteState.ROUTABLE_RESEARCH
    assert len(r.rulebook_ids) == 2
    assert r.production_authorized is False


def test_rejected_instrument_fails_closed():
    r = UniversalRouter(REGISTRY).resolve("EURUSD", "M5")
    assert r.state in {RouteState.NO_QUALIFIED_RULEBOOK, RouteState.UNKNOWN_INSTRUMENT}


def test_production_request_cannot_promote_research_candidate():
    r = UniversalRouter(REGISTRY).resolve("USDCHF", "M5", production_requested=True)
    assert r.state == RouteState.PRODUCTION_AUTHORIZATION_REQUIRED
