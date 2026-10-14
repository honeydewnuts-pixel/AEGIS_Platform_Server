# USDCHF Baseline Reproduction Report

**Date:** 2026-10-14  
**Main base:** `f546af71b88b250f7a30d6614d74b6d818505177`

---

## 1. Dataset identity

| Field | Value |
|-------|--------|
| Name | `USDCHF_M5_BIDASK_5Y.csv` |
| Manifest bytes | 38,311,813 |
| SHA-256 | `f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97` |
| Rows (prior audit) | 373,551 |
| Range (prior audit) | 2021-09-15 23:00 UTC → 2026-09-15 23:00 UTC |
| Present in this clone | **NO** |

Prior note (`research/instruments/USDCHF/CHECKPOINT.md`): **484** intervals with gap **&gt; 5 minutes**; no duplicate/null issues reported in audited columns.

---

## 2. Irregular five-minute intervals (484)

**Classification:** Previously audited; **not re-counted this session** (source CSV absent).

**Most plausible explanation (hypothesis pending re-audit on restored file):** normal FX session closures / weekend gaps / holiday gaps producing Δt ≠ 300s between consecutive M5 stamps — not necessarily corruption.

**Materiality:** Prior checkpoint stated gaps observed without duplicate/null column issues. Impact on individual signals requires bar-level re-scan after restore. Do not delete or overwrite the original file; any cleaned series must be a **new artifact** with its own hash.

---

## 3. Reproduction vs stored ledger

From `artifacts/v53_6_verification/USDCHF_V53_6_REPRODUCTION_SUMMARY.json` and local recompute of CSVs:

| Metric | Legacy path | Bid/Ask-embedded path |
|--------|-------------|------------------------|
| Trades | 4957 | 4957 |
| PF | ≈ 2.3265 | ≈ 2.6532 |
| Avg R | ≈ 0.573 | ≈ 0.658 |
| Total R | ≈ 2838.6 | ≈ 3259.9 |
| Matched event_i | 4957/4957 | 4957/4957 |

**REPRODUCTION VERIFIED** = match to **stored operational ledger**, not independent original research provenance.

Mean per-trade R difference bidask−legacy ≈ **0.085**, consistent with documented legacy cost separation.

---

## 4. Preliminary figures (3401 / PF 2.552 etc.)

Those training/validation split figures from earlier discussion are **not re-derived** in this run (no source CSV / split scripts executed). Treat as **unverified historical references** until recomputed from restored data.

Rulebook qualification block in summary JSON (validation PF 2.387, final test PF 2.375, six-block min 1.953) refers to the **historical reconstruction qualification path**, with Final Test **locked** — not a live promotion ticket.

---

## 5. Broker-realistic vs reconstruction

| Model | Result in repo evidence |
|-------|-------------------------|
| Ledger-matched V53.6 reconstruction | High PF (see above) |
| Stage 3 broker-correct **search** on multi-pair | **0 winners** |
| RSI9 independent corrected SHORT fills | **Invalidated** (~0.5 PF class outcomes in audit docs) |

**Conclusion:** Matching the internal V53.6 ledger does **not** establish a new tradable Rulebook under the Stage 3 broker-correct discovery gates. Discovery search under those gates already failed to select any candidate.

---

## 6. What could not be done this session

- Re-hash source CSV (file missing).  
- Re-enumerate 484 gaps.  
- Re-run bar engine with alternate side conventions.  
- Produce new per-trade files from raw OHLC.

**Blocker:** Restore Bid/Ask research datasets with SHA verification.
