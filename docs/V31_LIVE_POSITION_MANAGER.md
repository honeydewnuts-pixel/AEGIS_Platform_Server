# V31 / V53.6 Live Position Manager (Executor v2.17)

## Authority
**MT5 AEGIS_Executor v2.17** is the sole authority for live stop modification and time-exit closes of AEGIS-magic positions. The server publishes entry signals + ATR metadata only.

## Historical reference
`simulate_short` in `backend/app/rulebooks/evaluators/common.py`:
1. Stop if BidHigh >= stop
2. R from BidClose; BE at +1R → stop = entry
3. If BE: trail candidate = BidClose + 0.75 * ATR; tighten only
4. TIME at max 72 bars

## Live adaptations (not identical)
| Historical | Live |
|------------|------|
| Entry next-bar AskOpen | Actual OrderSend fill price |
| Cost 0.085R | Broker spread/commission (not synthetic) |
| Bar-perfect Bid series | SYMBOL_BID + M5 rates |

Initial stop = **fill_price + 1.5 * ATR14** (from signal or EA Wilder).

## Inputs
- `EnablePositionManager=true`
- `BaselineShortOnly=true` (rejects BUY)
- `DefaultMaxHoldBars=72`

## Demo checklist
1. Compile `windows-desktop/mq5/AEGIS_Executor.mq5` in MetaEditor (v2.17).
2. Attach with server signals, multi-pair or chart.
3. On SELL fill: Journal shows `AEGIS PM register SHORT`.
4. At +1R: `AEGIS PM BE`.
5. Trail tightens only.
6. At 72 M5 bars: `AEGIS PM close TIME`.
7. Restart MT5: management continues from position + state file.
