# V3 Active Path (authoritative)

Active production path for chart analysis:

- Rule engine: `backend/app/services/signal_rule_engine_v3.py` (RULEBOOK_V3 v2.3.6.6)
- Rulebook JSON: `backend/app/templates/rulebook_v3.json`
- Neural (primary): `backend/app/services/neural_service.py` + `neural_features_v3.py` (**FEATURE_DIM = 13**)
- Model file: `backend/app/models/aegis_neural_v3_2.3.6.6.json`
- Dispatch: `backend/app/services/brain_cv_service.py` → V3 first, V3-fallback on init failure

**Not on the active path**

- Archived v1/v2 under `archive_v1_v2/`
- 68-feature / 17-channel temporal window (legacy) — **not used**
- `neural_features_v3_fallback.py` (FEATURE_DIM = 52) only via explicit failover

Screen-Y convention: smaller pixel Y = higher on the chart. Formal rulebook operators in `rulebook_v3.json` are screen-Y operators and are applied directly in the engine (no double inversion on MA/RSI gates).
