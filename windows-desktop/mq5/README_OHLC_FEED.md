# AEGIS_OHLC_Feed v2.00

## Modes

| Mode | Behaviour |
|------|-----------|
| **ChartOnly** (default) | Streams `_Symbol` only — same as V1.00 |
| **MultiSymbol** | Streams `InpSymbolsList` (or Market Watch if empty), capped by `InpMaxSymbols` |

## Clean VPS layout

```
MT5
├── AEGIS_OHLC_Feed v2.00   MultiSymbol → GBPUSD,EURUSD,...
└── AEGIS_Executor v2.10    MultiPair   → same symbols
```

Same AccountId + ApiKey. Endpoint remains `POST /api/mt5/ohlc/stream` (one request per symbol per cycle).

## Inputs

- InpServerUrl, InpApiKey, InpAccountId  
- InpMode, InpSymbolsList, InpBars, InpTimerSec, InpMaxSymbols  
- InpForceTF: PERIOD_CURRENT or force M5  

## WebRequest

Allow your AEGIS API host in Expert Advisors options.

## Symbol suffixes

Feed posts `symbol` as **base** (GBPUSD) and `symbol_broker` as the MT5 name (GBPUSD.r). Server keys streams by base so Executor MultiPair always matches.
