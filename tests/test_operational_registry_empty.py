"""Fail-closed operational registry after research archival."""
from pathlib import Path
import sys
import pytest

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
    rb = ROOT / "registry" / "operational" / "AEGIS_OPERATIONAL_RULEBOOK_REGISTRY.csv"
    inst = ROOT / "registry" / "operational" / "AEGIS_OPERATIONAL_INSTRUMENT_REGISTRY.csv"
    assert rb.exists() and inst.exists()
    assert sum(1 for _ in rb.open()) == 1
    assert sum(1 for _ in inst.open()) == 1


def test_registry_service_empty_and_no_instrument_fallback():
    from app.services.registry_service import RegistryService
    svc = RegistryService()
    assert svc.list_rulebooks() == []
    assert svc.list_instruments(tradeable_only=False) == []
    assert svc.list_instruments(tradeable_only=True) == []


def test_stale_active_profile_cannot_authorize():
    from app.services.registry_service import RegistryService
    svc = RegistryService()
    ptr = svc.get_active_pointer()
    assert ptr.get("active") is False
    assert ptr.get("production_authorized") is False
    assert ptr.get("execution_authorized") is False


def test_activate_rejected_when_empty():
    from app.services.registry_service import RegistryService
    svc = RegistryService()
    with pytest.raises(ValueError, match="ACTIVATION_REJECTED"):
        svc.activate("AEGIS-RB-V31-GBPUSD-5M")


def test_archived_ids_not_routable():
    from app.rulebooks.registry import founding_registry
    reg = founding_registry()
    for rid in (
        "AEGIS-RB-V31-GBPUSD-5M",
        "AEGIS-RB-V35-GBPUSD-5M",
        "AEGIS-RB-V53.6-V31-AUDUSD-5M",
    ):
        assert reg.get(rid) is None
