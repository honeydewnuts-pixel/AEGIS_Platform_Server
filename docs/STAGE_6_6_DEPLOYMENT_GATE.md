# Stage 6.6 / 6.6B / 6.6C — Deployment Gate Runbook

**Document status:** authoritative Stage 6.6 operator runbook  
**Overall readiness:** READY WITH LIMITATIONS (deploy **BLOCKED** until backup/restore + inventory)  
**Application main SHA (verified):** `df757c2d17adea50b4ff17b3290641b03d5d0e56`  

**This document does not authorize production deploy, migration execution, EA install, or Demo orders.**

---

## Verified baseline (2026-10-10)

| Item | Value |
|------|--------|
| `origin/main` | `df757c2d17adea50b4ff17b3290641b03d5d0e56` |
| Main CI | [38060842633](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38060842633) — 453 passed, 3 skipped |
| Docs branch | `stage-6.6-deployment-gate` |
| EA fix branch | `fix/executor-v221-saveclosequeue-compile` @ `1bd2de1` — **not merged** |
| Health-route fix branch | `fix/health-route-shadowing` @ `f546af7` — **not merged, not deployed** |

---

## CATEGORY 1 — READ-ONLY PRODUCTION INSPECTION

No mutations. Operator enters credentials only in their environment.

### 1.1 Public health

```bash
BASE="https://aegis-api-0z1p.onrender.com"
curl -sS "$BASE/health"
curl -sS "$BASE/"
```

**Current live observation (Builder, 2026-10-10):**  
`{"status":"healthy","service":"AEGIS Backend","version":"0.1.0"}`  

This matches **legacy** `base_router` handlers. It does **not** prove the live Git SHA.

### 1.2 Admin executor presence

```bash
KEY="YOUR_ADMIN_API_KEY"   # interactive only — never commit or paste into chat
curl -sS -H "X-API-Key: $KEY" -H "Accept: application/json" \
  "$BASE/api/admin/ops/executor-status/ACC-1987D3D2E6"
```

Capture: `exists`, `healthy`, `last_seen_at`, `executor_version`, `client_type`, `execution_mode`, `last_symbol`.

### 1.3 SELECT-only SQL (production console)

Verify names against models: `aegis_position_lifecycle`, `aegis_execution_queue`, `subscriptions`, `alembic_version`.

```sql
-- B1 Alembic
SELECT version_num FROM alembic_version;

-- B2 Lifecycle by open_risk_applied
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

-- B3 Portfolio open risk
SELECT account_id, open_risk_usd
FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0
ORDER BY open_risk_usd DESC;

-- B4 Queue by status
SELECT status, count(*), min(created_at) AS oldest, max(created_at) AS newest
FROM aegis_execution_queue
GROUP BY status
ORDER BY status;

-- B5 CLAIMED / SUBMISSION_UNCERTAIN detail (no secrets)
SELECT signal_id, account_id, symbol, status, created_at, claimed_at, attempt_count
FROM aegis_execution_queue
WHERE status IN ('CLAIMED', 'SUBMISSION_UNCERTAIN')
ORDER BY created_at;
```

### 1.4 Emergency stop

Use existing admin operational-control / ops endpoints with admin key (GET only). Record stop ON/OFF and retrieval success.

### 1.5 Broker positions

From **MT5 only**. Compare tickets to server lifecycle. Do not treat ACK, heartbeat, or DB rows as broker truth.

**Inventory this stage:** UNAVAILABLE (Builder has no production DB/admin session).

---

## CATEGORY 2 — DISPOSABLE BACKUP / RESTORE VERIFICATION

**Provider:** Render Postgres (primary in `render.yaml`); production may also use Neon if `DATABASE_URL` points there. Confirm in the Render dashboard which database the `aegis-api` service uses.

### Procedure

1. In the provider dashboard, create or download a **full** backup/export.  
2. Record: backup id, UTC timestamp, database name (not password), status=completed.  
3. Create a **new disposable** database (or local Docker Postgres).  
4. Restore the backup **only** into the disposable database.  
5. Verify on disposable:  
   - `SELECT version_num FROM alembic_version;`  
   - `SELECT count(*) FROM aegis_position_lifecycle;`  
   - `SELECT count(*) FROM aegis_execution_queue;`  
   - `SELECT count(*) FROM subscriptions;`  
6. Ensure production app `DATABASE_URL` is unchanged and no test process uses production for writes.  
7. Destroy the disposable database when done.

**This stage:** BACKUP/RESTORE **NOT VERIFIED**.

**Deploy gate:** **BLOCKED** until VERIFIED.

---

## CATEGORY 3 — OPERATOR-REQUIRED ACTIONS

| Action | Owner | Evidence |
|--------|--------|----------|
| Provider backup + disposable restore | Operator with Render/Neon access | Backup id + restore check notes |
| Production inventory (Cat 1) | Operator with admin key + DB console | Query outputs (redact secrets) |
| MetaEditor compile EA fix | Windows VPS operator | 0 errors, 0 warnings screenshot/log |
| Confirm Render **deployed commit SHA** | Operator with Render dashboard | Dashboard commit = intended SHA |

**EA fix (not compiled in Builder):**

| Path | SHA-256 at `1bd2de1` |
|------|----------------------|
| `release/desktop/AEGIS_Executor.mq5` | `06dfc5a5845cc818044219e21dad68dceb8f02ce4e8c154ea8abe6bb95695a01` |
| `windows-desktop/mq5/AEGIS_Executor.mq5` | same |

Main (unfixed): `0cfd6e9b17ce5b76715cb5bdb846facea2dea835e38d555b5227bc78fe97b9e0`  

**METAEDITOR COMPILE NOT VERIFIED.**

---

## CATEGORY 4 — SEPARATELY AUTHORIZED CHANGES

Require explicit owner approval **per action**:

1. Merge `fix/health-route-shadowing` (optional identity fix).  
2. Merge `fix/executor-v221-saveclosequeue-compile` after clean MetaEditor compile.  
3. Production Render deploy of a named SHA.  
4. Accept automatic `alembic upgrade head` on container start (may apply 0023).  
5. VPS EA install/attach.  
6. Controlled Demo test signal / order.  
7. Any production data repair or stop-state change.

---

## Live deployment identity (Stage 6.6C finding)

### Source fact

On `main` (`df757c2`):

1. `app.main` defines `@app.get("/")` and `@app.get("/health")` (version `3.0.3`, Redis ping).  
2. `app.api.router` (`base_router`) **also** defined `@router.get("/")` and `@router.get("/health")` (version `0.1.0`).  
3. `include_router(base_router)` runs **before** the `main.py` route decorators.  
4. Starlette/FastAPI matches the **first** registered route for a path.

### Conclusion

Even if current `main` were deployed, live `/health` can still return the **legacy 0.1.0** payload because of **route shadowing**. Live response shape is therefore **insufficient** to prove or disprove deploy of `df757c2`.

**LIVE SOURCE IDENTITY UNVERIFIED** until Render dashboard shows the deployed commit SHA (authoritative).

### Proposed source fix (not merged, not deployed)

Branch `fix/health-route-shadowing` @ `f546af7`: removes duplicate `/` and `/health` from `base_router`; tests assert single handlers owned by `app.main`.

---

## Migration 0023

| Item | Status |
|------|--------|
| Design | PASS — additive nullable, no backfill |
| Semantics NULL/FALSE/TRUE | PASS in source |
| PG concurrent recovery / rollback tests | PASS on main CI |
| Downgrade limitation | Documented — drops column, does not reverse open_risk_usd |
| Entrypoint auto-migrate | YES — `alembic upgrade head` |
| Production apply | **NOT EXECUTED** |

---

## Queue / risk / emergency-stop

Stage 6.4–6.5 controls remain on main; CI evidence on `df757c2`. No exactly-once broker claim. No code change this stage except optional unmerged health-route fix.

---

## Gate matrix

| Gate | Status |
|------|--------|
| Source + CI (`df757c2`) | **PASS** |
| Migration 0023 design | **PASS** |
| Backup + disposable restore | **BLOCKED / NOT VERIFIED** |
| Production inventory | **UNAVAILABLE** |
| Live Git SHA identity | **INCONCLUSIVE** |
| Health route shadowing (source) | **FAIL** on main (shadow present); fix on branch only |
| EA MetaEditor compile | **NOT VERIFIED** |
| EA runtime v2.21 | **INCONCLUSIVE** |
| Deploy / migrate / Demo order | **NOT EXECUTED** |

---

## Safest next order

1. Category 2: backup + disposable restore → evidence  
2. Category 1: full inventory  
3. Render dashboard: record **deployed commit SHA**  
4. MetaEditor: compile EA fix → 0/0  
5. Owner decides merges (health-route, EA)  
6. Separate deploy authorization (named SHA)  
7. Post-deploy verify SHA + inventory + EA heartbeat  
8. Separate controlled Demo authorization  

---

## NOT performed (6.6 / 6.6B / 6.6C)

Production deploy · production migration · env/secret changes · emergency-stop change · production_authorized · signals/claims/orders · EA merge/install/attach · merge of any feature branch to main · automatic NULL recovery · UNCERTAIN redelivery  

---

## Recommendation

**Do not authorize deployment** until backup/restore is **VERIFIED** and production inventory is **COMPLETED** (or owner explicitly accepts residual risk in writing).

After those gates, deployment of a **named SHA** may be considered under **separate** authorization, with full awareness that entrypoint runs migrations.

Health-route fix and EA compile fix remain **optional pre-deploy merges** under separate approval.
