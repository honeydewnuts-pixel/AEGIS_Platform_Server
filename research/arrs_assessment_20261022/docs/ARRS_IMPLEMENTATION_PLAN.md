# ARRS Implementation Plan — Stage 1

## Scope (minimal)
1. File-based experiment + candidate registry under `research/arrs_registry/`  
2. Schema: experiment_id, candidate_id, parent_id, dataset_hashes, commit_sha, disposition, metrics paths, authorization flags (always false for production)  
3. Adapter: import pattern_discovery and P7 summary JSON/CSV **read-only** into registry records  
4. Lifecycle validation functions + unit tests (invalid transitions fail)  
5. Documentation cross-links to existing research folders  

## Reuse
- Dataset inventory CSVs  
- discovery_summary.json, evaluation_summary.json  
- RulebookDefinition field ideas (do not mutate production registry in stage 1)

## New files (proposed)
- research/arrs_registry/schema.json  
- research/arrs_registry/register_existing.py  
- research/arrs_registry/lifecycle.py  
- research/arrs_registry/tests/test_lifecycle.py  
- research/arrs_registry/tests/test_no_execution_import.py  

## Acceptance criteria
- [ ] Existing discovery/P7 artifacts registered without content mutation  
- [ ] Negative dispositions preserved  
- [ ] Cannot transition to APPROVED from research API  
- [ ] production_authorized remains false in all registry writes  
- [ ] Unit tests pass  
- [ ] No main merge, no V53.6 edit, no deployment  

## Out of scope stage 1
Automated pattern search expansion, FDR engine, drift monitor, demo/live integration, DB migrations.

## Risks
- Remote branch tip lag vs local commits for discovery artifacts  
- Accidental coupling to execution services  

## Rollback
Delete/revert research/arrs_registry branch commits only; no production state.

## Next stage conditions
Stage 1 accepted; lifecycle tests green; security import tests green; product owner signs off on state enum.
