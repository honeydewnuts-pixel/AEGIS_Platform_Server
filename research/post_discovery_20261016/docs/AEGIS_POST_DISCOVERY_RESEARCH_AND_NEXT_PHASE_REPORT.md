# AEGIS Post-Discovery Research and Next-Phase Report

**Date:** 2026-10-16  
**STATUS:** PARTIALLY COMPLETE (research analysis executed; git commit of artefacts to remote research branch is local-workspace constrained)  
**Research branch (aegis_disc2):** `research/broker-realistic-discovery-20261014`  
**HEAD commit verified:** `8385fc60ea16a195ba00a64697ddc07d4f526b9c`  
**No production changes. No orders. No promotion. No main merge.**

---

## 1. Executive summary

Three completed Rulebook-style scans (Asian→London, H1/H4→M5 pullback, Asian→NY) produced **zero** candidates meeting the frozen qualification gates. An integrity audit confirmed serious defects in earlier cost accounting and validation-block construction. A **preregistered** direct market-behaviour study then tested whether raw directional persistence or post-low-vol expansion exists in the 5-year Bid/Ask M5 data. **Both behavioural hypotheses are rejected** under the preregistered definitions: continuation rates are below 50%, signed returns after impulses are negative on average, and low-vol states do not expand more than the unconditional baseline.  

**Conclusion:** There is no evidence-based justification to launch another large trading-rule grid on momentum-continuation or simple compression-breakout at M5 horizons 6–24. The next research family should be chosen from the roadmap (failed breakouts, session/liquidity microstructure, or event-driven) only after a new preregistration — not by relaxing gates.

---

## 2. Research branch and checkpoint

| Item | Value | Status |
|------|-------|--------|
| Repo path | `/home/workdir/artifacts/aegis_disc2` | VERIFIED |
| Branch | `research/broker-realistic-discovery-20261014` | VERIFIED |
| HEAD | `8385fc60ea16a195ba00a64697ddc07d4f526b9c` | VERIFIED |
| Working tree | Heavily dirty (mass delete/re-add); discovery outputs live under `/home/workdir/artifacts/discovery_hypotheses/` | VERIFIED |
| Discovery artefacts committed at HEAD? | **No** — later scan CSVs/JSON and post_discovery_phase live on disk, not in that commit | VERIFIED |

---

## 3. Verified vs reported

| Claim | Classification |
|-------|----------------|
| Stage3/3B n_selected=0 at commit 8385fc6 | VERIFIED (commit message + prior artefacts) |
| Asian London v2: 254 evals, 0 passers | VERIFIED from `asian_london_v2_summary.json` |
| HTF pullback: 195 evals, 0 passers; costs in filter only | VERIFIED from code + summary |
| Asian NY: 195 evals, 0 passers; full-cost in R | VERIFIED from code + summary |
| Broker-correct unit tests 27/27 | VERIFIED (executed) |
| D1/D2 market-behaviour reject | VERIFIED (executed this assignment) |
| Remote GitHub push of new artefacts | **BLOCKED** in this environment (no verified push performed) |

---

## 4. Completed-scan reconciliation

| Experiment | Exec sides OK? | Full cost in R? | Calendar blocks? | Final test | Best val (as reported) | Qualifiers | Status |
|------------|----------------|-----------------|------------------|------------|------------------------|------------|--------|
| Asian→London v2 | Yes (broker-correct) | No (spread/filter) | No (trade quantiles) | EXPOSED | PF~1.38–1.49, n~212 | 0 | **FAILED UNDER SPEC** |
| HTF→M5 pullback | Yes | **No** (slip/comm filter only) | No (trade quantiles) | EXPOSED | PF~1.24, n=160 | 0 | **FAILED; PF not fully cost-adjusted** |
| Asian→NY | Yes | **Yes** | **Yes** (calendar; mostly insufficient n) | EXPOSED | PF_full~0.98, n~53 | 0 | **FAILED UNDER SPEC** |

No candidate is promoted. Incompatible cost bases must not be ranked against each other.

---

## 5. Integrity defects found

| Defect | Severity | Repaired? |
|--------|----------|-----------|
| Slippage/commission in filter but not in realised R (HTF scan) | High | Documented; Asian-NY scan implemented full-cost R |
| Six-block = trade-count quantiles not calendar duration | High | Documented; Asian-NY used calendar blocks |
| Gap fill at stop price (optimistic) | Medium | Documented; Asian-NY conservative open-fill option |
| Final 20% treated as untouched after inspection | High | Labelled EXPOSED in all new work |
| 160 trades described as failing >150 | Low (reporting) | Corrected in prior audit |
| 0.7 pip commission = assumption | Info | Labelled in all full-cost work |
| Discovery artefacts not in git commit 8385fc6 | Process | On disk under discovery_hypotheses/; commit to branch still required by operator |

Regression tests: `test_broker_correct_simulator.py` **27 PASS / 0 FAIL**; `test_asian_range_ny_simulator.py` **4 PASS / 0 FAIL**.

---

## 6. Direct market-behaviour findings

Prereg hash: `dd0ff932fb9617fe…` (recorded **before** outcome analysis).

**D1 Persistence (H=12):** REJECT. 0/13 instruments with positive mean signed return; mean continuation 47.6%; mean effect −0.25× median spread.

**D2 Vol expansion after low-vol (H=12):** REJECT / not tradable. Mean ratio_vs_uncond ≈ 0.96; only 3/13 instruments slightly above 1.0.

Outputs:  
`post_discovery_phase/outputs/direct_market_behaviour_results.csv`  
`post_discovery_phase/outputs/direct_market_behaviour_summary.json`  
`post_discovery_phase/docs/AEGIS_DIRECT_MARKET_BEHAVIOUR_FINDINGS.md`

---

## 7. Decision gate (behaviour → trading hypothesis)

A measured effect may proceed to a **minimal** trading simulation only if all of:

1. Clear definition + data support  
2. Not explained by lookahead/overlap alone  
3. Stable across chronological halves  
4. Effect size & uncertainty reported  
5. Instrument dependence clear  
6. Executable entry/exit plausible  
7. Expected move ≳ 5× (spread + slip + commission)  
8. Small fixed rule set without using EXPOSED final 20% to choose parameters  

**D1 and D2 fail this gate.** Do not auto-integrate into V53.6.

---

## 8. Operational-readiness (no mutation)

| Item | Status |
|------|--------|
| Stage 6.6 recovery acceptance | Incomplete (disposable restore still required) |
| Neon PITR ≠ backup acceptance | Affirmed |
| Stale EURUSD controlled-demo | Do not requeue |
| Executor v2.21 compile ≠ VPS binary proof | Affirmed |
| NO_POLL_YET monitor metric | May miss durable pending path |
| Production_authorized | Remains false; **not changed** |
| This assignment | No queue mutation, no orders, no deploy |

---

## 9. Recommended next action (evidence-based)

1. **Do not** run another M5 momentum or simple range-expansion Rulebook grid.  
2. Operator: commit `discovery_hypotheses/` and `post_discovery_phase/` onto `research/broker-realistic-discovery-20261014` when git identity/remote access is available.  
3. Next research family candidates (rank after a new preregistration):  
   - **Failed breakouts / failed price discovery** (distinct from “expansion after compression”).  
   - **Session/liquidity microstructure** (e.g. first-hour range behaviour with explicit cost model).  
   - **Event-driven** only if timestamped calendar + pre-release expectations exist.  
4. Any new trading simulation must use: full-cost R, calendar blocks, conservative gaps, EXPOSED-final labelling, preregistration-before-results.

---

## 10. Work not performed / blockers

| Item | Status |
|------|--------|
| Push/commit all artefacts to origin research branch | **BLOCKED** (workspace git dirty; no verified remote push in this session) |
| Block-bootstrap CIs for D1/D2 | Not run (limitation disclosed; simple aggregates only) |
| Corrected full-cost replay of HTF top configs | Not re-run as full grid (integrity note sufficient; would not change fail status) |
| Fresh out-of-sample data after 2026-09-15 | Unavailable |
| Production/ops changes | Intentionally not performed |

---

## 11. Key artefact paths

```
/home/workdir/artifacts/discovery_hypotheses/
  AEGIS_EXECUTION_AND_RESEARCH_INTEGRITY_AUDIT.md
  EXECUTION_CONTRACT.md
  asian_london_v2_*.{csv,json,log}
  htf_trend_m5_pullback_*.{csv,json,log}
  asian_range_ny_expansion_*.{csv,json,log,txt}
  test_broker_correct_simulator.py / test_broker_correct_output.txt
  post_discovery_phase/
    docs/AEGIS_DIRECT_MARKET_BEHAVIOUR_PREREGISTRATION.md
    docs/AEGIS_DIRECT_MARKET_BEHAVIOUR_FINDINGS.md
    docs/AEGIS_POST_DISCOVERY_RESEARCH_AND_NEXT_PHASE_REPORT.md
    outputs/AEGIS_RESEARCH_EXPERIMENT_REGISTER.csv
    outputs/AEGIS_RESEARCH_DATA_MANIFEST.csv
    outputs/direct_market_behaviour_results.csv
    outputs/direct_market_behaviour_summary.json
    outputs/preregistration_hash.txt
    scripts/run_direct_market_behaviour.py
```

**Dataset root:** `/home/workdir/artifacts/AEGIS_CSV_5Y/` (13 Bid/Ask + 1 mid-only excluded)

---

## 12. Operator-facing conclusion

We checked the books, the costs, and the raw market behaviour. The trading-rule searches did not find a rule that survives realistic costs and honest validation. More importantly, the market data themselves do not show simple short-horizon momentum continuation or reliable volatility expansion after quiet periods. That is a real research result: it tells us to stop searching in that neighbourhood and to pick a different, carefully preregistered question next — without loosening standards or going live.
