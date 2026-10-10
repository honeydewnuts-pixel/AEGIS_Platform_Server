# Stage 6.6 — Deployment Gate (NOT EXECUTED)

Approved main baseline at documentation time: `df757c2d17adea50b4ff17b3290641b03d5d0e56`

This document is a release gate and operator runbook. **No production deployment or migration is authorized by this document alone.**

## 1. Release identity

| Item | Value |
|------|--------|
| Source SHA | `df757c2d17adea50b4ff17b3290641b03d5d0e56` (verify before deploy) |
| Build | Render Docker: `docker/Dockerfile`, context `.` |
| Entrypoint | `docker/entrypoint.sh` → `alembic upgrade head` then uvicorn |
| Health | `GET /health` (no API key; Redis ping) |
| Service name | `aegis-api` (`render.yaml`) |

**Artifact ↔ SHA:** Render builds from the connected Git commit. After deploy, confirm Render dashboard commit SHA matches the authorized main SHA.

**Critical:** Entrypoint always runs migrations before the API starts. A failed migration prevents startup (`set -e`). A successful deploy of a revision that includes 0023 **will apply** 0023 if not already applied.

## 2. Migration 0023

- **Revision:** `0023_lifecycle_open_risk_applied` (after `0022_aegis_executor_presence`)
- **Operation:** `ADD COLUMN open_risk_applied BOOLEAN NULL` on `aegis_position_lifecycle`
- **No backfill:** existing rows stay NULL (historical/ambiguous)
- **Downgrade:** `DROP COLUMN` — unsafe after portfolio accounting has used the flag; does not reverse `open_risk_usd`

## 3. Pre-deploy inventory (read-only; operator / admin)

Use admin API key only in the authorized environment. **Do not paste secrets into chat.**

```bash
# Replace BASE and KEY locally — do not commit values
BASE="https://aegis-api-0z1p.onrender.com"
KEY="YOUR_ADMIN_KEY_HERE"

# Health (no key)
curl -sS "$BASE/health"

# Executor presence (admin)
curl -sS -H "X-API-Key: $KEY" -H "Accept: application/json" \
  "$BASE/api/admin/ops/executor-status/ACC-1987D3D2E6"

# Queue diagnostic for a known signal_id (admin, read-only)
# curl -sS -H "X-API-Key: $KEY" \
#   "$BASE/api/admin/ops/execution-diagnostic/SIGNAL_ID"
```

SQL inventory (operator with DB access only — never in chat):

```sql
-- Alembic
SELECT version_num FROM alembic_version;

-- Lifecycle open_risk_applied distribution
SELECT open_risk_applied, state, count(*)
FROM aegis_position_lifecycle
GROUP BY 1, 2 ORDER BY 1, 2;

-- Open risk by account
SELECT account_id, open_risk_usd FROM subscriptions
WHERE open_risk_usd IS DISTINCT FROM 0 ORDER BY open_risk_usd DESC;

-- Queue by status
SELECT status, count(*), min(created_at), max(created_at)
FROM aegis_execution_queue GROUP BY status ORDER BY status;
```

Broker positions must come from MT5 (operator), not from server inference.

## 4. Backup / restore gate

Before migration:

1. Produce a full Postgres backup of production.
2. Restore to a **disposable** database and verify:
   - `alembic_version` matches production
   - Row counts for lifecycle, queue, subscriptions
3. Record backup timestamp and storage location (secure).
4. Do **not** restore over production as a test.

If backup/restore is not verified → gate **BLOCKED**.

## 5. Deployment sequence (NOT EXECUTED)

**A. Preconditions:** authorized SHA + green CI; verified backup; inventory clean or accepted; emergency-stop known; EA v2.21 heartbeat if Demo follows; owner authorization.

**B. Migration:** Deploy triggers `alembic upgrade head` via entrypoint. Alternatively run migration in a controlled window first if process allows — current design ties migration to container start.

**C. App release:** Confirm Render commit SHA; `GET /health`; optional admin checks.

**D. Monitor:** logs, queue, presence, risk, stop state.

**E. Stop/rollback:** Prefer stop + forward repair if positions/UNCERTAIN exist. App rollback ≠ DB rollback. Do not drop `open_risk_applied` if risk accounting has used it.

## 6. Controlled Demo gates (no order in Stage 6.6)

1. Identity — Demo account, URL, EA version, `production_authorized=false`
2. Heartbeat/polling — presence healthy, version 2.21
3. Idle integrity — no unexpected PENDING/CLAIMED/UNCERTAIN; risk matches positions
4. Controlled order — **separate authorization**
5. Close/reconcile — **separate authorization**
6. Emergency stop — **separate authorization**
7. Final decision — PASS / FAIL / INCONCLUSIVE per gate

## 7. Known pending source items (not on main unless merged)

- EA MetaEditor compile fix branch: `fix/executor-v221-saveclosequeue-compile` (orphaned `SaveCloseQueueToFile` call). Must be compiled on Windows after merge/checkout.

## 8. Governance

- production_authorized remains false
- No exactly-once broker claim
- V53.6 / research / risk / withdrawals frozen
