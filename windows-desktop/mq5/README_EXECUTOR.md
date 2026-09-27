# AEGIS_Executor.mq5 v2.19 (current)

Authoritative source: `windows-desktop/mq5/AEGIS_Executor.mq5`  
Synced copies: `windows-desktop/AEGIS_Executor.mq5`, `release/desktop/AEGIS_Executor.mq5`  
`#property version` and `OnInit` log: **2.19**

## What v2.19 includes

- MultiPair / ChartOnly execution modes
- Server-polled signals (`/api/executor/pending-batch`) + ACK
- Broker-symbol resolution (shared contract with OHLC Feed — see `SYMBOL_RESOLUTION_CONTRACT.md`)
- 64-bit tickets, position ticket discovery, restart-safe `AEGIS <signal_id>`
- Partial-fill policy (ACCEPT or one residual with inherited SL/TP)
- **Position manager (short baseline):** initial stop from fill + 1.5×ATR, break-even at +1R (broker-confirmed), trail 0.75×ATR (tighten only), **72 completed M5 holding bars** TIME exit
- Short-only baseline when `BaselineShortOnly=true`

See `docs/V31_LIVE_POSITION_MANAGER.md` for historical vs live exit alignment.

## Partial-fill policy

| Setting | Behaviour |
|---------|-----------|
| **PARTIAL_ACCEPT** (recommended for first demo) | First `DONE` / `DONE_PARTIAL` completes the signal. ACK reports actual filled volume. |
| **PARTIAL_COMPLETE_REMAINDER** | After partial, exactly one residual `OrderSend` with same SL/TP. ACK reports total filled. |

## Demo inputs

```
ExecMode = MultiPair
SymbolsList = GBPUSD,EURUSD,USDJPY
UseServerSignals = true
UseLocalFileFallback = false
OnePositionPerSymbol = true
EnablePositionManager = true
BaselineShortOnly = true
DefaultMaxHoldBars = 72
Lots = 0.01
PollSeconds = 5
PartialFillPolicy = PARTIAL_ACCEPT
```

## Historical release notes (earlier builds)

| Version | Note |
|---------|------|
| v2.10–v2.14 | Multi-pair foundation, symbol resolve, ACK hardening |
| v2.15–v2.16 | Architecture freeze for early VPS demo (no PM bar-count fix) |
| v2.17–v2.18 | Position manager introduced; wall-clock hold then bar-count |
| **v2.19** | **Current** — 72-bar inclusive window aligned with `simulate_short` |

Do not use older mq5 files from archives when deploying; compile **v2.19** only.
