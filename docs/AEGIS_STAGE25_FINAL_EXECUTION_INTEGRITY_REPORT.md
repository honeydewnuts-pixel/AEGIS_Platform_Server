# AEGIS Stage 2.5 — Final Execution Integrity Report

**Starting HEAD:** `cead0ddce83d6debddfe05c47999506a0671e1e0`

## Delivered

1. Frozen V53.6 historical path unchanged (`simulate_short` AskOpen + BidHigh + optional 0.085R).
2. Separate broker-correct SHORT/LONG simulators (`simulate_short_broker_correct`, `simulate_long_broker_correct`).
3. Closed-bar isolation (`ohlc_bar_utils` + autonomous path).
4. Hard `production_authorized` fail-closed gate — research cannot reach Executor.
5. Publish lifecycle = `SIGNAL_QUEUED` (not position open).
6. `release_open_risk` on PortfolioRiskService.
7. RSI9/Native broker-correct requalification (prior run): all FAIL gates under corrected fills; USDCHF RSI9 remains INVALIDATED.
8. Structural V53.6 historical vs broker-correct probe: historical PF ~1.65 → broker-correct PF ~0.58.

## Production authorization

All research methods: **production_authorized = false**

## Limitations

Full V53.6 locked-event reproduction, 147-scenario cash matrix regeneration, and full Postgres CI remain incomplete / environment-limited.
