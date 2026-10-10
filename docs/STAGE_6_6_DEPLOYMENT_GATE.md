# Stage 6.6F — Production Recovery Evidence & Deployment-Gate Closure

**Source checkpoint (main):** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Post-merge CI:** [38077295836](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38077295836) — **455 passed, 3 skipped**; docker-build success  
**Health-route on main:** YES (Stage 6.6E merged)  

**Overall:** READY FOR FURTHER EVIDENCE COLLECTION  
**Production deployment:** **BLOCKED** until backup/restore and production inventory are **VERIFIED** and separately reviewed.

This document does **not** authorize deploy, migration, EA install, or trading.

---

## 1. Source checkpoint (verified)

| Item | Status |
|------|--------|
| `origin/main` | `f546af71b88b250f7a30d6614d74b6d818505177` |
| Health-route fix present | VERIFIED (`base_router` no longer registers `/` or `/health`) |
| Health tests on main | VERIFIED via CI 38077295836 |
| Unexpected main drift | None observed at verification time |
| Live `/health` | Still `0.1.0` / AEGIS Backend → **deploy not yet applied** (expected) |

---

## 2. CATEGORY 2 — Backup & disposable restore runbook

### Provider identification

`render.yaml` defines:

- Web service: **`aegis-api`** (Docker, `healthCheckPath: /health`)
- Database resource: **`aegis-postgres`** (Render Postgres) wired to `DATABASE_URL`
- Redis: **`aegis-redis`**

**Operator must confirm** in the Render dashboard whether the live `DATABASE_URL` still points at Render Postgres or was switched to an external provider (e.g. Neon). Use the dashboard value, not assumptions.

### A. Backup procedure (operator)

1. Render Dashboard → **aegis-postgres** (or external DB provider if `DATABASE_URL` is external).  
2. Create/export a **full** logical backup or point-in-time snapshot per provider UI.  
3. Record (no secrets):
   - Backup identifier  
   - UTC timestamp  
   - Database/service name  
   - Completion status = success  
4. Store the backup in the operator’s secure location (not chat, not GitHub).

### B. Disposable restore

1. Create a **new** disposable database (Render free DB, Neon branch, or local Docker Postgres).  
2. Restore the backup **only** into that disposable target.  
3. **Before** any app process uses it, confirm connection string points at the disposable host (not production).  
4. Verification queries on disposable only:

```sql
SELECT version_num FROM alembic_version;

SELECT count(*) AS lifecycle_rows FROM aegis_position_lifecycle;
SELECT count(*) AS queue_rows FROM aegis_execution_queue;
SELECT count(*) AS subscriptions FROM subscriptions;
SELECT count(*) AS presence_rows FROM aegis_executor_presence;
SELECT count(*) AS ops_control FROM aegis_operational_control;
```

5. Confirm schema includes columns `open_risk_applied` (lifecycle) and queue `status`.  
6. Destroy the disposable database when evidence is recorded.

### C. Gate rule

- Backup job alone = **NOT sufficient**.  
- Isolated restore + checks = required for **VERIFIED**.  
- **Current status: NOT VERIFIED.**

---

## 3. CATEGORY 1 — Production inventory (read-only)

**SELECT-only.** Operator environment only. Never paste secrets into chat.

### Admin / API (optional)

```bash
BASE="https://aegis-api-0z1p.onrender.com"
# Admin key entered interactively — do not log
curl -sS "$BASE/health"
curl -sS -H "X-API-Key: $ADMIN_KEY" -H "Accept: application/json" \
  "$BASE/api/admin/ops/executor-status/ACC-1987D3D2E6"
# Emergency-stop status via existing admin operational endpoint (GET only)
```

### SQL (production console — read-only)

Tables/columns verified in models on main `f546af7`:

- `alembic_version.version_num`
- `aegis_position_lifecycle` (`open_risk_applied`, `state`, …)
- `subscriptions` (`account_id`, `open_risk_usd`)
- `aegis_execution_queue` (`status` ∈ PENDING|CLAIMED|SUBMISSION_UNCERTAIN|ACKED|REJECTED|EXPIRED)
- `aegis_operational_control` (emergency_stop key)
- `aegis_executor_presence`

```sql
-- A. Alembic revision
SELECT version_num FROM alembic_version;

-- B–C. Lifecycle + open_risk_applied
SELECT
  CASE
    WHEN open_risk_applied IS NULL THEN 'NULL'
    WHEN open_risk_applied IS FALSE THEN 'FALSE'
    WHEN open_risk_applied IS TRUE THEN 'TRUE'
  END AS applied_state,
  state,
  count(*)
FROM aegis_position_lifecycle
GROUP BY 1, 2
ORDER BY 1, 2;

-- D. Portfolio open risk
SELECT account_id, open_risk_usd
FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0
ORDER BY open_risk_usd DESC;

-- E. Queue by status
SELECT status, count(*), min(created_at) AS oldest, max(created_at) AS newest
FROM aegis_execution_queue
GROUP BY status
ORDER BY status;

-- Non-terminal / attention
SELECT signal_id, account_id, symbol, status, created_at, claimed_at, attempt_count
FROM aegis_execution_queue
WHERE status IN ('PENDING', 'CLAIMED', 'SUBMISSION_UNCERTAIN')
ORDER BY status, created_at;

-- G. Emergency stop (key name as stored by operational control service)
SELECT key, value, updated_at
FROM aegis_operational_control
WHERE key = 'emergency_stop';

-- H. Executor presence (no secrets)
SELECT account_id, client_type, executor_version, execution_mode,
       last_symbol, last_seen_at
FROM aegis_executor_presence
ORDER BY last_seen_at DESC NULLS LAST;
```

### Broker comparison (F)

From **MT5 only**: open tickets, symbol, side, volume.  
Compare to lifecycle rows with open states.  
**Do not** treat ACK, queue status, or heartbeat as broker truth.

### Historical risk safety

- `open_risk_applied IS NULL` → **do not auto-recover**  
- `FALSE` → recover only after independent broker ticket + risk amount verification  
- `TRUE` → already applied; do not double-increment  
- **No backfill, no production writes in this stage**

### Inventory status

**NOT VERIFIED** (Builder has no production access).

---

## 4. Live Render deployment identity

**NOT VERIFIED.**

Operator:

1. Render Dashboard → **aegis-api** → **Events / Deploys**  
2. Select the **active** deployment  
3. Record: commit SHA, status, timestamp  
4. Compare to intended main: `f546af71b88b250f7a30d6614d74b6d818505177`  

Live health still shows legacy `0.1.0` → consistent with **pre–health-route deploy** or undeployed main. **Do not** treat health as Git identity.

After a **future authorized** deploy of `f546af7` (or later):

- Expected `GET /health`: `service: AEGIS API`, `version: 3.0.3`, `redis` bool, status `ok`/`degraded`  
- Still record the **dashboard deployed SHA** as authoritative  

Entrypoint on deploy: `alembic upgrade head` (may apply pending migrations including 0023 if not already on DB).

---

## 5. EA compilation (separate gate)

| Item | Value |
|------|--------|
| Branch | `fix/executor-v221-saveclosequeue-compile` |
| Commit | `1bd2de1355e670ad34063c07abf6ba0f29f7cb79` |
| Source SHA-256 | `06dfc5a5845cc818044219e21dad68dceb8f02ce4e8c154ea8abe6bb95695a01` |
| MetaEditor | **NOT VERIFIED** |
| Merged / installed | **No** |

Required operator evidence: file+commit, SHA-256 match, 0 errors / 0 warnings. No install implied.

---

## 6. Evidence register

| Gate | Status | Evidence source | Owner action |
|------|--------|-----------------|--------------|
| Main SHA `f546af7` | VERIFIED | GitHub | — |
| Post-merge CI | VERIFIED | Actions 38077295836 | — |
| Health-route on main | VERIFIED | Source + CI | — |
| Live deployed SHA | NOT VERIFIED | — | Render dashboard |
| Backup created | NOT VERIFIED | — | Provider backup |
| Disposable restore | NOT VERIFIED | — | Isolated restore + SQL checks |
| Production inventory | NOT VERIFIED | — | Cat 1 SQL + admin + MT5 |
| Emergency-stop known | NOT VERIFIED | — | Inventory query |
| EA MetaEditor | NOT VERIFIED | — | Windows compile |
| Production deploy | **BLOCKED** | — | Separate authorization after gates |

---

## 7. Safest next actions (order)

1. Operator: production **backup** + **disposable restore** → record evidence.  
2. Operator: **production inventory** (SQL + admin + MT5 positions).  
3. Operator: record **Render deployed commit SHA**.  
4. Owner: review evidence; only then consider **separate deploy** authorization of a **named SHA**.  
5. Post-deploy (if authorized): verify dashboard SHA + health contract + re-inventory.  
6. Separate: MetaEditor EA compile → merge/install only with further authorization.  
7. Separate: controlled Demo authorization.

---

## 8. NOT performed / not authorized this stage

Deploy · production migration · production data writes · env/secrets · emergency-stop change · production_authorized · signals/orders · EA merge/install · auto NULL recovery · UNCERTAIN redelivery · merge of docs/EA branches  

---

## Conclusion

**READY FOR FURTHER EVIDENCE COLLECTION**

Production deployment remains **BLOCKED** until backup/restore and production inventory are verified and separately reviewed.
