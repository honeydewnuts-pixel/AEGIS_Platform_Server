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
