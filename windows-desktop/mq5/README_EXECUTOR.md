# AEGIS_Executor.mq5 v2.10

## Modes

| Mode | Behaviour |
|------|-----------|
| **ChartOnly** (default) | Polls pending for `_Symbol` only. Attach one EA per chart/pair. |
| **MultiPair** | One EA polls `/api/executor/pending-batch` for many symbols (list or Good universe). |

Same **AccountId** + **ApiKey** on every instance. Positions are **one AEGIS magic position per symbol**, not account-wide.

## Filling mode

Uses symbol `SYMBOL_FILLING_MODE`: IOC → FOK → RETURN, with retry on invalid fill.

## Multi-pair setup (Option A — safest)

Attach Feed + Executor (ChartOnly) on each chart:

```
GBPUSD M5 → Feed + Executor
EURUSD M5 → Feed + Executor
```

## Multi-pair setup (Option B — one Executor)

1. ExecMode = MultiPair  
2. SymbolsList empty → server Good universe, or set `GBPUSD,EURUSD,USDJPY`  
3. Still run **OHLC Feed on each symbol chart** (or one feed per symbol).  
4. Symbols must exist in Market Watch.

## Server gates

Only **Good + tradeable** registry instruments are published/polled. V2-OPT-only pairs are blocked.

## WebRequest

Allow: `https://aegis-api-0z1p.onrender.com` (your API host).
