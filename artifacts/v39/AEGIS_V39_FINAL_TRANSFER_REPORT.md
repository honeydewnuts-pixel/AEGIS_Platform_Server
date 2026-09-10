# AEGIS V39 — Frozen Transfer Update

Scope: USDCHF 36M, NZDUSD 36M, USDJPY 24M Bid+Ask.
Frozen rulebooks: V31 and V35. No rule changes and no gate relaxation.

## Decisions
- USDCHF V31: numerical gates PASS (Validation 430 / PF 2.2053; Final Test 460 / PF 2.5187).
- USDCHF V35: numerical gates PASS (Validation 367 / PF 2.8194; Final Test 335 / PF 3.3881).
- NZDUSD V31: numerical gates PASS (Validation 439 / PF 2.1452; Final Test 483 / PF 2.4826).
- NZDUSD V35: numerical gates PASS (Validation 358 / PF 2.6192; Final Test 378 / PF 3.3056).
- USDJPY V31: FAIL (Validation 282 / PF 1.3023; Final Test 271 / PF 1.2616).
- USDJPY V35: FAIL (Validation 223 / PF 1.6849; Final Test 203 / PF 1.2899).

The USDCHF/NZDUSD passes are numerical gate passes, not yet formal Rulebook Library promotion. Audit pass remains required: lineage, causality/leakage, execution, independent reproduction, and final qualification matrix.

USDJPY uses 24 months of Bid+Ask data (Jan 2023-Dec 2024). 2025 Bid-only data is excluded from strict execution transfer.
