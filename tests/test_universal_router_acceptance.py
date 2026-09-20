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
    # Non-V2OPT rulebooks only — Good pairs
    for inst in ("GBPUSD", "AUDUSD", "USDCHF", "NZDUSD", "GBPJPY", "EURGBP", "USDCAD"):
        d = ur.resolve(inst, "M5")
        assert d.state == RouteState.ROUTABLE_RESEARCH, (inst, d)
        assert d.rulebook_ids, inst
        assert d.production_authorized is False
        assert not any("V2OPT" in x for x in d.rulebook_ids), (inst, d.rulebook_ids)


def test_v2opt_only_pairs_disabled():
    """V2-OPT-only pairs are TRADING_DISABLED (insufficient qualification gates)."""
    ur = _router()
    for inst in ("EURUSD", "USDJPY", "EURJPY", "GBPAUD"):
        d = ur.resolve(inst, "M5")
        assert d.state == RouteState.TRADING_DISABLED, (inst, d)
        assert d.production_authorized is False


def test_production_authorization_required():
    ur = _router()
    for inst in ("GBPUSD", "AUDUSD", "USDCHF", "NZDUSD"):
        d = ur.resolve(inst, "M5", production_requested=True)
        assert d.state == RouteState.PRODUCTION_AUTHORIZATION_REQUIRED, (inst, d)
        assert d.production_authorized is False
