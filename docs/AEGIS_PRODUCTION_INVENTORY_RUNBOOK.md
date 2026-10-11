# AEGIS Production Inventory Runbook (Read-Only)

**Main HEAD this runbook was written against:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Database:** Neon **production** branch only (not recovery/PITR branches).  
**Mode:** SELECT-only. Never paste connection strings or API keys into chat.

## Safety

1. Open Neon SQL Editor on the branch named **production**.  
2. Confirm the branch name in the UI before running anything.  
3. Run only the SELECT statements below.  
4. Do not run UPDATE, DELETE, INSERT, DROP, TRUNCATE, or migrations.  
5. Save results locally (counts and non-secret identifiers only).

Optional session guard (if your client supports it):

```sql
SET default_transaction_read_only = on;
```

---

## Q1 — Alembic revision

```sql
SELECT version_num FROM alembic_version;
```

**Establishes:** Which migration head production has applied.  
**Does not establish:** Application Git SHA or Render deploy identity.

Expected if aligned with current main: `0023_lifecycle_open_risk_applied`.

---

## Q2 — Exact pending EURUSD controlled-demo signal

```sql
SELECT
  signal_id,
  account_id,
  symbol,
  side,
  volume,
  status,
  methodology,
  rule_name,
  production_authorized,
  controlled_demo_authorized,
  attempt_count,
  claimed_at,
  claim_token IS NOT NULL AS has_claim_token,
  position_ticket,
  order_ticket,
  deal_ticket,
  ack_ok,
  created_at,
  updated_at
FROM aegis_execution_queue
WHERE signal_id = '9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b';
```

**Establishes:** Whether that UUID still exists on **production** and its current status.  
**Does not establish:** Broker fill, Executor polling, or that historical-branch data is current.  
**Do not:** claim, ACK, expire, or requeue this row.

---

## Q3 — Queue counts by status

```sql
SELECT status, count(*) AS n,
       min(created_at) AS oldest,
       max(created_at) AS newest
FROM aegis_execution_queue
GROUP BY status
ORDER BY status;
```

**Establishes:** How many rows sit in PENDING / CLAIMED / SUBMISSION_UNCERTAIN / ACKED / REJECTED / EXPIRED.  
**Does not establish:** Whether CLAIMED rows have live broker positions.

---

## Q4 — Unresolved / attention queue rows

```sql
SELECT signal_id, account_id, symbol, side, status,
       methodology, attempt_count, claimed_at, created_at
FROM aegis_execution_queue
WHERE status IN ('PENDING', 'CLAIMED', 'SUBMISSION_UNCERTAIN')
ORDER BY status, created_at;
```

**Establishes:** Work that is not terminal.  
**Does not establish:** Safe to execute any of these rows.

---

## Q5 — Lifecycle row counts and states

```sql
SELECT state, count(*) AS n
FROM aegis_position_lifecycle
GROUP BY state
ORDER BY state;
```

**Establishes:** Lifecycle distribution on production.  
**Does not establish:** Match to MT5 open positions (requires broker-side list).

---

## Q6 — open_risk_applied distribution

```sql
SELECT
  CASE
    WHEN open_risk_applied IS NULL THEN 'NULL'
    WHEN open_risk_applied IS FALSE THEN 'FALSE'
    WHEN open_risk_applied IS TRUE THEN 'TRUE'
  END AS applied_state,
  count(*) AS n
FROM aegis_position_lifecycle
GROUP BY 1
ORDER BY 1;
```

**Establishes:** How many rows are historical-unknown (NULL), explicitly unapplied (FALSE), or applied (TRUE).  
**Does not establish:** Correctness of `open_risk_usd` totals.  
**Rule:** Do not auto-recover NULL rows.

---

## Q7 — Portfolio open risk

```sql
SELECT account_id, open_risk_usd, status
FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0
ORDER BY open_risk_usd DESC;
```

**Establishes:** Non-zero portfolio open-risk allocations by account.  
**Does not establish:** That each dollar maps 1:1 to an open broker ticket without MT5 comparison.

---

## Q8 — Emergency stop

```sql
SELECT key, value, updated_at, updated_by
FROM aegis_operational_control
WHERE key = 'emergency_stop';
```

**Establishes:** Durable stop flag if a row exists (`value` typically `"true"` / `"false"`).  
**Does not establish:** Transient in-memory stops or VPS-side kills.  
Empty result may mean never set (treat as unknown until confirmed via admin API).

---

## Q9 — Executor presence (DB view of heartbeat)

```sql
SELECT account_id, client_type, executor_version, execution_mode,
       last_symbol, last_seen_at
FROM aegis_executor_presence
ORDER BY last_seen_at DESC NULLS LAST;
```

**Establishes:** Last durable heartbeat rows written by `POST /api/executor/heartbeat`.  
**Does not establish:** Successful OrderSend or that CHART_ONLY is correct for multi-pair intent.

---

## After collecting results

1. Label each result **production** + UTC time.  
2. Compare Q2 to historical-branch notes (same UUID or missing).  
3. Proceed to Executor-presence API check (separate runbook).  
4. Do **not** authorize a new controlled-demo signal until presence is healthy and owner approves.
