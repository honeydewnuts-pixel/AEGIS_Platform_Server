# Stage 3 — Broker-Correct Discovery (Generation 2)

## Authorization
User-authorized Stage 3 discovery under broker-correct execution contract, separate from frozen V53.6.

## Contract
- LONG open ASK / close BID
- SHORT open BID / close ASK
- No universal 0.085R
- Next-bar entry, closed-bar signals
- Frozen gates: val n≥200, val PF>1.6, val six-block min PF>1.0; test PF≥1.0, test block≥1.0

## Families searched
SHORT: RSI overbought (7/9/14 × 65/70/75), EMA pullback short, z-score overbought  
LONG: RSI oversold, EMA pullback long, z-score oversold  
Stops: 1.0/1.5 ATR × trail 0.5/0.75; max hold 72; event throttle 12 bars

## Result
**Selected rulebooks: 0**

No pair/side/family combination passed the frozen gates under broker-correct fills.

### Best near-misses (by validation PF)

| Pair | Side | Family | Val PF | Val N | Test PF | Pass |
|------|------|--------|--------|-------|---------|------|
| EURUSD | LONG | zscore_os | ~1.06 | 988 | ~0.88 | No |
| USDJPY | LONG | rsi_os | ~0.95 | 1357 | ~1.09 | No |
| GBPUSD | LONG | rsi_os | ~0.92 | 809 | ~0.72 | No |
| EURJPY | LONG | rsi_os | ~0.89 | 304 | ~0.84 | No |
| USDCAD | SHORT | rsi_ob | ~0.87 | 338 | ~0.68 | No |

All others lower. Typical best PF remains **below 1.1** vs gate **>1.6**.

## Interpretation
Generation-1 RSI9/Native profitability was largely an artifact of incorrect Bid/Ask conventions. Under genuine broker economics, simple RSI/EMA/z-score families with ATR stop/trail do not clear the frozen research gates on these 5Y M5 sets.

## Production authorization
**false** for all Stage 3 outputs (none qualified).

## What was not done
- Thresholds were not lowered
- Failed Gen-1 books were not retuned to “pass”
- V53.6 historical reconstruction was not modified
- No production promotion

## Artifacts
- `artifacts/stage3_broker_correct/STAGE3_DISCOVERY_REPORT.json`
- `scripts/stage3_broker_correct_discovery.py`
