# AEGIS Operational Baseline Report

**Report date:** 2026-10-11  
**Inspected remote:** `honeydewnuts-pixel/AEGIS_Platform_Server`  
**Branch inspected:** `origin/main`  
**Actual HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Reported checkpoint match:** **YES** (exact match)

## Remote / CI

| Item | Value |
|------|--------|
| Remote | `https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server.git` |
| Main HEAD | `f546af71b88b250f7a30d6614d74b6d818505177` |
| Tip commit | `fix(health): remove base_router / and /health that shadow main.py` |
| CI run | [38077295836](https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/actions/runs/38077295836) |
| CI result | **success** — 455 passed, 3 skipped; docker-build success |
| Docs branch (unmerged) | `stage-6.6-deployment-gate` @ `1016d27…` |
| EA fix branch (unmerged) | `fix/executor-v221-saveclosequeue-compile` @ `1bd2de1…` |

## Live API (Builder read-only)

| Endpoint | Response |
|----------|----------|
| `GET /health` | `{"status":"ok","redis":true,"service":"AEGIS API","version":"3.0.3"}` |
| `GET /` | `service: AEGIS API`, `version: 3.0.3`, `status: online` |

Health contract matches `app.main` handlers after Stage 6.6E merge + operator redeploy.

## Migrations

Head revision in repo: **`0023_lifecycle_open_risk_applied`**  
Operator Neon production: revision **`0023_lifecycle_open_risk_applied`** (reported) — consistent.

Key migrations: 0019 lifecycle, 0020 execution queue, 0021 operational control, 0022 executor presence, 0023 open_risk_applied.

## Environment separation (as designed)

| Layer | Hosting (operator-confirmed) |
|-------|------------------------------|
| API | Render (`aegis-api`) |
| PostgreSQL | Neon (production branch) |
| Redis | Render keyvalue / configured `REDIS_URL` |
| MT5 terminal | Windows VPS (operator) |

`render.yaml` still lists Render Postgres resource; live `DATABASE_URL` points at Neon (operator). Do not assume render.yaml alone describes production DB.

## Entrypoint

`docker/entrypoint.sh`: `alembic upgrade head` then uvicorn (auto-migrate on container start).

## Monitoring / health

- Authoritative `/health` and `/` on `app.main` (Redis-aware).
- Executor presence: `POST /api/executor/heartbeat`, admin `GET /api/admin/ops/executor-status/{account_id}`.
- Durable queue diagnostic: admin execution-diagnostic endpoints (read-only).

## Tests covering execution / lifecycle / risk

Present on main (CI green): Stage 6.4A open-risk recovery (incl. real PG), Stage 6.4B claim/duplicate delivery, Stage 6.5 enqueue stop fail-closed, health-route identity, concurrent reconcile release.

## Discrepancies

1. **Live deploy SHA:** Operator reported prefix `f546af7`; full 40-char SHA should be copied from Render Deploys for audit. Live health contract supports post–health-route deploy.
2. **Pending controlled_demo queue row:** Observed on a **historical/recovery** Neon branch — not proven identical to current production without production SELECT (see queue report).
3. **Main MQ5 on repo:** Executor sources identify as **v2.21** with heartbeat; MetaEditor compile of fix branch still **UNVERIFIED** as a separate gate.
4. Documentation branches are **not** on main; operational truth is main + live deploy + Neon.

## Safety

No production writes, deploys, or merges performed for this baseline inspection.
