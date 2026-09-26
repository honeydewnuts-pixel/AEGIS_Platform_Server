# V31 / V53.6 Live Position Manager (Executor v2.18)

## Authority
**MT5 AEGIS_Executor v2.18** is the sole authority for live stop modification and time-exit closes of AEGIS-magic positions.

## Historical reference
`simulate_short` in `backend/app/rulebooks/evaluators/common.py`:
1. Stop if BidHigh >= stop  
2. R from BidClose; BE at +1R → stop = entry  
3. If BE: trail candidate = BidClose + 0.75 * ATR; tighten only  
4. TIME when held bars reach 72 (entry bar convention)

## v2.18 corrections
| Issue | Fix |
|-------|-----|
| 72-bar wall-clock | `CompletedM5BarsSinceEntry` via `iBarShift` (skips weekend clock) |
| BE marked without broker confirm | `ModifyPositionStopConfirmed` checks retcode + position SL |
| Global trail/maxHold only | Per-signal fields in state file |
| Invented risk after trail | Initial risk frozen from registration; incomplete state → skip |

## Live adaptations (not identical to cash-test)
| Historical | Live |
|------------|------|
| Entry next-bar AskOpen | Actual fill price |
| Cost 0.085R | Broker costs |
| Perfect Bid series | M5 rates + SYMBOL_BID |

## Demo checklist
1. Compile `windows-desktop/mq5/AEGIS_Executor.mq5` (**v2.18**) in MetaEditor.  
2. `EnablePositionManager=true`, `BaselineShortOnly=true`.  
3. Journal: `register SHORT`, `BE confirmed`, trail only when confirmed, `close TIME` after **72 completed M5 bars**.  
4. Restart with open short + delete state file → recovery path logs; no invented BE.  
5. Production authorization remains disabled.
