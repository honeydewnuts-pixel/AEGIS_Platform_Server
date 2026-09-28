# AEGIS_OHLC_Feed.mq5 v2.05

# AEGIS_OHLC_Feed.mq5 v2.02

See `SYMBOL_RESOLUTION_CONTRACT.md` — resolver must match Executor.

## First demo inputs

```
InpMode = MultiSymbol
InpSymbolsList = GBPUSD,EURUSD,USDJPY
InpForceTF = PERIOD_M5
InpTimerSec = 30
```

Empty `InpSymbolsList` → chart symbol only (never entire Market Watch).


## v2.04
Posts  and  (SymbolInfo contract data).
Inputs: , .


## v2.05
- Posts `available_margin_usd` from `AccountInfoDouble(ACCOUNT_MARGIN_FREE)` with equity (never substitutes equity).
- Posts true `margin_per_lot` via `OrderCalcMargin(..., 1.0 lot)` (not min-lot margin).
- Server uses these values for fail-closed position sizing.
