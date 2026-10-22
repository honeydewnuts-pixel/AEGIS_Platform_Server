# BB17/BB34 RSI Swing v2.1 — Signal Integrity Audit (2026-10-22)

production_authorized=false · execution_authorized=false

## Provenance
Rules from operator task text (late-reversal 8 conditions, early RSI, ddof=0, RBB on SMA7). PDF file still not in repo.

## Late reversal
Implemented in scripts/late_reversal_v21.py. Tests: 12 PASS / 0 FAIL.

## Early counts — EXACT MATCH
| Metric | Reported | Reproduced |
|--------|----------:|----------:|
| Eligible early | 167,412 | 167,412 |
| Bearish | 88,454 | 88,454 |
| Bullish | 78,958 | 78,958 |

## Target-state changes — EXACT MATCH (early-only)
| Metric | Reported | Reproduced |
|--------|----------:|----------:|
| Early-only machine | 64,084 | 64,084 |
| Early+late machine | — | 87,985 |
| Late eligible events | — | 46,833 |
| Conflicts early-only | 0 | 0 |
| Conflicts early+late | — | 191 |

Raw eligible > target changes because same-direction repeats are suppressed by the single-position state machine.

## Definitions
- eligible event = frozen conditions met
- signal = eligible at confirm/decision row
- target-state change = FLAT/LONG/SHORT transition
- trade = NOT counted (no cash model)

## Authorization
Unchanged. No merge, deploy, or production promotion.
