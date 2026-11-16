import pytest
from app.rulebooks import founding_registry

V31 = "AEGIS-RB-V31-GBPUSD-5M"
V35 = "AEGIS-RB-V35-GBPUSD-5M"


def test_founding_registry_empty_after_rehab():
    """Operational founding registry is empty; research books are not loaded."""
    r = founding_registry()
    assert list(r.all()) == []
    assert r.get(V31) is None
    assert r.get(V35) is None


def test_lookup_fail_closed():
    r = founding_registry()
    assert r.lookup("EURUSD", "M5", qualified_only=True) == []
    assert r.lookup("GBPUSD", "M5", qualified_only=True) == []
