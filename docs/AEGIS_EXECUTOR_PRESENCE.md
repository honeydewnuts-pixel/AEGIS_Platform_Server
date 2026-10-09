# AEGIS Executor Presence (Stage 6.2I)

## Purpose

Identify **MQL5 AEGIS_Executor** contact separately from:

- mobile device heartbeats
- Python `worker_registry` (mt5_worker)
- anonymous `/pending` poll timestamps (ReqBin / any client)

## Heartbeat

```http
POST /api/executor/heartbeat
X-API-Key: <account API key bound to account_id>
```

JSON body:

- `account_id` (required; must match key)
- `client_type` (`AEGIS_Executor`)
- `executor_version` (e.g. `2.21`)
- `execution_mode` (`CHART_ONLY` / `MULTI_PAIR`)
- `chart_symbol` (optional)

Default EA cadence: **30 seconds** (`HeartbeatSeconds` input; `0` = off).

**Trading independence:** HTTP failure is logged on the EA and **must not** block OrderSend, ACK, or position management.

## Admin status

```http
GET /api/admin/ops/executor-status/{account_id}
X-API-Key: <admin API key>
```

Fields: `exists`, `client_type`, `executor_version`, `execution_mode`, `last_symbol`,
`last_seen_at`, `age_sec`, `healthy`, `stale_after_sec` (default **90**), `server_time`, `source=durable_presence`.

`healthy` = `age_sec <= stale_after_sec`.

No API keys, hashes, or credentials are returned.

## Persistence

Table: `aegis_executor_presence` (Alembic `0022_aegis_executor_presence`).

One row per `account_id`. Survives API process restart.

## Deployment order (when authorized)

1. Deploy server with migration `0022`.
2. Compile updated `AEGIS_Executor.mq5` on VPS MetaEditor.
3. Attach / refresh EA (inputs unchanged except optional `HeartbeatSeconds`).
4. Admin: `GET .../executor-status/{account_id}` until `healthy=true`.
5. Only then consider a **new** controlled-demo signal (separate authorization).

## Rollback

1. Set EA `HeartbeatSeconds=0` or revert MQ5 binary.
2. Redeploy previous server revision (routes unused).
3. Table may remain; optional down migration drops it.

## Non-goals

Does not change `production_authorized`, research gates, queue claim/ACK, or emergency stop.
