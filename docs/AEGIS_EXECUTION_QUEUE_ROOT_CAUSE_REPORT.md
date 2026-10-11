# AEGIS Execution Queue Root-Cause Report

**Signal under investigation:** `9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b`  
**Account:** `ACC-1987D3D2E6`  
**Symbol / side / volume:** EURUSD / SELL / 0.01  
**Methodology:** `controlled_demo_test`  
**Observed status (operator historical branch):** PENDING, attempt_count=0, tickets null  

**Main HEAD inspected:** `f546af71b88b250f7a30d6614d74b6d818505177`

## 1. Record location — production vs recovery branch

| Question | Status |
|----------|--------|
| Exists on Neon historical/recovery branch | **Operator-verified** (one queue row on observed historical branch) |
| Exists on current **production** branch | **UNVERIFIED** by Builder (no production DB session) |
| Same physical row | **INCONCLUSIVE** until production SELECT by `signal_id` |

**Required operator query (production branch, SELECT-only):**

```sql
SELECT signal_id, account_id, symbol, side, volume, status,
       production_authorized, controlled_demo_authorized,
       claimed_at, attempt_count, created_at, updated_at
FROM aegis_execution_queue
WHERE signal_id = '9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b';
```

Do **not** UPDATE/DELETE/requeue this row during diagnosis.

## 2. Creation path (source)

Created by **`POST /api/demo-monitor/controlled-test-signal`** (`demo_monitor_router.publish_controlled_test_signal`):

- Sets `methodology=controlled_demo_test`, `rule_name=controlled_demo_test`
- `production_authorized=false`, `controlled_demo_authorized=true`
- Publishes to in-memory executor signal service **and** durable enqueue via `DurableExecutionQueueService.enqueue`

This matches operator fields. It is an **engineering controlled-demo** signal, not V53.6 / RSI9 / Native.

## 3. Claim / execution / ACK (source + prior live evidence)

From prior Stage 6.2 diagnostics (same signal_id) when production was queried:

- Durable status remained **PENDING**, `claimed_at=null`, `attempt_count=0`
- `GET /api/executor/pending` could return the payload with `has_signal=true`
- `authorized` is computed via `ExecutorSignalService.is_execution_authorized` which **does** allow path B: `controlled_demo_authorized` + methodology `controlled_demo_test`

**Why still PENDING with attempt_count=0 (most likely, evidence-based):**

1. **Executor never successfully claimed** the durable row (claim runs on durable pending path when Executor polls and server delivers).
2. Possible contributing factors (must not be assumed without VPS Experts log):
   - Executor in **CHART_ONLY** on a chart that was not polling that symbol path as expected
   - Executor not attached / UseServerSignals false / wrong AccountId
   - HTTP failures treated as empty signal
   - Process restart before claim
3. **No OrderSend evidence** for this signal in prior diagnostics.
4. **No ACK** — consistent with never claimed / never filled.

**Not proven:** broker rejection (OrderSend never shown).  
**Not proven:** automatic expiry (still PENDING, not EXPIRED/SUBMISSION_UNCERTAIN).

## 4. Authorization gates

| Gate | Behavior |
|------|----------|
| Enqueue | Requires `is_execution_authorized` — controlled_demo path allowed |
| Production strategies | Blocked unless `production_authorized` and non-research methodology |
| RSI9 / Native / V53.6 research | Not promoted by this path |
| Live `authorized` field | Uses same `is_execution_authorized` |

**Do not execute this stale signal** as an acceptance test. Create a **new** controlled-demo signal only under explicit owner authorization after Executor presence is healthy.

## 5. Duplicate execution / stale pending

- Claim-on-deliver + lease → SUBMISSION_UNCERTAIN (no auto-redeliver) on main design.
- PENDING can remain indefinitely until claimed, superseded, or expired by newer enqueue rules.
- **Gap:** long-lived PENDING without operator alert is a monitoring gap, not automatic execution.

## 6. Conclusions

| Finding | Classification |
|---------|----------------|
| Record is controlled_demo engineering signal | **VERIFIED** (source + fields) |
| Still unclaimed in historical observation | **VERIFIED** (operator) |
| Production current state | **UNVERIFIED** |
| Root cause of non-execution | **Executor did not claim** (best supported); exact VPS reason **UNVERIFIED** without Experts log |
| Safe next step | Read-only production SELECT; Executor presence check; **do not** force this UUID |

## 7. Explicitly not done

No claim, ACK, reject, expire, requeue, or broker order for this signal.
