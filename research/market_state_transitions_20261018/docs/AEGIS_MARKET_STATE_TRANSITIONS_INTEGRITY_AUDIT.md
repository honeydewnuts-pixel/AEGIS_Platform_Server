# Integrity Audit (Closeout Update 2026-10-19)

| Check | Status |
|-------|--------|
| 1. Prereg ordering and hash | **PASS** — bed4565 before e60526c; hash match |
| 2. Prereg vs implementation | **PARTIAL** — 50-bar percentile refresh not in prereg text |
| 3. Dataset integrity | **PASS** — 13-pair manifest present |
| 4. Past-only thresholds | **PASS** (tested); refresh schedule **PARTIAL** vs continuous expanding wording |
| 5. State timing | **PASS** — boundary tests |
| 6. Look-ahead protection | **PASS** — rv past window; outcomes after bar i |
| 7. Prefix invariance | **PASS** — synthetic test |
| 8. Forecast horizon H*=12 | **PASS** |
| 9. Overlapping outcomes | **PARTIAL** — thin step 12; not full block bootstrap |
| 10. Bootstrap validity | **PARTIAL** — fixed seed, N=1000; unpaired pools |
| 11. Multiple comparisons | **PASS** — primary contrast only confirmatory |
| 12. Exposed final 20% | **PASS** — labelled EXPOSED |
| 13. Baseline fairness | **PASS** — same rv feature, different cut |
| 14. Materiality “15/13” | **PASS** — false; true count **5/13** |
| 15. Reproducibility of counts | **PASS** — CSV/JSON/recalc agree |
| 16. Test coverage | **PASS** — 23/23 dedicated tests |
| 17. Headline interpretation | **PASS** — threshold refinement, not new mechanism |
| 18. OHLC limitations | **PASS** — disclosed; not liquidity |

**Headline decision unchanged:** RETAIN AS DESCRIPTIVE ONLY. No Rulebook.
