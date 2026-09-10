# AEGIS V40 — Universal Router Policy

## Purpose
Place explicit rulebook eligibility above the legacy RULEBOOK_V3 selection path without replacing legacy intelligence.

## Routing order
1. Resolve instrument and timeframe.
2. Load Instrument Registry.
3. Resolve only rulebooks whose status is QUALIFIED_RESEARCH_CANDIDATE or SOURCE_RULEBOOK_FROZEN and whose instrument/timeframe match.
4. Require all rulebook prerequisites: data-side integrity, causal feature availability, spread policy, risk policy, and independent-reproduction status.
5. If no eligible rulebook exists, return HOLD / NOT_ELIGIBLE and do not fall through to an unrelated rulebook.
6. Preserve legacy RULEBOOK_V3 as a separately identified intelligence family; it is never silently substituted for a missing V39 rulebook.
7. Production authorization remains a separate control. All V39 registry entries are production_authorized=false.

## Fail-closed states
- UNKNOWN_INSTRUMENT
- UNKNOWN_TIMEFRAME
- NO_QUALIFIED_RULEBOOK
- INSUFFICIENT_SPREAD_DATA
- RULEBOOK_INTEGRITY_FAILURE
- MODEL_LINEAGE_FAILURE
- PRODUCTION_AUTHORIZATION_REQUIRED

## Safety invariant
A qualified research result is not an execution permission. The router may expose research eligibility while the production execution gate remains closed.
