# AEGIS_Executor.mq5 v2.11

## Hardening (vs 2.10)

1. **ResolveBrokerSymbol** — maps AEGIS base (GBPUSD) → broker name (GBPUSD.r / m / # / Market Watch scan).
2. **Handled only after outcome** — success or permanent fail; transient (spread/requote) retries up to `MaxRetriesTransient`.
3. **ACK payload** — order_ticket, deal_ticket, position_ticket, retcode, volume, side, symbol.
4. **Fill modes** — only modes advertised by `SYMBOL_FILLING_MODE`; cycle on INVALID_FILL.

## Modes

- ChartOnly / MultiPair (same AccountId + ApiKey)
- One AEGIS position **per symbol** (magic filter)

## First test

UseServerSignals=true, UseLocalFileFallback=false, explicit SymbolsList.
