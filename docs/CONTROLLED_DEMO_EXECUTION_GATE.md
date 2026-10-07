# Controlled Demo Execution Gate

## Purpose

Engineering test of the MT5 Demo mechanical path only. **Not** a strategy test.
**Not** production authorization.

## Why `controlled-test-signal` previously failed

`POST /api/demo-monitor/controlled-test-signal` published with
`production_authorized=False` (default).  
`ExecutorSignalService.get_pending` requires `is_execution_authorized`, which
previously accepted **only** `production_authorized is True`.

Therefore the Executor polled an empty authorized queue.

## New gate (this change)

Separate flag: `controlled_demo_authorized=True` on the **signal payload only**.

Allowed through pending filter **only when**:

- `controlled_demo_authorized is True`
- `methodology == controlled_demo_test` (or rule_name contains `controlled_demo`)
- methodology/rule does **not** contain: rsi9, native, stage3b, research, transfer, v53, v31

`production_authorized` remains **False** on these signals and globally.

## Safety properties

- Explicit opt-in per publish call
- Demo engineering methodology only
- Cannot authorize RSI9 / Native / V53.6 / research
- Does not set platform `PRODUCTION_AUTHORIZED`
- Auditable via signal payload fields
- One signal per symbol (queue key); ACK clears it

## Human-controlled Demo procedure

1. Confirm VPS: Feed + Executor attached, account `ACC-…`
2. With API key bound to that account:
   ```http
   POST /api/demo-monitor/controlled-test-signal
   {"account_id":"ACC-…","symbol":"EURUSD","side":"SELL","volume":0.01}
   ```
3. Confirm `GET /api/executor/pending-batch?account_id=…&symbols=EURUSD` returns `has_signal=true`
4. Observe Executor OrderSend on **Demo** only
5. Verify ACK → lifecycle → risk → close → release
6. Do **not** enable strategy autonomous trading

## Production

`production_authorized` remains **FALSE** until separate explicit authorization.
