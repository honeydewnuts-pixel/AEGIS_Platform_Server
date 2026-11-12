"""Fail-closed operational registry after research archival."""
from pathlib import Path
import sys

# Ensure backend app is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

def test_founding_registry_is_empty():
    from app.rulebooks.registry import founding_registry
    reg = founding_registry()
    assert reg.count() == 0
    assert list(reg.all()) == []
    assert reg.get("AEGIS-RB-V31-GBPUSD-5M") is None
    assert reg.lookup("GBPUSD", "M5") == []


def test_operational_csv_empty():
    root = ROOT
    rb = root / "registry" / "operational" / "AEGIS_OPERATIONAL_RULEBOOK_REGISTRY.csv"
    inst = root / "registry" / "operational" / "AEGIS_OPERATIONAL_INSTRUMENT_REGISTRY.csv"
    assert rb.exists()
    assert inst.exists()
    # header only
    assert sum(1 for _ in rb.open()) == 1
    assert sum(1 for _ in inst.open()) == 1


def test_registry_service_empty():
    from app.services.registry_service import RegistryService
    svc = RegistryService()
    assert svc.list_rulebooks() == [] or len(svc.list_rulebooks()) == 0
    tradeable = svc.list_instruments(tradeable_only=True)
    assert tradeable == [] or len(tradeable) == 0


def test_archived_ids_not_routable():
    from app.rulebooks.registry import founding_registry
    reg = founding_registry()
    for rid in (
        "AEGIS-RB-V31-GBPUSD-5M",
        "AEGIS-RB-V35-GBPUSD-5M",
        "AEGIS-RB-V53.6-V31-AUDUSD-5M",
    ):
        assert reg.get(rid) is None
