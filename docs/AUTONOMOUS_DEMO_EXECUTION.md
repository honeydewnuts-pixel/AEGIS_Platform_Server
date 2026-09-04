# AEGIS V3 Autonomous Demo Execution

## Root cause fixed

The previous checkpoint had two independent blockers:

1. `trading_router.py` rejected the `demo` plan at `/api/trading/market-order`.
2. The V3 screenshot-analysis route returned BUY/SELL but never enqueued a market-order job.
3. The Windows worker imported `MT5Adapter`, but `backend/app/services/adapters/mt5_adapter.py` was missing from the checkpoint, so the execution worker could not actually perform orders.

## New behavior

`POST /aegis/analyze`:
1. Extracts V3 screenshot state.
2. Gets synchronized M1 OHLC from the connected MT5 terminal.
3. Evaluates the V3 rule engine.
4. If BUY/SELL, and the account is a demo plan with execution enabled, submits `market_order` to the account's Windows MT5 worker.
5. Uses Redis event idempotency keyed by account + symbol + M1 candle + signal + rule.
6. Uses the existing daily trade quota.
7. Returns execution status and broker result in the analysis response.

## Safety

This checkpoint is DEMO-ONLY for autonomous execution. The MT5 adapter verifies `ACCOUNT_TRADE_MODE_DEMO` after login and refuses REAL accounts.

The system does not use a separate broker REST/HTTP trading API. Orders are sent through the connected MT5 terminal using the MetaTrader5 Python package on Windows.

Default autonomous demo volume is 0.01 lots and is configurable with `AUTONOMOUS_DEFAULT_VOLUME`.


## Single-executor policy


The Android application no longer auto-clicks the MT5 mobile UI when a BUY/SELL
signal arrives. Server-side V3 execution through the Windows MT5 worker is the
single automatic execution path. This prevents duplicate orders when the same
analysis result reaches the phone and server at nearly the same time.
