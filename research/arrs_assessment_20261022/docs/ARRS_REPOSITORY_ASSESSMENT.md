# ARRS Repository Assessment
**Date:** 2026-10-22  
**Branch:** `research/arrs-assessment-20261022`  
**Assessment base HEAD:** `c872ab2026d3fe8897a7580114bd4d567e79edc5` (p7 extension)  
**Authorization:** Research and design only — production_authorized=false, execution_authorized=false

## Executive summary

AEGIS already has substantial building blocks for Rulebook registration, fail-closed execution gating, durable position lifecycle, research experiment archives, and cost-aware discovery scripts. What is **missing** is a unified **Adaptive Rulebook Research Supervisor (ARRS)** that:

1. Registers research experiments and candidates as first-class, versioned objects  
2. Enforces preregistration and lifecycle transitions in software  
3. Prevents research code paths from granting execution authority  
4. Preserves negative results systematically  
5. Monitors approved Rulebooks for deterioration without auto-trading

The completed pattern-discovery wave (24 instruments, 2640 evaluations, **0 hard-materiality passers, 0 Rulebooks**) should be the first **case study** registered into ARRS—not re-run for a more favourable outcome.

**Recommendation:** **READY SUBJECT TO SPECIFIED PRECONDITIONS** for a minimal first-stage registry + lifecycle + read-only adapter. Not ready for automated discovery expansion or production integration.

## Verified repository baseline

| Item | Value | Status |
|------|-------|--------|
| Repo | honeydewnuts-pixel/AEGIS_Platform_Server | VERIFIED |
| Assessment start branch | research/p7-price-action-extension-20261022 @ c872ab2 | VERIFIED |
| Remote pattern-discovery | origin/research/data-driven-pattern-discovery-20261022 @ **9168b74** | VERIFIED (differs from reported 0ba218a) |
| Local pattern-discovery artifacts | research/pattern_discovery_20261022/* present | VERIFIED |
| MFE commit 0ba218a | Present in local history | VERIFIED |
| RSI v2.1 remote | origin/research/bb17-bb34-rsi-swing-v2.1-20261021 @ 1da8d97 | VERIFIED |
| RulebookRegistry | backend/app/rulebooks/registry.py | VERIFIED |
| ExecutionGuard | backend/app/safety/execution_guard.py (production_authorized=False default) | VERIFIED |
| DurableLifecycleService | backend/app/services/durable_lifecycle_service.py | VERIFIED |

**Discrepancy:** Reported discovery final SHA `0ba218a` is in local history but remote tracking tip for that branch is `9168b74`. Artifacts for MFE analysis exist locally and were committed on lineage including 0ba218a. Do not assume remote tip alone holds all outputs.

## Existing capabilities (summary)

See `ARRS_COMPONENT_INVENTORY.md` for full table.

**Strong reuse candidates:**
- `RulebookRegistry` / `RulebookDefinition` (research-candidate status vocabulary already includes QUALIFIED_RESEARCH_CANDIDATE_FROZEN)
- `SafetyConfig.production_authorized` / `live_enabled` defaults False; ExecutionGuard fail-closed
- Research tree under `research/*` with discovery CSVs, prereg docs, tests
- Dataset inventory + SHA-256 pattern from pattern_discovery and P7 work
- Feature engines: `research/pattern_discovery_20261022/scripts/features.py`, `research/p7_price_action_extension/scripts/p7_features.py`

**Gaps:**
- No unified experiment registry schema/API for research candidates vs production Rulebooks
- No enforced lifecycle state machine for research → demo → approved
- No automated multi-testing / FDR layer
- No continuous drift monitor for approved Rulebooks tied to research supervisor
- Research scripts are offline; not a service with authorization isolation tests

## Proposed architecture (high level)

```
[Data Provenance] → [Candidate Generators] → [Experiment Registry]
        ↓                    ↓                        ↓
[Feature Engine]      [Prereg Gate]            [Evaluation Engine]
                                                     ↓
                                            [Lifecycle Manager]
                                        (DISCOVERED…REJECTED/APPROVED)
                                                     ↓
                              [Read-only reports]  [NEVER auto-exec]
                                                     ↓
                              [Existing ExecutionGuard + Risk]
                                   (separate authorization)
```

Research supervisor **must not** call order submission APIs. Integration with execution requires an explicit authorized transition outside ARRS.

## First-stage recommendation

Minimal useful stage:
1. Versioned **experiment + candidate registry** (JSON/CSV or DB table) that can ingest existing pattern_discovery and P7 outputs **without modifying** historical results  
2. Lifecycle states with invalid-transition rejection  
3. Authorization flags that cannot flip to production from research code  
4. Adapter scripts + tests  
5. No new discovery algorithms  

Preconditions listed in Implementation Plan.

## Explicit non-goals (this assessment)

- No merge to main  
- No V53.6 changes  
- No live/demo orders  
- No re-running 2640 pattern grid for better scores  
- No promotion of P7-L1 to qualified Rulebook  

## Final recommendation

**READY SUBJECT TO SPECIFIED PRECONDITIONS**

Preconditions:
1. Confirm remote vs local discovery commit tip and push any missing MFE artifacts if required for provenance  
2. Agree lifecycle state enum and that research cannot set production_authorized  
3. Locate or define storage (repo files vs DB) for experiment registry without production DB migrations in stage 1  

Then implement first-stage registry only.

## Answers to required decision questions

1. **Existing ARRS-related capabilities:** RulebookRegistry/Definition; ExecutionGuard fail-closed; DurableLifecycleService (positions); research experiment folders; dataset inventories; feature + discovery scripts; cost model service file; audit modules.

2. **Reuse:** Registry pattern (not production mutation); SafetyConfig defaults; research scripts as case-study inputs; dataset hashing approach; feature modules versioned as libraries.

3. **Missing:** Unified research experiment registry; enforced lifecycle SM; multiple-testing software; drift monitor; ARRS isolation tests; automated independent-holdout reservation.

4. **Register discovery outputs without modification?** Yes — adapter reads CSV/JSON paths and hashes; disposition REJECTED/NO_RULEBOOK preserved.

5. **Prevent retuning on exposed holdout?** Prereg hash + experiment versioning; label EXPOSED segments; new versions required for criterion changes.

6. **Multiple testing:** Stage 1 record search-space size; stage 2 FDR/selection-bias methods; prefer new data confirmation.

7. **Bid/Ask profitability:** Class A only; next-bar Ask/Bid conventions; full costs; trade-management prereg before cash PF; never pool Class B as executable proof.

8. **Block unqualified → execution:** ExecutionGuard defaults; ARRS cannot set production_authorized; no import of order APIs; APPROVED only by external actor.

9. **Monitor approved Rulebooks:** Stage 2+ drift metrics (frequency, expectancy, DD, slippage); alerts only in stage 1 design.

10. **Suspension/retirement governance:** Risk/ops authority; evidence thresholds; ARRS recommends only.

11. **Smallest first implementation:** File-based experiment/candidate registry + lifecycle validation + read-only adapters + isolation tests.

12. **Acceptance tests:** Invalid transition rejection; production flag immutable from research write; existing artifacts register unchanged; unit tests green.

13. **Blocking risks:** Remote tip lag for discovery branch; accidental execution coupling; unclear storage (files vs DB).

14. **Before platform integration:** Stage 1 accepted; security tests; no production DB migration required for stage 1; owner sign-off on lifecycle enum.

15. **Evidence for next stage:** Stage 1 criteria met; at least one historical study registered end-to-end; documented isolation tests.

## Decision table

| Area | Status | Evidence | Remaining work |
|------|--------|----------|----------------|
| Repository baseline | VERIFIED | git HEAD/remotes, file listing | Reconcile remote tip 9168b74 vs local 0ba218a artifacts |
| Reusable components | VERIFIED | registry.py, execution_guard.py, research/* | Document adapters |
| Candidate registry | MISSING | — | Stage 1 implement |
| Evaluation pipeline | PARTIALLY VERIFIED | discovery + P7 scripts | Standardize interfaces |
| Statistical governance | PROPOSED | docs | Software enforcement later |
| Lifecycle management | PROPOSED | LIFECYCLE_SPEC | Code + tests |
| Security and execution isolation | PARTIALLY VERIFIED | ExecutionGuard defaults | Import-ban tests, process isolation |
| First-stage readiness | PROPOSED | IMPLEMENTATION_PLAN | Preconditions below |
| Production impact | NOT APPLICABLE | No production changes in this task | Keep zero |

## Recommendation

**READY SUBJECT TO SPECIFIED PRECONDITIONS**

Preconditions: (1) provenance reconcile for discovery remote tip, (2) agree lifecycle enum and non-self-authorization, (3) stage-1 storage = research files only (no production migration).
