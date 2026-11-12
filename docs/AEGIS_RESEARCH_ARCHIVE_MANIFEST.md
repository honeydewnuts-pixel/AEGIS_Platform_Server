# AEGIS Research Archive Manifest

**Date:** 2026-11-12  
**Branch:** research/repository-rehabilitation-20261112  
**production_authorized:** false  
**execution_authorized:** false  

## Purpose

Preserve all researched, experimental, historical and qualified-but-unapproved rulebooks **out of the operational path**.

Operational registries after rehabilitation:

| Registry | Count |
|----------|------:|
| Operational rulebooks | 0 |
| Operational tradeable instruments | 0 |
| Active rulebooks (API) | [] |

## Research families located (inventory)

| Family | Example paths | Operational status |
|--------|---------------|--------------------|
| V31 / V35 founding (code) | `backend/app/rulebooks/registry.py` (definitions removed from operational load) | **Archived — not loaded** |
| V39 / V40 CSV registries | `artifacts/v40/registry/*`, `artifacts/v39/*` | Emptied operationally; artifact history retained |
| V53.6 qualified | `artifacts/v53_6/` | Research only |
| V2-OPT | `artifacts/v2_opt/rulebooks/` | Research only |
| Templates | `backend/app/templates/rulebook_*.json` | Not operational sources |
| archive_v1_v2 | `archive_v1_v2/` | Historical |

## Operational files (authoritative empty)

- `registry/operational/AEGIS_OPERATIONAL_RULEBOOK_REGISTRY.csv` (header only)
- `registry/operational/AEGIS_OPERATIONAL_INSTRUMENT_REGISTRY.csv` (header only)
- `registry/broker_technical/BROKER_SYMBOL_CATALOGUE.csv` (technical; no strategy eligibility)

## Code changes

- `founding_registry()` returns **empty** `RulebookRegistry`.
- `RegistryService` loads operational CSVs only; does **not** merge founding research books.
- `RESEARCH_ELIGIBLE` is **not** treated as tradeable.
- Rulebook API returns explicit empty-state payload with authorization flags false.

## Hashes

Recompute after commit:

```bash
sha256sum registry/operational/*.csv artifacts/v40/registry/*.csv
```

## Non-goals

- No production authorization of any research rulebook.
- No deletion of historical research evidence under `artifacts/` or `archive_v1_v2/`.
- Broker technical symbol catalogue does not authorize trading.
