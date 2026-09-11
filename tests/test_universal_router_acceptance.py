"""V46 Universal Router acceptance — fail-closed research vs production."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.universal_router import UniversalRouter, RouteState


def _router():
    reg = ROOT / "registry" / "v40"
    return UniversalRouter(
        instrument_csv=reg / "AEGIS_V40_INSTRUMENT_REGISTRY.csv",
        rulebook_csv=reg / "AEGIS_V40_RULEBOOK_REGISTRY.csv",
    )


def test_research_eligible_pairs():
    ur = _router()
    for inst in ("GBPUSD", "AUDUSD", "USDCHF", "NZDUSD"):
        d = ur.resolve(inst, "M5")
        assert d.state == RouteState.ROUTABLE_RESEARCH, (inst, d)
        assert d.rulebook_ids, inst
        assert d.production_authorized is False


def test_rejected_pairs_fail_closed():
    ur = _router()
    for inst in ("EURUSD", "USDJPY", "EURJPY", "GBPJPY"):
        d = ur.resolve(inst, "M5")
        assert d.state == RouteState.TRADING_DISABLED, (inst, d)


def test_production_authorization_required():
    ur = _router()
    for inst in ("GBPUSD", "AUDUSD", "USDCHF", "NZDUSD"):
        d = ur.resolve(inst, "M5", production_requested=True)
        assert d.state == RouteState.PRODUCTION_AUTHORIZATION_REQUIRED, (inst, d)
        assert d.production_authorized is False
