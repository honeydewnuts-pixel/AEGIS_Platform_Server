# Stage 6.6–6.6D — Deployment Gate Runbook (Authoritative)

**Overall:** READY WITH LIMITATIONS — **deploy BLOCKED** until backup/restore VERIFIED and production inventory COMPLETED.

**Verified main:** `df757c2d17adea50b4ff17b3290641b03d5d0e56`  
**Main CI:** [38060842633](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38060842633) — 453 passed, 3 skipped  

This document does **not** authorize production deploy, migration, EA install, or Demo trading.

---

## Branch inventory (verified 2026-10-10)

| Branch | SHA | Status |
|--------|-----|--------|
| `main` | `df757c2…` | CI green |
| `stage-6.6-deployment-gate` | (this docs branch) | Documentation only |
| `fix/health-route-shadowing` | `f546af71b88b250f7a30d6614d74b6d818505177` | **CI green; not merged** |
| `fix/executor-v221-saveclosequeue-compile` | `1bd2de1…` | Not merged; MetaEditor not verified |

Health-route CI: [38066627255](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38066627255) — **455 passed, 3 skipped** including:
- `test_health_handler_is_main_not_legacy_base_router` **PASSED**
- `test_root_handler_is_main` **PASSED**
- Stage 6.4 PG recovery tests **PASSED**

---

## CATEGORY 1 — Read-only production inspection

### Public

```bash
BASE="https://aegis-api-0z1p.onrender.com"
curl -sS "$BASE/health"
curl -sS "$BASE/"
```

**Live observation (Builder):** `version: 0.1.0`, `service: AEGIS Backend` — legacy shape.  
**Does not prove Git SHA.**

### Admin (operator environment only)

```bash
KEY="YOUR_ADMIN_API_KEY"   # never paste into chat
curl -sS -H "X-API-Key: $KEY" -H "Accept: application/json" \
  "$BASE/api/admin/ops/executor-status/ACC-1987D3D2E6"
```

### SELECT-only SQL

Tables verified in source: `alembic_version`, `aegis_position_lifecycle`, `aegis_execution_queue`, `subscriptions`.

```sql
SELECT version_num FROM alembic_version;

SELECT CASE
  WHEN open_risk_applied IS NULL THEN 'NULL'
  WHEN open_risk_applied IS FALSE THEN 'FALSE'
  WHEN open_risk_applied IS TRUE THEN 'TRUE'
END AS applied_state, state, count(*)
FROM aegis_position_lifecycle GROUP BY 1, 2 ORDER BY 1, 2;

SELECT account_id, open_risk_usd FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0 ORDER BY open_risk_usd DESC;

SELECT status, count(*), min(created_at), max(created_at)
FROM aegis_execution_queue GROUP BY status ORDER BY status;

SELECT signal_id, account_id, symbol, status, created_at, claimed_at, attempt_count
FROM aegis_execution_queue
WHERE status IN ('CLAIMED', 'SUBMISSION_UNCERTAIN')
ORDER BY created_at;
```

Broker positions: **MT5 only**.

**Inventory status:** UNAVAILABLE (Builder).

---

## CATEGORY 2 — Disposable backup / restore

**Provider:** Confirm in Render dashboard whether `aegis-api` uses Render Postgres (`render.yaml`) or an external `DATABASE_URL` (e.g. Neon).

1. Create/export full backup in provider UI.  
2. Record: backup id, UTC time, DB name (no password), completed.  
3. Restore **only** to a new disposable database.  
4. On disposable: `alembic_version`, counts for lifecycle / queue / subscriptions.  
5. Confirm production `DATABASE_URL` unchanged.  
6. Destroy disposable DB.

**Status:** NOT VERIFIED → deploy **BLOCKED**.

---

## CATEGORY 3 — Operator-required

| Task | Evidence |
|------|----------|
| Backup + disposable restore | Backup id + restore checks |
| Production inventory (Cat 1) | Query/API outputs (redacted) |
| Render **deployed commit SHA** | Dashboard screenshot/text |
| MetaEditor compile EA fix | 0 errors, 0 warnings |

**EA fixed SHA-256 (both paths @ `1bd2de1`):**  
`06dfc5a5845cc818044219e21dad68dceb8f02ce4e8c154ea8abe6bb95695a01`  
**METAEDITOR COMPILE NOT VERIFIED.**

---

## CATEGORY 4 — Separate authorization required

Merge health-route · merge EA · production deploy · accept auto-migrate on start · VPS EA install · controlled Demo · any production repair/stop change · `production_authorized`.

---

## Health-route diagnosis (6.6C/D)

| Fact | Evidence |
|------|----------|
| `base_router` registered `/` and `/health` before `main.py` | Source on main |
| First registered route wins | FastAPI/Starlette behavior |
| Live payload matches legacy router | Live GET `/health` |
| Fix removes duplicates; single handlers on `app.main` | Branch `f546af7` |
| Tests inspect **real** `app.routes` (not text-only) | `tests/test_health_route_identity.py` |
| Branch CI | **455 passed** |

**Health-route fix readiness for separate merge decision:** **PASS** (tested).  
**Not merged. Not deployed.**

**LIVE SOURCE IDENTITY:** **UNVERIFIED** until Render shows deployed commit SHA.

**How to read deployed SHA (operator):** Render Dashboard → service `aegis-api` → Events / Deploys → commit hash → compare to `df757c2…` or intended target.

---

## Migration 0023

Additive nullable `open_risk_applied`; no backfill; NULL/FALSE/TRUE preserved; PG recovery tests on main CI **PASS**. Entrypoint: `alembic upgrade head`. Production apply **NOT EXECUTED**. Downgrade drops column only — does not reverse `open_risk_usd`.

---

## Queue / risk / stop

Stage 6.4–6.5 on main: stop fail-closed, no auto-redeliver CLAIMED/UNCERTAIN, concurrent PG tests **PASS**. Exactly-once broker **not claimed**.

---

## Gate matrix

| Gate | Status |
|------|--------|
| Main source + CI | **PASS** |
| Health-route fix (branch) | **PASS** (merge-ready; unmerged) |
| Live deployed SHA | **UNVERIFIED** |
| Backup/restore | **NOT VERIFIED / BLOCKED** |
| Production inventory | **UNAVAILABLE** |
| Migration 0023 design | **PASS** |
| Migration 0023 production | **NOT EXECUTED** |
| EA MetaEditor | **NOT VERIFIED** |
| EA runtime v2.21 | **INCONCLUSIVE** |
| Deploy / Demo order | **NOT EXECUTED** |

---

## Safest next order

1. Cat 2 backup + disposable restore  
2. Cat 1 inventory  
3. Record Render deployed commit SHA  
4. MetaEditor compile EA fix  
5. Separate decisions: merge health-route; merge EA; deploy named SHA  
6. Post-deploy verify SHA + inventory + heartbeat  
7. Separate controlled Demo authorization  

---

## NOT performed

Production deploy · production migration · secret/env changes · emergency-stop change · production_authorized · signals/orders · EA merge/install · any merge to main · auto NULL recovery · UNCERTAIN redelivery  

---

## Recommendation

**Do not authorize deployment** until backup/restore is **VERIFIED** and inventory is **COMPLETED**.

Health-route branch may be **separately approved for merge** (CI green). EA merge only after MetaEditor 0/0. Deploy remains a further separate authorization after inventory + backup gates.
