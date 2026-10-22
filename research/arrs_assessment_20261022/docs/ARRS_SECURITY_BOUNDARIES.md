# ARRS Security and Execution Isolation

## Existing controls (VERIFIED)
- `SafetyConfig.production_authorized: bool = False`
- `SafetyConfig.live_enabled: bool = False`
- `ExecutionGuard` is fail-closed and does not place orders
- `RulebookRegistry` is in-process; qualification_status is declarative metadata

## Required ARRS boundaries
1. Research processes/services **must not import or call** order submission, queue enqueue for live, or MT5 adapters.  
2. Experiment registry writes **cannot** set `production_authorized=True`.  
3. Candidate APPROVED transition requires an actor identity outside the research service identity.  
4. Failure of ARRS must not halt or alter existing approved execution paths.  
5. Research code must not rewrite `SafetyConfig` or risk limits for production accounts.

## Enforcement recommendations
- Separate Python package/module path for ARRS with import-linter or tests forbidding imports of `autonomous_execution_service`, `durable_execution_queue` write paths.  
- Stage 1: file-based registry under `research/arrs/` only — no production DB migrations.  
- Automated tests: invalid lifecycle → APPROVED rejected; research flag flip rejected.

## Boolean flags alone are insufficient
A flag in a JSON artifact is not enforcement. Enforcement requires process isolation + tests + (later) service scopes.
