# Corrections Log — Market-State Transitions

**Date:** 2026-10-19  
**Scope:** Integrity closeout only; no re-analysis of primary hypothesis.

## Materiality “15/13” claim

**Finding:** No committed artefact contains “15/13”.

| Source | n_mat_ge1 |
|--------|----------:|
| `outputs/market_state_summary.json` | **5** |
| `outputs/instrument_state_summary.csv` (count materiality≥1) | **5** |
| Independent recalculation | **5** |
| Findings report (committed) | **5/13** |

**Root cause:** Prose-only inconsistency in an external/handover narrative (not in Git). Likely a typographical transposition of “5/13”.

**Correction:** Authoritative count is **5 of 13** instruments with `|mean_abs_ELEVATED − mean_abs_B_HIGH| / median_spread ≥ 1`.

**Formula (from script):**
```
materiality = abs(diff) / med_spread
diff = mean(abs_disp | ELEVATED) − mean(abs_disp | B_HIGH)
med_spread = median(AskClose − BidClose) over development rows
```

No source-code or output-file repair required for this metric.
