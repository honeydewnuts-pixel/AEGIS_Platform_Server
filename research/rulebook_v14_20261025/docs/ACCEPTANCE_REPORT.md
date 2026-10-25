# Rulebook V1.4 — Acceptance Report
**BB17/BB34 Band Transition and Swing Reversal (M15)**  
**Branch:** research/rulebook-v14-bb17-bb34-20261025  
**production_authorized=false · execution_authorized=false**

## Conclusion
**Implementation and causal evaluation complete. No instrument PASSED predeclared gates.**

The strategy generates ~970–1120 trades per Class A instrument over ~5Y M15 (resampled from M5 Bid/Ask), but validation and final-test profit factors are **below 1.2 / 1.1** on every instrument. Several show val_pf > 1 briefly (EURJPY 1.13, GBPUSD 1.09) but **test_pf remains < 1.1**.

## Implementation notes
- Causal swing confirmation at p+2
- BB17/BB34 with std **ddof=0** (population), multiplier 1.0
- ATR(14) Wilder
- ε_t = max(0.1×ATR, 2×tick)
- Next-bar Ask/Bid entry; stop-first / gap worse-open
- Risk sizing: equity × 0.5% / stop distance (**price-unit proxy**; not verified contract lot sizing)
- Spread via Bid/Ask; commission/slippage/swap **not** added (disclosed)

## Results summary (13 Class A)

| Symbol | Gate | Val PF | Test PF | Full PF | Trades |
|--------|------|-------:|--------:|--------:|-------:|
| AUDUSD | FAIL | 0.86 | 0.55 | 0.74 | 1015 |
| EURCHF | FAIL | 0.43 | 0.28 | 0.44 | 1045 |
| EURGBP | FAIL | 0.44 | 0.60 | 0.52 | 1090 |
| EURJPY | FAIL | 1.13 | 0.76 | 0.77 | 981 |
| EURUSD | FAIL | 0.73 | 0.83 | 0.75 | 973 |
| GBPJPY | FAIL | 0.80 | 0.59 | 0.71 | 1022 |
| GBPNZD | FAIL | 0.38 | 0.37 | 0.45 | 1119 |
| GBPUSD | FAIL | 1.09 | 0.84 | 0.91 | 983 |
| NZDCHF | FAIL | 0.15 | 0.29 | 0.40 | 1041 |
| NZDJPY | FAIL | 0.59 | 0.49 | 0.57 | 1052 |
| USDCAD | FAIL | 0.70 | 0.68 | 0.80 | 974 |
| USDCHF | FAIL | 0.52 | 0.71 | 0.65 | 1019 |
| USDJPY | FAIL | 0.87 | 0.98 | 0.88 | 981 |

**PASS count: 0 / 13**

## Classification
**Non-transfer / FAIL** under frozen V1.4 rules and preregistered gates.

## Limitations
- State machine is a faithful engineering interpretation of the sequential Rulebook; subtle sequencing ambiguities (when progression is “established”) may differ from a future reference implementation.
- Final 20% of 5Y data is previously exposed in AEGIS research.
- Account-currency / broker lot constraints not verified.
- No parameter optimization performed after results.

## Safety
No production merge, deploy, orders, EA changes, or authorization elevation.

## Decision
Do **not** promote V1.4. Do **not** retune ε, persistence, or ATR multiples against these folds to force a pass. Treat as a documented negative causal evaluation of the supplied specification.
