# ARRS Component Inventory

Capability| Existing implementation| Verified location| Tests/evidence| Status| Reuse recommendation| Gap
---|---|---|---|---|---|---
Market-data validation| Partial (CSV loaders, OHLC checks in P7 engine)| research/p7…/scripts/p7_features.py load(); pattern features load| P7 tests pass| PARTIALLY VERIFIED| Reuse loaders| Central manifest service
Dataset manifests + hashing| pattern_discovery inventory CSV; P7 model manifests| research/pattern_discovery_20261022/outputs/dataset_inventory.csv| SHA verified for XAUUSD| VERIFIED| Register as ARRS dataset records| Unified schema
Feature calculation| Price-structure + P7 features| research/pattern_discovery…/features.py; p7_features.py| leakage tests 5/5; p7 10/10| VERIFIED| Versioned feature modules| Registry of feature versions
Pattern enumeration| 22 binary patterns| research/pattern_discovery…/discover.py| run log 2640 evals| VERIFIED| Case-study only; do not expand blindly| Generator interface
Experiment registration| Ad-hoc markdown/JSON per study| research/*/docs, outputs| Present| PARTIALLY VERIFIED| Formalize| Unified Experiment ID schema
Chronological splitting| 60/20/20 in discover/evaluate| discover.py split_idx; evaluate_p7| Used in runs| VERIFIED| Standardize helper| Holdout exposure flag required
Leakage prevention| Prefix tests| test_features_leakage.py; test_p7_features.py| PASS| VERIFIED| Mandatory CI for generators| Broader suite
Backtesting / cash| P7 in-sample engine (archive); V7 engines| p7 archives; research/v7*| SOURCE_REPORTED / partial| PARTIALLY VERIFIED| Isolate research backtest API| No production path
Bid/Ask execution modelling| Documented in research + ExecutionGuard market state| backend/app/safety/execution_guard.py; research specs| Code present| VERIFIED| Reuse conventions| Unified cost applicator for research
Spread/commission modelling| Research cost assumptions; execution_cost_model service| backend/app/services/execution_cost_model.py| File exists| PARTIALLY VERIFIED| Inspect & reuse| Research vs live cost config separation
Stop/exit modelling| Per-Rulebook schemas in registry| backend/app/rulebooks/models.py execution_schema| Founding registry examples| VERIFIED| Keep on RulebookDefinition| Research candidates need explicit TM before cash PF
Position sizing| Risk schemas on RulebookDefinition| models.py| VERIFIED structure| VERIFIED| Do not invent in ARRS stage 1| —
Statistical evaluation| Conditional returns, MFE/MAE scripts| pattern_discovery outputs| NEWLY computed in prior work| VERIFIED for those runs| Adapter to registry| FDR / multiple-testing module MISSING
Multiple-testing controls| Disclosed narratively| FINAL_REPORT.md| REPORTED| REPORTED| Implement policy| Software enforcement MISSING
Candidate registries| RulebookRegistry (production/research-frozen IDs)| backend/app/rulebooks/registry.py| Code| VERIFIED| Extend or parallel ResearchCandidateRegistry| Research lifecycle states MISSING
Rulebook versioning| version, supersedes fields| models.py| VERIFIED| VERIFIED| Keep| Research candidate versioning
Approval/authorization| production_authorized default False; qualification_status| execution_guard.py; models.py| Code| VERIFIED| Enforce in lifecycle| Transition authorization matrix
Runtime monitoring| demo_execution_monitor; metrics| services/demo_execution_monitor.py; core/metrics.py| Files present| PARTIALLY VERIFIED| Read-only hooks for ARRS| Drift criteria MISSING
Performance drift detection| Not found as dedicated module| —| —| MISSING| Design in stage 2+| —
Retirement/requalification| Not formalized for research candidates| —| —| MISSING| Lifecycle spec| —
Audit logging| safety/audit.py; audit_service| backend/app/safety/audit.py; services/audit_service.py| Files present| PARTIALLY VERIFIED| Append research events| Schema for experiment events
CI/test infrastructure| .github present; research unit tests local| .github/; research/*/tests| Local tests run this assessment| PARTIALLY VERIFIED| Add ARRS unit tests| Full CI not executed here
Durable position lifecycle| DurableLifecycleService| services/durable_lifecycle_service.py| Code| VERIFIED| **Do not couple research to this**| Isolation required
Order execution path| autonomous_execution_service; durable_execution_queue| services/*| Code present| VERIFIED| **ARRS must not call**| Security boundary tests
