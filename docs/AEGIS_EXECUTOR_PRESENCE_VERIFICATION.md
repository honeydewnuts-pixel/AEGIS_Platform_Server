# AEGIS Executor Presence Verification

**Main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Account of interest:** `ACC-1987D3D2E6`

## Endpoint (read-only)

```
GET https://aegis-api-0z1p.onrender.com/api/admin/ops/executor-status/ACC-1987D3D2E6
```

**Authorization:** Admin API key via header `X-API-Key` (same class of key used for admin ops / bootstrap admin — **not** a normal account trading key).  
Enter the key only in your browser/ReqBin environment. **Never** paste the key into chat, GitHub, or docs.

```bash
# Operator machine only — do not commit the key
curl -sS \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Accept: application/json" \
  "https://aegis-api-0z1p.onrender.com/api/admin/ops/executor-status/ACC-1987D3D2E6"
```

## Implementation source

- Route: `admin_ops_router` — `GET /api/admin/ops/executor-status/{account_id}`  
- Auth: `verify_api_key` + `require_admin`  
- Data: `ExecutorPresenceService.get_status` reading table `aegis_executor_presence`  
- Updated only by authenticated `POST /api/executor/heartbeat` from the EA

## Expected response fields (when a row exists)

| Field | Meaning |
|-------|---------|
| `exists` | Presence row found for account |
| `healthy` | `last_seen_at` within service stale window (~90s class; heartbeat default 30s) |
| `last_seen_at` | Last successful heartbeat timestamp |
| `age_sec` | Seconds since last_seen |
| `executor_version` | e.g. `"2.21"` if EA reports it |
| `client_type` | e.g. `AEGIS_Executor` |
| `execution_mode` | e.g. enum string such as `AEGIS_MODE_CHART_ONLY` |
| `last_symbol` | Chart symbol last reported |
| `stale_after_sec` | Threshold used for healthy |
| `server_time` | Server clock for comparison |
| `source` | e.g. `durable_presence` |

When **no** heartbeat has ever been stored:

```json
{"exists": false, "healthy": false, "last_seen_at": null, ...}
```

## How to interpret

| Observation | Interpretation |
|-------------|----------------|
| `exists=false` | Updated EA with heartbeat not installed, not running, or not authenticating heartbeat |
| `exists=true`, `healthy=false` | Was seen; now stale (stopped, network, or wrong account) |
| `exists=true`, `healthy=true` | Recent heartbeat for that account |
| Version ≠ expected | Wrong build attached on VPS |
| `execution_mode` CHART_ONLY | Only chart symbol path unless MULTI_PAIR configured |

**Does not prove:** successful claim of a queue row, OrderSend, or ACK.

## Complementary checks (operator VPS)

1. MT5 Experts: `AEGIS_Executor` version print on init.  
2. Experts: heartbeat / poll errors (HTTP 401/403/empty).  
3. Inputs: `AccountId=ACC-1987D3D2E6`, `UseServerSignals=true`, `ServerUrl` → production API.  
4. DB Q9 in inventory runbook should match API `last_seen_at` if heartbeat works.

## Builder note

This stage documents the procedure only. Builder did **not** call the endpoint with production admin credentials.
