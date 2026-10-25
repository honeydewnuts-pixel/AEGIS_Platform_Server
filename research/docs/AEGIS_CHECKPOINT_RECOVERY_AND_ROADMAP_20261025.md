# AEGIS — Original Checkpoint Recovery, Research Closure, and Next-Stage Plan
**Date:** 2026-10-25  
**Mode:** Read-only inspection + documentation only  
**production_authorized=false · execution_authorized=false**

---

## 1. Executive decision

1. **Core-platform continuation checkpoint (research lineage pre–Variant B-V):**  
   **`579180d0079c56e02bd81b4f4f707ad8c7859f8a`**  
   *Message:* `research: ARRS implementation registry and tests` (2026-10-23).  
   This is the last commit on the linear research chain **before** Variant B-V (`d07f76b`).

2. **Repository / V46 platform baseline (monorepo root of this clone’s main tip):**  
   **`8385fc60ea16a195ba00a64697ddc07d4f526b9c`**  
   *Message:* `research: broker-realistic discovery status — Stage3/3B zero winners reconciled` (2026-10-14).  
   Contains V46 baseline docs, backend, ExecutionGuard defaults, CI configs. In this environment, `origin/main` resolved to this SHA.

3. **Rulebook V1.4:** Formally **NOT QUALIFIED** — **0/13** Class A instruments passed predeclared gates. Artifacts preserved at `d273ab6`. Do not retune.

4. **All surveyed research families:** **No production-qualified Rulebook.** Negative findings preserved.

5. **Next research experiment (single):** *Trade-management ablation on a frozen, non-optimized structural signal set* — measure whether failures are primarily **signal expectancy** vs **exit/cost path**, using preregistered TM variants on **development/validation only**, with final-test locked and previously exposed data labelled. Do **not** implement in this task.

6. **No production, deploy, order, EA, or authorization changes** were made in this task.

---

## 2. Verified original checkpoint and branch recommendation

| Field | Evidence |
|-------|----------|
| Pre–Variant B-V SHA | **`579180d0079c56e02bd81b4f4f707ad8c7859f8a`** |
| Date | 2026-10-23 13:00:48 +0000 |
| Message | research: ARRS implementation registry and tests |
| Parent (prior) | `813050e` (ARRS assessment) |
| Next (Variant B-V) | `d07f76b` |
| V46 / main tip in clone | **`8385fc60ea16a195ba00a64697ddc07d4f526b9c`** (2026-10-14) |
| Branches containing 579180d | research/arrs-implementation-20261023 and descendants (stage2, stage3, v14, etc.) |

**Recommendation:** Continue **core-platform** work from the V46 tree at **`8385fc6`** (or current protected main after owner confirms remote main), without merging research experiment branches. Continue **research infrastructure (ARRS)** from **`579180d`** or later ARRS commits (`82ffd0c` Stage 2) on isolated `research/*` branches only.

**Do not** reset protected main. **Do not** merge V1.4 / Variant B-V / Stage 3 candidates into main.

---

## 3. Core-platform status matrix

Classification key: SOURCE-VERIFIED | TEST-VERIFIED | BUILDER-REPORTED | UNVERIFIED | NOT IMPLEMENTED | BLOCKED

| Component | Status | Evidence | Gap / next |
|-----------|--------|----------|------------|
| ExecutionGuard fail-closed | SOURCE-VERIFIED | `backend/app/safety/execution_guard.py` — `production_authorized=False`, `live_enabled=False` default | ENVIRONMENT-VERIFIED deploy not claimed |
| RulebookRegistry | SOURCE-VERIFIED | `backend/app/rulebooks/registry.py`, founding QUALIFIED_RESEARCH_CANDIDATE_FROZEN entries | Research candidates ≠ live |
| Durable execution queue | SOURCE-VERIFIED | `backend/app/services/durable_execution_queue.py` present | Not exercised this task |
| Durable lifecycle | SOURCE-VERIFIED | `durable_lifecycle_service.py` | Isolation from ARRS required |
| Universal Router | SOURCE-VERIFIED (docs) | V46 baseline / universal_router | Fail-closed design per docs |
| OHLC / market data path | SOURCE-VERIFIED (modules) | services under `backend/app/services/` | Full pipeline ENVIRONMENT UNVERIFIED |
| Risk / volume / margin | SOURCE-VERIFIED (partial) | SafetyConfig, risk schemas on RulebookDefinition | Contract-spec completeness UNVERIFIED |
| Emergency stop | SOURCE-VERIFIED (enum) | Decision.KILL_SWITCH in ExecutionGuard | Runtime ENVIRONMENT UNVERIFIED |
| CI workflows | SOURCE-VERIFIED | `.github/workflows/backend-ci.yml`, mobile-ci | Full CI **NOT RUN** this task |
| Render / deploy | BUILDER-REPORTED | REPOSITORY_DEPLOYMENT_READINESS.md — deploy not claimed successful | BLOCKED without controlled deploy |
| Live trading | NOT AUTHORIZED | Explicit false flags + docs | Must remain unauthorized |
| ARRS Stage 1–2 research eval | TEST-VERIFIED (local) | Stage1 27 PASS; Stage2 21 PASS in prior sessions | Not re-run this task |
| Screenshot/mobile safeguards | BUILDER-REPORTED | Historical AEGIS design | Not re-audited line-by-line here |

**Important:** Source presence ≠ deployed production correctness. No production mutation performed.

---

## 4. Rulebook V1.4 audit and closure

| Item | Result |
|------|--------|
| Branch | `research/rulebook-v14-bb17-bb34-20261025` |
| Commit | **`d273ab658485d77b5d1f9d14df8d8d199376d2f5`** — **VERIFIED** present |
| Artifacts | prereg, engine, tests (5 PASS reported), `v14_results.csv`, ACCEPTANCE_REPORT.md |
| Timeframe | M15 (resampled from M5 Class A) — consistent with report |
| Gates | val PF≥1.2, test PF≥1.1 — **0/13 PASS** in recorded CSV |
| Auth flags | false/false on all rows — **SOURCE-VERIFIED** in CSV |
| Full reproduction this task | **NOT RUN** (results inspected, not re-executed) |

**Formal status: NOT QUALIFIED.**

**Preserved limitations:** price-unit risk proxy; incomplete commission/slippage/swap; exposed final-test data; progression state-machine interpretation risk.

**Action:** Close as current alpha path. Do not retune on same final-test folds.

---

## 5. Inventory of previous research candidates

| Family | Branch / commit (reported) | Outcome | Exposed final? | Future? |
|--------|----------------------------|---------|----------------|---------|
| Broker-realistic Stage3/3B | 8385fc6 | Zero winners (status) | Yes | Closed |
| Failed price discovery | failed-price-discovery | INCONCLUSIVE (≪ spread) | Yes | Measurement only |
| Session liquidity | session-liquidity | Seasonality, not transition edge | Yes | Closed as trading path |
| Volatility shock | volatility-shock | No general conditional edge | Yes | Closed |
| Market-state transitions | market-state | Descriptive only | Yes | Closed as alpha |
| Directional displacement | Phase 6 | Novelty reject | — | Closed |
| DBT RSI / BB RSI v2.1 | dbt / bb17 branches | Signal engine; no cash TM qual | Yes | Signal-only |
| V7 Fixed Squeeze | v7 branch | 0 passers all-instrument | Yes | Closed |
| Pattern discovery | 9168b74 / 0ba218a | 0 hard materiality; no Rulebook | Yes | Closed search |
| P7 L1/L2 | c872ab2 | Exploratory association; unconfirmed | In-sample issues | No TM retrofit |
| ARRS Stage 1–2 | 579180d / 82ffd0c | Infrastructure PASS tests | — | Reuse |
| ARRS Stage 3 | 0625747 | 26/26 FAIL inside/range20 | Yes | Closed |
| Variant B-V | d07f76b | Causal non-transfer (look-ahead ref) | Yes | Closed |
| Rulebook V1.4 | d273ab6 | 0/13 FAIL | Yes | **Closed** |

Do **not** pool these into a synthetic positive performance claim.

---

## 6. Failure-mode evidence assessment

From available **aggregate** metrics (V1.4, Stage 3, Variant B-V causal):

| Mode | Evidence strength | Notes |
|------|-------------------|-------|
| Weak signal expectancy | **Supported** | Full and fold PF typically &lt; 1 under causal fills |
| Exit / TM damage | **Possible, under-measured** | Few side-by-side TM ablations with frozen signals |
| Cost sensitivity | **Partial** | Bid/Ask spread included; commission/swap often zero in models |
| Instrument instability | **Supported** | Cross-sectional FAIL consistency, not one bad pair |
| Chronological instability | **Partial** | Val vs test divergence (e.g. EURJPY val&gt;1, test&lt;1) |
| Implementation uncertainty | **Acknowledged** | V1.4 progression sequencing; Variant B-V look-ahead in reference |

**Missing for sharper diagnosis:** trade-level MFE/MAE distributions, exit-reason breakdowns, and controlled TM ablations on **frozen** signals without re-selecting entries on test.

---

## 7. Recommended single next research experiment

### Question
**Given a frozen, non-optimized structural signal definition, does changing only trade-management (stop multiple, time stop, trail on/off) move validation expectancy from negative to robustly positive after Bid/Ask costs—or does the signal remain negative under all preregistered TM templates?**

### Why
Existing failures mix signal and management. Evidence shows widespread PF&lt;1 after causal execution; we do not yet know if exits are the dominant destroyer.

### Reject if
All preregistered TM templates show val PF&lt;1.0 (or fail sample gates) on ≥80% of Class A instruments, or any “pass” appears only after using final-test to choose TM.

### Design (document only — not implemented here)
- **Signals:** freeze one simple definition (e.g. Stage 3 range20 **or** a single V1.4 subset)—**no** re-optimization of entries.
- **TM set:** ≤3 templates preregistered (e.g. 1.5 ATR stop / 48h; 2.0 ATR stop / 48h; 2.0 ATR + trail 2.5).
- **Data:** Class A Bid/Ask only; label exposed history; prefer any new post-cutoff data if available.
- **Split:** 60/20/20; **final-test locked** until TM choice frozen on train/val only.
- **Costs:** Bid/Ask sides + declared commission scenario; no silent zero if material.
- **Gates:** predeclared min trades, val PF, test PF, cost stress; fail closed on missing evidence.
- **Stop rule:** stop after one pass through the ≤3 TM × instrument matrix; no expansion.
- **Artifacts:** prereg hash, per-instrument folds, exit-reason counts, MFE/MAE, ARRS records, all FAILs retained.

If new untouched data are unavailable, still run the ablation but classify confirmation as **PENDING**.

---

## 8. Coordinated AEGIS roadmap

### A. Core-platform checkpoint recovery
- **Status:** Baseline at `8385fc6`; research chain continues separately.
- **Next:** Owner confirms remote `main`; optional `platform/continue-from-v46` branch from verified main **without** research experiment merges.
- **Acceptance:** Documented SHA, clean separation of `backend/` vs `research/`.

### B. Execution, risk, operational integrity
- **Status:** Source-level fail-closed controls present.
- **Outstanding:** ENVIRONMENT verification (staging), contract specs, recovery drills.
- **Unauthorized:** live_enabled, production_authorized elevation.

### C. Strategy discovery and validation
- **Status:** Multiple families closed negative; ARRS evaluator usable.
- **Next:** Single TM-ablation experiment (§7); no broad indicator grids.
- **Acceptance:** Prereg → run → all results recorded including negatives.

### D. Research-to-demo qualification
- **Status:** No candidate eligible.
- **Blocked until:** Independent confirmation data + full cost model + human review gates.

### E. Production readiness
- **Status:** Not production-ready for trading.
- **Evidence required:** CI green on target, staging soak, explicit written authorization—none of which this task provides.

---

## 9. Risks, blockers, unresolved questions

- Remote `main` identity should be re-confirmed by operator (this clone tipped `8385fc6`).
- Full backend CI / staging environment **NOT RUN** here.
- Contract-level lot/tick value tables incomplete for account-currency claims.
- No genuinely untouched forward window for independent confirmation of any strategy.
- Git working tree may show unrelated deleted paths (mobile_app noise)—do not mass-commit.

---

## 10. Supporting commits and paths

| Conclusion | Path / SHA |
|------------|------------|
| Pre–Variant B-V | `579180d0079c56e02bd81b4f4f707ad8c7859f8a` |
| V46 baseline / main tip | `8385fc60ea16a195ba00a64697ddc07d4f526b9c` |
| Variant B-V | `d07f76b` / `research/variant-bv-20261024` |
| ARRS Stage 2 | `82ffd0c` / `research/arrs-stage2-20261024` |
| ARRS Stage 3 | `0625747` / `research/arrs-stage3-candidates-20261025` |
| Rulebook V1.4 | `d273ab6` / `research/rulebook_v14_20261025/` |
| V1.4 results | `research/rulebook_v14_20261025/outputs/v14_results.csv` |
| ExecutionGuard | `backend/app/safety/execution_guard.py` |

---

## Distinction summary

| Category | Content |
|----------|---------|
| **Verified** | Commit SHAs above; V1.4 CSV shows 0 PASS and auth false; ExecutionGuard defaults false; research dirs present |
| **Reported not re-verified** | Prior test pass counts from earlier sessions; full deploy health |
| **Incomplete** | Staging ENVIRONMENT checks; full CI; contract-spec sizing; untouched confirmation data |
| **Next authorized step** | (1) Confirm remote main SHA with owner; (2) Keep research on `research/*`; (3) Review/approve §7 experiment design before any implementation; (4) No production authorization |

**AEGIS is not production-ready for live trading on the basis of this audit.**
