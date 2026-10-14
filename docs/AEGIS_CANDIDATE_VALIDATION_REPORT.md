# Candidate Validation Report

**Date:** 2026-10-14  
**Gates used (Stage 3 artifact):** val_min_trades=200, val_min_pf=1.6, val_min_block_pf=1.0, test_min_pf=1.0, test_min_block_pf=1.0  
**Source:** `artifacts/stage3_broker_correct/STAGE3_DISCOVERY_REPORT.json`

---

## Summary

| Gate outcome | Count |
|--------------|-------|
| Stage 3 selected | **0** |
| Stage 3B selected | **0** |
| Eligible for integration proposal | **0** |

---

## Stage 3 near-misses (best per symbol) — all REJECTED

Best observed validation PF among near-misses is still **below 1.6** for all symbols except none cleared the full gate set. Highest listed val_pf examples remain sub-threshold or fail blocks (see experiment register).

USDJPY LONG rsi_os showed test_pf ≈ 1.088 in the near-miss table but did not appear as a selected winner under the full Stage 3 selection logic (`n_selected=0`).

---

## V53.6 USDCHF

| Status label | Meaning |
|--------------|---------|
| REPRODUCTION VERIFIED | Matches stored ledger |
| DISCOVERY ONLY / RESEARCH ONLY | Not production |
| Independent executable promotion | **Not authorized**; prior broker-correct concerns documented |

---

## RSI9 / Native

| Stream | Decision |
|--------|----------|
| RSI9 | REJECTED / INVALIDATED under broker-correct (USDCHF) |
| Native LONG | NOT QUALIFIED under broker-correct |

---

## Final Test

**Protected / locked** for champion selection per USDCHF checkpoint. This assignment did **not** consume Final Test for tuning.

---

## Promotion decision

**NO PROMOTION.**  
No candidate reaches **ELIGIBLE FOR INTEGRATION PROPOSAL**.
