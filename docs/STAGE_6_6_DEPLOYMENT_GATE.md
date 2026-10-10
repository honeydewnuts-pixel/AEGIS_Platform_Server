# Stage 6.6 / 6.6B — Deployment Gate Evidence Report

**Status date:** 2026-10-10  
**Overall decision:** READY WITH LIMITATIONS  

This document is evidence and procedure. **Nothing in this file authorizes production deploy, migration 0023 execution, EA install, or a controlled Demo order.**

---

## 1. Verified source baseline

| Item | Value | Evidence class |
|------|--------|----------------|
| `origin/main` | `df757c2d17adea50b4ff17b3290641b03d5d0e56` | Verified (git fetch 2026-10-10) |
| Stage 6.6 branch | `stage-6.6-deployment-gate` | Verified |
| EA compile-fix branch | `fix/executor-v221-saveclosequeue-compile` @ `1bd2de1355e670ad34063c07abf6ba0f29f7cb79` | Verified; **not on main** |
| Main CI | [Run 38060842633](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38060842633) — **453 passed, 3 skipped**, Docker success | Verified |
| Tested SHA | `df757c2d17adea50b4ff17b3290641b03d5d0e56` | Verified |

**3 CI skips:** rulebook causal tests (external large CSV absent). Not Stage 6.4/6.5 related.

**Application runtime behavior on main is unchanged by Stage 6.6 documentation commits.**

---

## 2. Deployment identity (source)

| Topic | Finding |
|-------|---------|
| Platform | Render (`render.yaml`: web `aegis-api`, Docker) |
| Dockerfile | `docker/Dockerfile` |
| Entrypoint | `docker/entrypoint.sh`: `alembic upgrade head` then uvicorn `--workers 1` (`set -e`) |
| Health check path | `/health` |
| Required env (names only) | `DATABASE_URL`, `REDIS_URL`, `AEGIS_MASTER_KEY`, `ADMIN_BOOTSTRAP_KEY`, `SECRET_KEY`, payment keys, `ALLOWED_ORIGINS`, … |

**Entrypoint implication:** Any deploy of a revision that includes migration 0023 will **automatically apply** it if not already applied. Failed migration prevents API start.

---

## 3. Live health / source-identity discrepancy

### Observed live (read-only, 2026-10-10)

`GET https://aegis-api-0z1p.onrender.com/health`:

```json
{"status":"healthy","service":"AEGIS Backend","version":"0.1.0"}
```

`GET https://aegis-api-0z1p.onrender.com/`:

```json
{"application":"AEGIS","description":"Autonomous Enterprise Global Intelligence System","company":"Honeydewnuts Nigerian Limited","version":"0.1.0","status":"Running"}
```

### Current `main` source defines **two** health-related handlers

1. `backend/app/main.py` — `@app.get("/health")` → `status`/`redis`/`service: AEGIS API`/`version: 3.0.3`
2. `backend/app/api/router.py` — `@router.get("/health")` → `status: healthy`/`service: AEGIS Backend`/`version: 0.1.0` (matches live)

`base_router` is `include_router`'d **before** the `main.py` `/health` registration. Live responses match the **base_router** shape, not the main.py Redis-aware shape.

### Conclusion

**LIVE SOURCE IDENTITY UNVERIFIED.**

A health `version` string alone cannot prove the deployed Git SHA. Possible explanations include: older deploy; current main with route registration order favoring `base_router`; or another service revision. **Do not deploy solely to make version strings match.** Future improvement (separate authorization): single health handler exposing `git_sha` or build id — not implemented in this stage.

---

## 4. Migration 0023 review

| Check | Result |
|-------|--------|
| Revision | `0023_lifecycle_open_risk_applied` (revises `0022_aegis_executor_presence`) |
| Operation | Additive `open_risk_applied BOOLEAN NULL` on `aegis_position_lifecycle` |
| Backfill | **None** — existing rows remain NULL |
| Destructive | No |
| App semantics | NULL = historical unknown (no auto-recover); False = eligible when verified; True = applied |
| Recovery | Flag not set inside `reconcile`; caller records portfolio risk then marks applied in same session |
| Downgrade | Drops column; **does not** reverse `open_risk_usd` — unsafe as general rollback after flag is used |
| Production migration this stage | **NOT EXECUTED** |

**Gate: PASS** (design) / **NOT EXECUTED** (production apply).

---

## 5. Read-only production inventory procedure

**Category 1 — Read-only production inspection** (operator environment only; never paste secrets into chat).

```bash
# Local only — operator substitutes values; do not commit
BASE="https://aegis-api-0z1p.onrender.com"
KEY="YOUR_ADMIN_API_KEY"   # enter interactively; do not log

curl -sS "$BASE/health"
curl -sS -H "X-API-Key: $KEY" -H "Accept: application/json" \
  "$BASE/api/admin/ops/executor-status/ACC-1987D3D2E6"
# Optional: execution-diagnostic for a known signal_id
# curl -sS -H "X-API-Key: $KEY" "$BASE/api/admin/ops/execution-diagnostic/SIGNAL_ID"
```

SQL (**SELECT only**; production DB console / approved client):

```sql
SELECT version_num FROM alembic_version;

SELECT open_risk_applied, state, count(*)
FROM aegis_position_lifecycle
GROUP BY 1, 2 ORDER BY 1, 2;

SELECT account_id, open_risk_usd FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0
ORDER BY open_risk_usd DESC;

SELECT status, count(*), min(created_at), max(created_at)
FROM aegis_execution_queue
GROUP BY status ORDER BY status;

SELECT signal_id, account_id, symbol, status, created_at, claimed_at
FROM aegis_execution_queue
WHERE status IN ('CLAIMED', 'SUBMISSION_UNCERTAIN')
ORDER BY created_at;
```

Broker positions: **from MT5 only**. Do not infer from DB.

**Inventory completion this stage:** **INCONCLUSIVE / UNAVAILABLE** (no production DB or admin key in Builder environment).

---

## 6. Backup / restore procedure (Category 2 — disposable)

1. Use the approved Postgres provider (Render Postgres / Neon) backup UI or documented export.
2. Record: backup id, timestamp, database name (not password), completion status.
3. Restore **only** to a disposable database/instance.
4. On disposable DB: check `alembic_version`, row counts for lifecycle/queue/subscriptions.
5. Ensure no app process uses production `DATABASE_URL` during the exercise.
6. Tear down disposable environment after evidence capture.

**This stage:** **BACKUP/RESTORE NOT VERIFIED.**

**Gate: BLOCKED** for production migration/deploy until verified.

---

## 7. Executor v2.21 status

| Item | Status |
|------|--------|
| Main tree EA SHA-256 | `0cfd6e9b17ce5b76715cb5bdb846facea2dea835e38d555b5227bc78fe97b9e0` (pre-fix; compile error) |
| Fix branch EA SHA-256 (both paths match) | `06dfc5a5845cc818044219e21dad68dceb8f02ce4e8c154ea8abe6bb95695a01` |
| Fix | Orphaned `SaveCloseQueueToFile()` moved inside `FlushCloseNotifyRetries()` |
| MetaEditor compile | **NOT VERIFIED** — requires Windows operator |
| Merged to main | **No** |
| Installed on VPS | **No evidence** |
| Heartbeat `executor_version=2.21` | **NOT VERIFIED** this stage |

**Gates:** compile **INCONCLUSIVE**; runtime **INCONCLUSIVE**. Do not merge/install/attach until 0 errors / 0 warnings from MetaEditor.

---

## 8. Queue / risk / emergency-stop (source + CI)

| Control | Evidence |
|---------|----------|
| Stop ON blocks delivery | Source + Stage 6.4B tests |
| Stop lookup failure fail-closed (delivery) | Source + tests |
| Enqueue fail-closed on stop lookup failure | Stage 6.5 on main |
| CLAIMED not auto-redelivered | Source |
| Lease → SUBMISSION_UNCERTAIN | Source |
| Same account/symbol block while CLAIMED/UNCERTAIN | Source + tests |
| Late ACK / durable ACK failure handling | Source + Stage 6.3/6.4 |
| NULL/FALSE/TRUE open_risk_applied | Source + PG recovery tests |
| Real PG concurrent claim / reconcile / recovery / rollback | Main CI **PASSED** |
| Exactly-once broker | **Not claimed** |

---

## 9. Gate status summary

| Gate | Status |
|------|--------|
| Source main SHA + CI | **PASS** |
| Migration 0023 design | **PASS** |
| Migration 0023 production apply | **NOT EXECUTED** |
| Backup + disposable restore | **BLOCKED** (not verified) |
| Production inventory | **INCONCLUSIVE** |
| Live deploy SHA identity | **INCONCLUSIVE** (`LIVE SOURCE IDENTITY UNVERIFIED`) |
| EA MetaEditor compile (fix) | **INCONCLUSIVE** |
| EA runtime v2.21 heartbeat | **INCONCLUSIVE** |
| Controlled Demo order | **NOT EXECUTED** / not authorized |

---

## 10. Operator actions (safest order)

1. **Backup** production DB; **restore to disposable**; record evidence (Category 2).  
2. **Read-only inventory** (Category 1): Alembic, lifecycle flags, open_risk, queue, CLAIMED/UNCERTAIN, stop, executor-status.  
3. **Windows MetaEditor:** compile fix-branch `AEGIS_Executor.mq5` (hash `06dfc5a5…`); confirm 0 errors / 0 warnings.  
4. **Separate authorization:** merge EA fix if compile clean; then VPS install/attach.  
5. **Separate authorization:** deploy exact main SHA to Render (accepts entrypoint migration).  
6. **After deploy:** confirm identity (Render commit SHA), health, inventory, EA heartbeat.  
7. **Separate authorization:** controlled Demo order only after idle integrity.

---

## 11. Rollback / forward recovery limitations

- App image rollback **≠** database rollback.  
- 0023 downgrade drops `open_risk_applied` and does **not** reverse `open_risk_usd`.  
- Prefer stop + forward repair when open positions or SUBMISSION_UNCERTAIN exist.  
- Uncertain broker outcomes require human/broker reconciliation.

---

## 12. Explicitly NOT performed in Stage 6.6 / 6.6B

- Production deploy  
- Production migration 0023  
- Production env/secret changes  
- `production_authorized=true`  
- Emergency-stop state change  
- Trading signals / claims / ACKs / broker orders  
- EA merge / VPS install / chart attach  
- Merge of documentation or EA branches to main  
- Automatic NULL open_risk recovery or UNCERTAIN redelivery  

---

## 13. Recommendation

**READY WITH LIMITATIONS** — source and CI are acceptable for **considering** separate deployment authorization **only after** backup/restore verification and read-only production inventory. Do **not** authorize deploy while backup/restore remains BLOCKED.

Controlled Demo and EA production use require additional gates above.
