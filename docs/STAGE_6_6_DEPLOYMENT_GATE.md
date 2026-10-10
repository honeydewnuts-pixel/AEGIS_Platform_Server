# Stage 6.6 — Recovery Verification & Production Readiness (Updated)

**Document date:** 2026-10-10  
**Main HEAD (verified):** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Main CI:** [38077295836](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38077295836) — **455 passed, 3 skipped**  

**Conclusion:** READY FOR FURTHER EVIDENCE COLLECTION  
**Deploy of further changes:** still requires backup/restore VERIFIED  
**Current live deploy of health-route fix:** supported by live health contract + operator Render report (see §1)

This document does **not** authorize new deploys, migrations, EA install, or trading.

---

## 1. Source and deployment state

| Item | Evidence | Status |
|------|----------|--------|
| main HEAD | `f546af7…` | **PASS** |
| Health-route on main | Merged (FF); no legacy `/health` on base_router | **PASS** |
| Main CI | 38077295836 success | **PASS** |
| Live `GET /health` | `{"status":"ok","redis":true,"service":"AEGIS API","version":"3.0.3"}` | **PASS** (matches main.py contract) |
| Live `GET /` | `service: AEGIS API`, `version: 3.0.3`, `status: online` | **PASS** |
| Render deployed SHA | Operator reported active deploy commit prefix **f546af7** | **PASS with limitation** — full SHA should still be copied from Render Deploys for the audit trail |
| Neon Alembic | Operator: `0023_lifecycle_open_risk_applied` | **PASS** |
| Column `open_risk_applied` | Operator: boolean, nullable YES on `aegis_position_lifecycle` | **PASS** |

**Limitation:** Builder cannot open Render dashboard. Live response contract matching main + operator commit-prefix report is strong evidence the health-route deploy is active. Record the **full** 40-character SHA from Render for formal closure.

---

## 2. Migration 0023 & recovery semantics (source)

| Check | Status |
|-------|--------|
| Additive nullable column, no backfill | **PASS** (migration source) |
| NULL = do not auto-recover | **PASS** (source + design) |
| FALSE eligible only with verified broker risk | **PASS** (source design) |
| TRUE = applied | **PASS** |
| Concurrent recovery / no double-count | **PASS** (main CI PG tests) |
| Fail-closed on missing portfolio service | **PASS** (Stage 6.4A) |
| Exactly-once broker | **Not claimed** |

Production schema matches migration intent (operator SQL).

---

## 3. Neon backup & restore (operator phone-friendly)

**Facts:** Production DB is **Neon**. API is **Render**.  
**BLOCKED:** Neon **Backup & Restore** page loads then goes **blank** (desktop and mobile). Availability of point-in-time restore / snapshots is **UNVERIFIED**.

### A. Confirm project / branch (Neon Console)

1. Open [console.neon.tech](https://console.neon.tech) and sign in.  
2. Select the AEGIS project.  
3. Open the **production** branch (name as used for live API).  
4. Note project name and branch name (no passwords).

### B. Why Backup & Restore may be blank

Common causes (do not assume DB damage):

- Plan does not include PITR / history (free/limited plans vary).  
- Browser/extension issue (try another browser or desktop).  
- Temporary Neon UI bug.  
- Wrong org/project selected.

### C. Supported alternatives (check what your plan shows)

In Neon Console, look for **any** of:

1. **Branches → Create branch** from current production (copy-on-write snapshot of current state).  
2. **Restore** / **Point-in-time** if available on your plan.  
3. **Export** / external dump using Neon’s documented connection (operator runs locally; **never** paste connection string into chat).

### D. Disposable recovery test (preferred if “Create branch” works)

1. Create a **new branch** named e.g. `restore-test-YYYYMMDD` from production.  
2. Open **SQL Editor** on that **new** branch only.  
3. Run:

```sql
SELECT version_num FROM alembic_version;

SELECT count(*) FROM aegis_position_lifecycle;
SELECT count(*) FROM aegis_execution_queue;
SELECT count(*) FROM subscriptions;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'aegis_position_lifecycle'
  AND column_name = 'open_risk_applied';
```

4. Expected: revision `0023_lifecycle_open_risk_applied`; column present, nullable.  
5. Record: branch name, time, query results.  
6. **Delete** the test branch when done (do not delete production).

### E. Gate rule

| Evidence | Status |
|----------|--------|
| Neon UI Backup page works | **UNVERIFIED** (blank) |
| Disposable branch/restore test completed | **UNVERIFIED** |
| Backup/restore gate overall | **BLOCKED** until disposable recovery succeeds |

---

## 4. Read-only production inventory (Neon SQL Editor)

Run on **production** branch, SELECT only. Record counts (no secrets).

```sql
SELECT version_num FROM alembic_version;

SELECT
  CASE
    WHEN open_risk_applied IS NULL THEN 'NULL'
    WHEN open_risk_applied IS FALSE THEN 'FALSE'
    WHEN open_risk_applied IS TRUE THEN 'TRUE'
  END AS applied_state,
  state,
  count(*)
FROM aegis_position_lifecycle
GROUP BY 1, 2 ORDER BY 1, 2;

SELECT account_id, open_risk_usd
FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0
ORDER BY open_risk_usd DESC;

SELECT status, count(*), min(created_at), max(created_at)
FROM aegis_execution_queue
GROUP BY status ORDER BY status;

SELECT signal_id, account_id, symbol, status, created_at, claimed_at, attempt_count
FROM aegis_execution_queue
WHERE status IN ('PENDING', 'CLAIMED', 'SUBMISSION_UNCERTAIN')
ORDER BY status, created_at;

SELECT key, value, updated_at
FROM aegis_operational_control
WHERE key = 'emergency_stop';

SELECT account_id, client_type, executor_version, execution_mode,
       last_symbol, last_seen_at
FROM aegis_executor_presence
ORDER BY last_seen_at DESC NULLS LAST;
```

**MT5 checklist (operator):** open positions (ticket, symbol, side, volume) vs lifecycle open rows.  
Do not auto-fix NULL `open_risk_applied`.

**Inventory status:** **UNVERIFIED** (except Alembic + column schema already provided by operator).

---

## 5. Executor EA gate (separate)

| Item | Status |
|------|--------|
| Branch/commit | `fix/executor-v221-saveclosequeue-compile` / `1bd2de1` |
| SHA-256 both paths | `06dfc5a5845cc818044219e21dad68dceb8f02ce4e8c154ea8abe6bb95695a01` **PASS** (source) |
| MetaEditor 0 errors / 0 warnings | **UNVERIFIED** |
| Merged / installed | **No** |

---

## 6. Evidence register

| Gate | Status |
|------|--------|
| Main + CI | **PASS** |
| Live health contract 3.0.3 | **PASS** |
| Render commit prefix f546af7 | **PASS with limitation** (record full SHA) |
| Neon Alembic 0023 | **PASS** |
| open_risk_applied column | **PASS** |
| Full production inventory | **UNVERIFIED** |
| Neon backup / disposable restore | **BLOCKED / UNVERIFIED** |
| EA MetaEditor | **UNVERIFIED** |
| New production deploy authorization | **BLOCKED** until backup/restore + inventory |
| production_authorized / Demo order | Not authorized |

---

## 7. Mobile operator checklist

- [ ] Copy **full** Render deploy commit SHA (Deploys → active)  
- [ ] Neon: try **Create branch** from production for restore-test  
- [ ] On test branch: run verification SQL; save results; delete test branch  
- [ ] If Backup & Restore stays blank: note plan name + screenshot of empty page  
- [ ] Production SQL inventory (section 4)  
- [ ] MT5: list open positions  
- [ ] Emergency-stop value from SQL  
- [ ] Executor presence row (version / last_seen)  
- [ ] Do **not** paste passwords or connection strings into chat  
- [ ] Do **not** run UPDATE/DELETE/migrate on production  

---

## 8. Exact next actions

1. Complete Neon **disposable branch** recovery test (or document plan limitation if Create branch unavailable).  
2. Complete full **inventory** SQL + MT5.  
3. Record full Render deploy SHA.  
4. Owner reviews evidence before any **new** deploy authorization.  
5. Separate: MetaEditor compile EA fix.  
6. Separate: controlled Demo only after idle integrity.

---

## NOT performed by Builder this stage

Deploy · production SQL writes · restore over production · secret changes · emergency-stop change · production_authorized · signals/orders · EA merge/install · branch merges · fabricated backup success  

**Production deployment of further changes remains BLOCKED until backup/restore is verified.**
