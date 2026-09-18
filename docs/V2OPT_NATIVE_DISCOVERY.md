# V2-OPT Native Sequential Discovery

## Protocol
- One instrument at a time
- Nested parameter search (tune-only)
- Inner holdout + validation half stability
- avg_R > 0, trade-rate band, gap-penalized selection
- 60/20/20 outer chronological split
- cost 0.05R

## Registry
- `registry/v2_opt/{INSTRUMENT}/rulebook.json`
- Entries also listed in `registry/v40/AEGIS_V40_RULEBOOK_REGISTRY.csv`
- Instruments promoted from transfer-reject to `NATIVE_V2OPT_QUALIFIED` / `RESEARCH_ELIGIBLE` where V2-OPT passed gates

## Safety
- `production_authorized = false` for all V2-OPT books
- Production requests still return `PRODUCTION_AUTHORIZATION_REQUIRED`

## Evaluator
- `backend/app/rulebooks/evaluators/v2opt_sequential.py`
- Wired from `universal_analysis_service` when OHLC bars ≥ 30 and a V2OPT rulebook id is eligible
