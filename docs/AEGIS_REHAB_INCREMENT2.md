# Rehabilitation Increment 2

Branch: research/repository-rehabilitation-20261112b
Parent: a5ccf58cd115cfd51a02869d0277cb7da7458b78

## Changes
- /rulebooks* uses RegistryService (same as /api/registry/*); no founding_registry API snapshot
- get_active_pointer requires rulebook + tradeable instrument + eligible list + timeframe consistency
- Stale active_profile cannot authorize; blocked_reason always set when inactive
- production_authorized and execution_authorized remain false even on consistent association
- Adversarial tests with temporary CSVs/profiles (12 cases)
- V38 founding test expects empty registry
- Missing CSV log message no longer implies founding fallback

## Tests
pytest tests/test_registry_fail_closed_adversarial.py tests/test_operational_registry_empty.py tests/rulebooks/test_rulebook_library_v38.py
20 passed
