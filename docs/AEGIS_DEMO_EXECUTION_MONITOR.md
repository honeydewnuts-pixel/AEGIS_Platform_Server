# AEGIS Demo Execution Monitor

## Purpose

Mobile HTTP 200 + HOLD does **not** prove that MT5 received or filled an order.
This monitor exposes every stage between market data and broker ACK so demo validation does not rely on screenshots alone.

## Stages

1. **mt5_connection** — OHLC streams present / stale / missing  
2. **ohlc_feed** — last symbol, TF, bar count  
3. **signal_generation** — `NO_SIGNAL` vs `SIGNAL_PENDING`  
4. **signal_queue** — pending queue depth  
5. **executor** — last `pending-batch` poll age  
6. **order_submission** — last fill or reject  
7. **acknowledgement** — server recorded Executor ACK  
8. **notifications** — pointer to inbox API  

## API

```
GET /api/demo-monitor/{account_id}
GET /api/demo-monitor/{account_id}/events
GET /api/demo-monitor/{account_id}/signal/{signal_id}
POST /api/demo-monitor/controlled-test-signal
```

All require API key. Account isolation via `require_account_match`.

### Controlled test signal (Test 3)

```json
POST /api/demo-monitor/controlled-test-signal
{
  "account_id": "ACC-...",
  "symbol": "GBPUSD",
  "side": "SELL",
  "volume": 0.01
}
```

Enqueues a pending signal for the Executor. Does **not** bypass broker risk or production authorization.
Attach Executor with `UseServerSignals=true` and confirm ACK appears in the monitor.

## Acceptance tests

| Test | How to verify |
|------|----------------|
| 1 Market data | Monitor `mt5_connection=CONNECTED`, freshest age low |
| 2 Signal generation | Strategy path or controlled-test-signal → `SIGNAL_PENDING` |
| 3 Executor | Poll age recent; pending clears after ACK |
| 4 Demo order | `order_submission=TRADE_FILLED` + matching MT5 ticket |

## Overall codes

| Code | Meaning |
|------|---------|
| `NO_SIGNAL` | Pipeline OK; strategy has no entry |
| `MT5_DISCONNECTED` | No OHLC streams |
| `OHLC_STALE` | Data too old |
| `EXECUTOR_NOT_POLLING` | Queue has signal; EA silent |
| `SIGNAL_AWAITING_EXECUTION` | Queued; Executor should poll |
| `ORDER_REJECTED` | Last ACK was failure |
| `TRADE_FILLED` | Recent successful ACK |

## Non-goals

- Does not force strategy trades for cosmetics  
- Does not change V53.6 entry/exit rules  
- Does not enable production authorization  
