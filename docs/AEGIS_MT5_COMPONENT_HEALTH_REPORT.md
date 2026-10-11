# AEGIS MT5 Component Health Report

**Main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Builder cannot access Windows VPS Experts logs** — runtime status for MT5 is largely **UNVERIFIED** except operator screenshots from earlier stages.

## Component matrix

| Component | Responsibility | Repo version | Runtime status |
|-----------|----------------|--------------|----------------|
| **AEGIS_OHLC_Feed.mq5** | POST closed/current bars to `/api/mt5/ohlc/stream` | **v2.05** in release tree | **UNVERIFIED** now (earlier operator: cycles ok) |
| **AEGIS_Executor.mq5** | Poll pending, OrderSend, ACK, PM, heartbeat | **v2.21** source on main (heartbeat); MetaEditor compile of fix branch **UNVERIFIED** | **UNVERIFIED** presence |
| **Backend (Render)** | Queue, auth, risk, lifecycle, OHLC ingest | `f546af7` + health 3.0.3 | **PASS** (live health) |
| **Mobile monitor** | Display connection / pairs / offline | Depends on API fields | **UNVERIFIED** this session |
| **Windows worker / VPS** | Hosts MT5 + EAs | N/A | **UNVERIFIED** |

## Critical separation

- **OHLC Feed healthy ≠ Executor healthy ≠ Python mt5_worker connected.**
- Mobile “MT5 worker: not connected” historically referred to **Python worker registry**, not necessarily OHLC Feed HTTP success.
- Controlled Demo execution path is: **Executor poll → durable claim → OrderSend → ACK → lifecycle**, not the screenshot→HOLD path.

## Authorization to execute orders

- Server: `production_authorized` remains false by design; controlled_demo path is separate and narrow.
- Executor: must have `UseServerSignals=true`, correct AccountId/ApiKey, and receive `authorized=true` payloads for controlled_demo.
- Repo Executor defaults include `AEGIS_MODE_CHART_ONLY` and heartbeat every 30s when enabled.

## Verification without placing orders

1. Admin: `GET /api/admin/ops/executor-status/ACC-1987D3D2E6` → `exists`, `healthy`, `executor_version`, `last_seen_at`.
2. OHLC: server logs / stream timestamps for account symbols (operator).
3. Executor Experts: poll URL, HTTP codes, “no signal” vs error.
4. Live health already shows API + Redis **ok**.

## Known failure modes

| Mode | Effect |
|------|--------|
| Feed down | HOLD / WAITING_FOR_OHLC research path; no fabricated OHLC |
| Executor down | Durable PENDING accumulates; no claim |
| CHART_ONLY misconfig | Only chart symbol polled |
| Unauthorized methodology | Server blocks executable delivery |

## Status

**Overall MT5 runtime health: UNVERIFIED** pending operator presence + Experts evidence.  
**Backend: PASS** for process/Redis health at inspection time.
