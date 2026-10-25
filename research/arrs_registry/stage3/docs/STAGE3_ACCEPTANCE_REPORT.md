# ARRS Stage 3 Acceptance Report
**Branch:** research/arrs-stage3-candidates-20261025  
**production_authorized=false · execution_authorized=false**

## A. Stage 2 checkpoint
**VERIFIED** — HEAD `82ffd0c7570f908ea32f4d7f16dbd5733cb88836` on `research/arrs-stage2-20261024`.  
Stage 2 tests: **21 PASS**. Stage 1: **16 + 4 PASS** (import not re-run this session).

## B. Evaluator readiness
Causal Bid/Ask next-bar engine used as implemented in Stage 2.  
**Limitations (material):** price-unit PnL only; no account-currency/lot sizing; no swap; commission/slippage set to 0 (spread via Bid/Ask sides only).  
Results are comparative research under this model, **not** broker-ledger P&L.

## C. Datasets
Inventory: **24** files; **13 Class A Bid/Ask**; **11 Class B OHLC**.  
**Fully evaluated:** all **13 Class A** instruments × 2 candidates = **26** evaluations.  
Class B not used for Bid/Ask qualification.

## D. Candidates selected
| ID | Rationale |
|----|-----------|
| CAND-S3-INSIDE-BREAK-V1 | Fully specified price-structure rule from discovery feature family |
| CAND-S3-RANGE20-BREAK-V1 | Fully specified range-break rule |

**Excluded:** Variant B-V (directive); P7-L1/L2 (no original frozen TM — avoid retroactive favorable TM); aggregate discovery wave (already REJECTED).

## E. Preregistration
Frozen in `stage3/prereg/PREREGISTRATION.md`  
prereg_sha256: `9d94b05997038236f769648324ea82c1b30713de33063b0f5a6abebbc902772c`  
Shared TM: **TM_ATR_STOP_V1** (1.5 ATR stop, 48-bar max hold, no TP) before evaluation.

## F–G. Results
**0 / 26 PASS.** All gates_overall **FAIL** (val/test PF below GatePolicy mins; all val_pf and test_pf < 1.0).  
Best observed test_pf still < 1 (e.g. EURUSD range20 test_pf 0.805; USDJPY inside test_pf 0.785).  
No candidate satisfied predefined research gates.

## H. Transferability
**Non-transfer** for both frozen candidates across all 13 Class A instruments under the stated model.

## I. Failures / insufficient
- Strategy failure (not software failure): PF < 1 on validation and final test for every instrument.  
- Multiple-testing: 2 candidates × 13 instruments; no selection of winners after the fact for qualification.  
- Final-test segments on these CSVs have been used in prior AEGIS research waves → **exposed**; not claimed as pristine independent confirmation for a passer (none passed).

## J. Final-test exposure
Historical 5Y CSVs extensively used in prior discovery → final 20% **not** described as untouched first-look data for programme-level novelty.

## K. Files / tests / SHA
See commit. Tests: Stage2 21 PASS; Stage3 signal adapter 3 PASS. Full backend CI: **NOT RUN**.

## L. Safety
No production merge, deploy, DB mutation, broker order, EA change, or authorization elevation.  
All records: execution_authorized=false, production_authorized=false.

## Decision
**No qualified Rulebook.** Research decision: close these two Stage 3 hypotheses as **FAIL / non-transfer** under causal Bid/Ask + TM_ATR_STOP_V1. Do not optimize parameters against these results to manufacture a pass.
