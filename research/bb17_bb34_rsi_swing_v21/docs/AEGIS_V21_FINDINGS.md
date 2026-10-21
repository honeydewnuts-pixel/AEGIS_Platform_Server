# BB17/BB34 RSI Swing Rulebook v2.1 — Research Findings

## Executive conclusion

Frozen v2.1 **signal dependency chain implemented and tested**. Critical corrections vs prior DBT V1: **ddof=0**, **RBB on SMA7(RSI9)** not RSI9. Signal research completed on 13 Bid/Ask M5 pairs. **No cash profitability claim.** Full operator PDF/reference file not present in repo; rules taken from task text.

| Metric | v2.1 (this study) |
|--------|------------------:|
| Eligible early reversals | **167,412** |
| Early bearish | 88,454 |
| Early bullish | 78,958 |
| Target-state changes | 64,084 |
| Conflicts (opposing same bar) | 0 |
| Unit tests | **12 PASS / 0 FAIL** |

Prior DBT V1 had ~183k eligible under **non-conformant** RBB-on-RSI9 + ddof=1 — those counts are **not** comparable as the same methodology.

## Authorization

production_authorized=false · execution_authorized=false
