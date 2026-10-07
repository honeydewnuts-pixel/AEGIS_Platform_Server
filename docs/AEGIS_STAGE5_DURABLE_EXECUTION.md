# AEGIS Stage 5 — Durable Execution Queue

## Governance

```
production_authorized = false
```

V53.6, RSI9, Native, Generation 3 remain **unchanged** and **not** promoted.

Stage 5 only persists **already-authorized** execution requests so they survive API restart.

---

## Starting point

| Item | Value |
|------|--------|
| Baseline HEAD | `78de4d423bddab8954af38ee9e19ee05a9550579` |

---

## Problem addressed

In-memory pending queue was lost on API restart (fail-safe but operationally incomplete).

## Solution

Table: `aegis_execution_queue`

States: `PENDING` → `CLAIMED` → `ACKED` | `REJECTED` | `EXPIRED`

- Unique `signal_id`
- `FOR UPDATE` on claim/ack
- Abandoned `CLAIMED` leases expire after 120s → return to `PENDING`
- Unauthorized / research rows **never** inserted (`is_execution_authorized` gate)

## Dual path

1. Memory queue (fast path, same process)
2. Durable row (survives restart)
3. Poll: memory first; if empty, load from durable and hydrate memory
4. ACK: memory + durable terminal (idempotent)

## Authorization boundary

| Signal type | Durable enqueue |
|-------------|-----------------|
| controlled_demo_test + controlled_demo_authorized | Allowed |
| RSI9 / Native / V53 / transfer / research | **Blocked** |
| production_authorized without valid methodology | **Blocked** (current policy) |

## Crash windows

| Window | Behaviour |
|--------|-----------|
| After durable commit, before response | Row survives; Executor polls PENDING |
| Broker fill before ACK | Lifecycle + reconcile; durable ACK idempotent |
| ACK then crash | Terminal status; retry ACK idempotent |

## Risk

Risk reservation remains on lifecycle ACK path (Stage 3.3 shared session).  
Durable queue does **not** reserve risk by itself.

## Unknown broker positions

Stage 4 quarantine preserved: `unknown_broker_tickets`, not auto-adopted.

## Operator recovery

| Event | Action |
|-------|--------|
| API restart | Durable PENDING remains; Executor polls normally |
| Executor restart | Startup reconcile + poll durable/memory |
| Duplicate Executor | signal_id + claim lease + ACK idempotency |
| Network retry | Idempotent ACK |

## Migration

`0020_aegis_execution_queue` — additive table only.

## Limitations

1. Claim lease is best-effort single-executor; uniqueness is on `signal_id` + ACK idempotency.
2. Memory still used for low latency within one process.
3. Live VPS Demo remains a separate human gate.

## Explicit statement

```
production_authorized = false
V53.6 = unchanged
RSI9 = unchanged
Native = unchanged
Generation 3 = research-only / closed
```
