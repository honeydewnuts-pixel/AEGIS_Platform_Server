# AEGIS_OHLC_Feed.mq5 v2.01

Header and `#property version` are both **2.01**.

## Modes

- ChartOnly — chart symbol
- MultiSymbol — **requires explicit `InpSymbolsList`** for production (empty list falls back to chart only, not full Market Watch)

Posts `symbol` (base) + `symbol_broker` (MT5 name) to `/api/mt5/ohlc/stream`.

## Pair with Executor v2.11

One MultiSymbol feed + one MultiPair executor on the VPS.
