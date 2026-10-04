# Stage 3B — Multi-Timeframe Broker-Correct Discovery

## Authorization
User authorized wider mechanism search under broker-correct fills; higher timeframes allowed if M5 insufficient.

## Contract
- LONG ASK/BID, SHORT BID/ASK, no 0.085R
- Gates: val PF>1.6, val six-block>1.0, test PF≥1.0, test block≥1.0
- Trade counts: M5/M15 ≥200; H1 ≥80 (sample-size only; PF gates unchanged)

## Search space
Pairs: 13 FX · TF: M5, M15 (resampled), H1 (resampled)  
Families: RSI, EMA pullback, Donchian, z-score, MACD cross  
Stops: 1.0/1.5/2.0 ATR × trail 0.5/0.75/1.0

## Result
**Selected: 0**

No combination passed all frozen gates.

### Closest near-misses
| Pair | TF | Side | Family | Val PF | Val N | Test PF |
|------|-----|------|--------|--------|-------|---------|
| EURUSD | H1 | LONG | rsi_os | ~1.54 | 88 | ~1.34 |
| USDJPY | H1 | SHORT | rsi_ob | ~1.66 | 86 | ~1.15 |
| EURUSD | M15 | LONG | rsi_os | ~1.37 | 303 | ~1.16 |
| NZDJPY | M15 | SHORT | rsi_ob | ~1.42 | 136 | ~0.51 |
| GBPJPY | H1 | LONG | rsi_os | ~1.56 | 122 | ~0.72 |

Typical failure mode: validation PF approaches 1.5–1.7 on H1 with thin samples, then six-block or test-block collapses; M5 remains PF ≲ 1.1.

## Interpretation
Under broker-correct economics, simple single-indicator rules on M5–H1 do not clear the frozen research bar on these 5Y sets. Higher TF helps a little but does not produce a gate-passing candidate without lowering thresholds (which was not done).

## Production
`production_authorized = false`

## Artifacts
- `artifacts/stage3b_multitf/STAGE3B_REPORT.json`
- `scripts/stage3b_multitf_broker_correct_discovery.py`
