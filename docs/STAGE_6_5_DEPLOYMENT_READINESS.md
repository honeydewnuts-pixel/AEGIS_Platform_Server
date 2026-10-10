# Stage 6.5 — Deployment Readiness (NOT EXECUTED)

Baseline main: `636863b96b9771e03cea5b22658577d293ba9459`

This document is an audit and plan. **No production deployment or migration is authorized by this document alone.**

## Architecture (from repository)

- **API host:** Render (`render.yaml` → Docker web service `aegis-api`)
- **Database:** Render Postgres / Neon (env `DATABASE_URL`)
- **Redis:** Render keyvalue service
- **Migration:** `docker/entrypoint.sh` runs `alembic upgrade head` on container start
- **MT5:** Windows VPS separately; OHLC Feed + Executor poll the API

## Migration 0023

- **Revision:** `0023_lifecycle_open_risk_applied` (revises `0022_aegis_executor_presence`)
- **Change:** Additive nullable boolean `aegis_position_lifecycle.open_risk_applied`
- **Default:** SQL `NULL` (no backfill)
- **Semantics:** NULL=historical/unknown; false=eligible recovery; true=applied
- **Downgrade:** drops column (loses applied flags; does not reverse portfolio open_risk_usd)
- **Safety:** Additive, non-blocking metadata column; no table rewrite expected on modern PostgreSQL
- **Do not** treat NULL as false in recovery (double-count risk)

## Durable queue states

| State | Deliverable | Supersedable | Notes |
|-------|-------------|--------------|-------|
| PENDING | Yes (claim) | Yes | New enqueue may EXPIRE prior PENDING |
| CLAIMED | No | No | Lease; ACK accepted; expiry → SUBMISSION_UNCERTAIN |
| SUBMISSION_UNCERTAIN | No | No | No auto-redelivery; late ACK accepted |
| ACKED / REJECTED / EXPIRED | No | Terminal | Idempotent ACK |

## Emergency stop

- Delivery (`/pending`, `/pending-batch`): stop ON or lookup failure → no claim (fail closed)
- Enqueue: stop ON or lookup failure → no new row (Stage 6.5 fail-closed)
- Stop does **not** cancel already-submitted broker orders

## EA compatibility (source only)

- Repository EA: **AEGIS_Executor v2.21** (heartbeat + UseServerSignals)
- Polls `/api/executor/pending-batch`
- Heartbeat: `POST /api/executor/heartbeat` (~30s)
- **Does not send claim_token** — server accepts tokenless ACK for legacy compatibility
- Source compatibility ≠ runtime proof; operator must confirm VPS compile/attach/heartbeat

## Controlled Demo gates (summary)

1. Environment identity (Demo account, production_authorized=false)
2. Connectivity (heartbeat, polling)
3. Idle integrity (no unexpected PENDING/CLAIMED/UNCERTAIN)
4. Controlled order (separate authorization)
5. Close and reconcile
6. Emergency-stop block of new claims
7. Acceptance decision

## Rollback cautions

- Reverting the application image does **not** reverse migration 0023
- Downgrade drops `open_risk_applied` and loses applied/unknown distinction
- SUBMISSION_UNCERTAIN rows must be operator-reconciled against the broker
- Existing broker positions are not closed by application rollback

## Governance

- production_authorized remains false
- V53.6 / RSI9 / Native unchanged
- No exactly-once broker claim
