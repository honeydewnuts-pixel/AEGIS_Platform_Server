# Rulebook V1.4 Preregistration — BB17/BB34 Band Transition and Swing Reversal
**Date:** 2026-10-25  
**Timeframe:** M15  
**production_authorized=false · execution_authorized=false**

## Frozen before evaluation
- Spec: AEGIS RULEBOOK V1.4 as supplied (BB17/BB34, swing confirmation, 2-candle persistence)
- ε_t = max(0.1 × ATR_t, 2 × TickSize)
- ATR(14) Wilder
- BB period 17 and 34, multiplier 1.0, close, std ddof=0 (population) — frozen convention
- Initial stop 2.0 × ATR_signal; trail activate 1R; trail 2.5 × ATR_current
- Max hold 48 elapsed hours
- Risk 0.5% equity (price-unit risk proxy if contract specs unavailable — labeled)
- Partition 60/20/20 chronological; Class A Bid/Ask only for qualification
- Entry next-bar Ask (BUY) / Bid (SELL)

## Gates (predeclared)
- Val trades ≥ 30, val PF ≥ 1.2
- Test trades ≥ 20, test PF ≥ 1.1
- Class A required
- TM fully specified (this rulebook)
- Missing contract specs → report price-unit results; do not claim account-currency qualification

## Non-goals
- No parameter search after seeing results
- No production authorization from historical PASS
