# AEGIS EURUSD Controlled-Demo Execution — Forensic Root-Cause Report

**Investigation date:** 2026-10-14  
**Main HEAD inspected:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Documentation branch tip (before this commit):** `e85d49b2f2968189bb7970cf456ae3d9ea9da01c`  
**Mode:** Read-only forensics — no production mutation, no new signals, no EA install

---

## 1. Executive summary

The original controlled-demo EURUSD SELL was **accepted by the API and persisted** as a durable queue row under signal_id `9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b` (account `ACC-1987D3D2E6`). Live diagnostics on or after 2026-10-08 showed it still **PENDING**, `claimed_at=null`, `attempt_count=0` — **no successful claim and no OrderSend**.

The monitor event of **2026-10-13 09:46:37** — `Rejected: SELL EURUSD`, reason **`stale`**, `ORDER_REJECTED`, `ACKED FAILURE` — matches the **Executor MQ5** path that compares `created_at_ms` to `TimeGMT()` and rejects when age exceeds **`MaxSignalAgeSec` (default 300 seconds / 5 minutes)**, then sends a failure ACK with message `"stale"`.

**Strongest evidence-supported explanation:**  
The instruction remained **PENDING for far longer than the 5-minute Executor freshness window** (creation ≈ 2026-10-08 08:08 UTC → rejection ≈ 2026-10-13 09:46). When an Executor (reported as v2.21) finally processed the delivered payload, it **correctly** rejected the command as **stale** and recorded a failure ACK. That is **command-age protection**, not market OHLC staleness, and not a broker fill failure.

**What is not proven:** That the “old” Executor never polled HTTP at all; that v2.21 was the only client to ever see the row; or the exact live queue status after the 2026-10-13 ACK without a fresh read-only query.

**NO_POLL_YET** on the mobile monitor is **not reliable proof** that no Executor polled: the monitor reads **in-memory** `ExecutorSignalService._last_poll_ms`, and the durable `/pending` and `/pending-batch` routes **do not call `note_poll()`**. Render restarts also clear that map.

---

## 2. Incident chronology (evidence-backed)

| When | Event | Classification |
|------|--------|----------------|
| ≈ 2026-10-08 08:08:52 UTC | Controlled-demo publish; `signal_id=9fc3cb49-…`; EURUSD SELL 0.01 | **CONFIRMED** (prior live API response + durable diagnostic) |
| Same interval | API note: pending; attach Executor; poll pending-batch | **CONFIRMED** (API response text) |
| Days after create (pre–v2.21 attach) | Durable diagnostic: status=PENDING, claimed_at=null, attempt_count=0, no tickets | **CONFIRMED** (prior Stage 6.2 live read) |
| Same period | GET `/pending` could return `has_signal=true` with controlled_demo fields | **CONFIRMED** (prior live JSON) |
| 2026-10-11 window | Render logs: repeated pending-batch HTTP 200 (account in traffic) | **CONFIRMED** (operator log excerpt) — does not prove this signal was in the body |
| ≈ 2026-10-13 09:46:37 | Monitor: Rejected SELL EURUSD, reason stale, ORDER_REJECTED, ACKED FAILURE | **CONFIRMED** (operator monitor display) |
| Same | Operator interpretation: v2.21 encountered old instruction | **HYPOTHESIS** on version identity; stale path **CONFIRMED** in source |

Age at rejection: on the order of **~5 days** ≫ **300 s** → stale reject is expected if `created_at_ms` is the original create time.

---

## 3. Verified identity of the original instruction

| Field | Value | Status |
|-------|--------|--------|
| Endpoint | `POST /api/demo-monitor/controlled-test-signal` | **CONFIRMED** (`demo_monitor_router.py`) |
| Account | `ACC-1987D3D2E6` | **CONFIRMED** |
| Symbol / side / volume | EURUSD / SELL / 0.01 | **CONFIRMED** |
| UUID `9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b` | **`signal_id`** (also unique key on durable queue) | **CONFIRMED** |
| Methodology / rule | `controlled_demo_test` | **CONFIRMED** |
| `controlled_demo_authorized` | `true` | **CONFIRMED** |
| `production_authorized` | `false` | **CONFIRMED** |
| Original curl body | Not recovered in this session | **UNVERIFIED** |
| Exact original HTTP status | Prior reports: success with `ok: true` | **STRONGLY SUPPORTED** |

**Identifier rule:** Do not treat `signal_id` as a separate “queue id”; the durable row is keyed by **`signal_id`** (`uq_exec_queue_signal_id`).

---

## 4. Identifier correlation table

| Identifier | Role |
|------------|------|
| `9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b` | `signal_id` / durable queue primary business key |
| `ACC-1987D3D2E6` | Account scope for queue, poll, ACK |
| `controlled_demo_test` | Methodology + rule_name allowing Path B execution auth |
| Monitor “ORDER_REJECTED — stale” | Executor failure ACK message `"stale"` + retcode path `-3` |

Correlation of monitor rejection to this UUID: **STRONGLY SUPPORTED** (same account/symbol/side, operator timeline, only long-lived controlled-demo pending row known from diagnostics). Exact `signal_id` on the failure ACK body: **UNVERIFIED** without ACK log or DB row post-event.

---

## 5. API acceptance and persistence

**Source path:**

1. `publish_controlled_test_signal` (`demo_monitor_router.py`)  
2. In-memory publish + **durable enqueue** with `controlled_demo_authorized=True`, `production_authorized=False`  
3. Status starts **PENDING**

**Persistence:** Durable `aegis_execution_queue` — **CONFIRMED** by design and prior live diagnostic (status PENDING, no claim).

---

## 6. Lifecycle stages (actual design)

```
curl controlled-test-signal
  → validation + controlled_demo auth
  → durable PENDING row (signal_id)
  → Executor GET /pending or /pending-batch
  → durable get_pending: PENDING → CLAIMED (lease 120s)
  → EA HandleSignalJsonObject
  → age check vs MaxSignalAgeSec (300)
  → if stale: AckServerFull(..., ok=false, "stale")  [NO OrderSend]
  → POST /ack → durable REJECTED (ok=false)
```

**First divergence from “trade consummated”:**  
Between **create** and **timely claim+execute within 300s**. Prior evidence: **never claimed** for days → divergence at **Executor discovery/claim/execute**, not at API accept.

**ORDER_REJECTED / stale:** **Executor-side validation before OrderSend**, not MT5 broker reject. Source sends ACK with message `"stale"` and does not call OrderSend on that path.

---

## 7. Old Executor investigation

| Question | Finding |
|----------|---------|
| Intended source | Repository has evolved; historical EX5 on VPS **UNVERIFIED** |
| Mode reported earlier | CHART_ONLY, EURUSD M5, account match | **STRONGLY SUPPORTED** (prior VPS screenshots) |
| Polls pending-batch 200? | HTTP 200s in Render logs | **CONFIRMED** for some client; **UNVERIFIED** that body included this signal |
| EA checks `authorized` field? | **No** — uses `has_signal` / signals array | **CONFIRMED** |
| Why attempt_count stayed 0? | No successful durable claim before diagnostics | **CONFIRMED** as observed; **cause of non-claim UNVERIFIED** (could be deploy lag, WebRequest, claim code not yet live, CHART_ONLY vs batch, restart, auth HTTP failures, etc.) |

**Old Executor “failure”:** **UNVERIFIED** as a specific code defect. **STRONGLY SUPPORTED** that **no successful processing** of this signal occurred while it was still young.

---

## 8. Executor v2.21

| Item | Finding |
|------|---------|
| Source `#property version` | `"2.21"` in `release/desktop/AEGIS_Executor.mq5` | **CONFIRMED** |
| `MaxSignalAgeSec` | default **300** | **CONFIRMED** |
| Stale path | `created_at_ms` vs `TimeGMT()*1000`; ACK `"stale"`; MarkHandled | **CONFIRMED** |
| Controlled demo | methodology containing CONTROLLED_DEMO allows BUY/SELL | **CONFIRMED** |
| Installed EX5 identity | Operator report only | **UNVERIFIED** independently |
| Heartbeat / presence | Separate Stage 6.2I feature; not required for stale path | — |

**Proven:** Source behaviour for stale rejection.  
**Not proven:** Binary on VPS is bit-identical to this source; Experts log of the event.

---

## 9. Exact stale-rejection source

**File:** `release/desktop/AEGIS_Executor.mq5` / `windows-desktop/mq5/AEGIS_Executor.mq5`  

```text
created_at_ms from JSON
ageSec = (TimeGMT()*1000 - created) / 1000
if ageSec > MaxSignalAgeSec (300):
  MarkHandled(signalId)
  AckServerFull(..., retcode -3, ok false, message "stale")
  return false   // no OrderSend
```

**Timestamp field:** signal/queue **`created_at_ms`** from server payload (`row.created_at` in durable `_to_payload`).  
**Not** OHLC bar time. **Not** poll time.  
**Intentional** delayed-command protection.

Server durable **does not** auto-expire PENDING solely for age; the **EA** enforces the 300s window on process. A PENDING row can therefore sit for days until an EA claims and rejects it.

---

## 10. Poll monitor (`NO_POLL_YET`)

**Implementation:** `demo_execution_monitor.py` reads `executor_signals.last_poll_ms(account_id)`.  
**Updated only via** `ExecutorSignalService.note_poll()`.

**CONFIRMED gap:** Durable routes `GET /api/executor/pending` and `GET /api/executor/pending-batch` **do not call `note_poll()`**.  
In-memory poll bookkeeping is therefore **often empty** even when Render shows HTTP 200 pending-batch traffic.

Additionally, `_last_poll_ms` is **process memory** → lost on Render restart.

**Conclusion:** Monitor `NO_POLL_YET` **can coexist** with real Executor polls. **Do not** treat it as proof the EA never contacted the server.

---

## 11. Queue and risk accounting

| Topic | Finding |
|-------|---------|
| Pre-v2.21 state | PENDING, no claim, no tickets | **CONFIRMED** (prior diagnostic) |
| After failure ACK | Expected durable status **REJECTED** (`ack` sets ACKED if ok else REJECTED) | **CONFIRMED** in source; **live row after 2026-10-13 UNVERIFIED** this session |
| Open risk on create | Controlled-demo path does not reserve portfolio risk until successful open ACK | **STRONGLY SUPPORTED** by ACK/lifecycle design |
| Risk after stale reject | No position → no open-risk increment expected | **STRONGLY SUPPORTED** |
| Double release | Not applicable if risk never applied | — |

**Read-only operator check (do not mutate):**

```sql
SELECT signal_id, status, claimed_at, attempt_count, ack_ok, message,
       position_ticket, order_ticket, created_at, updated_at
FROM aegis_execution_queue
WHERE signal_id = '9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b';
```

(Confirm column names against live schema if any differ.)

---

## 12. Relationship to OHLC streaming diagnostic

**Separate pipelines.** Controlled-demo execution does **not** require screenshot OHLC or stream freshness for authorization.  
Stale here = **command age**, not **market-data age**.  
HOLD `v40_research_awaiting_ohlc` is **not** the mechanism for this incident.

---

## 13. Root cause

### Strongest evidence-supported explanation

**The controlled-demo signal remained durable PENDING far beyond the Executor’s 300-second `MaxSignalAgeSec` window. When an Executor finally delivered/processed it, the EA correctly rejected it as `stale` and failure-ACKed — so no broker order was sent.**

Classification: **STRONGLY SUPPORTED** (create time + rejection time + MQ5 source + prior unclaimed PENDING).

### Not established as root cause

- Specific defect unique to “old” vs v2.21 binaries without Experts logs.  
- Broker rejection.  
- Mobile app offline.  
- OHLC Feed failure.  
- Wrong stale clock/timezone in the sense of “false stale” for a fresh signal (age was multi-day).

### Alternative explanations (with confidence)

| ID | Cause | Confidence |
|----|--------|------------|
| A | Old EA never polled | **HYPOTHESIS** (NO_POLL_YET unreliable) |
| B | Polled but signal not in response | **HYPOTHESIS** |
| C–F | Parse/claim/submit/ACK loss while young | **UNVERIFIED**; contradicted by long PENDING + zero attempts |
| G | Incomplete transition left PENDING | **CONFIRMED** outcome; mechanism **UNVERIFIED** |
| H | v2.21 correctly rejected expired pending | **STRONGLY SUPPORTED** |
| I | Wrong timestamp field | **NOT SUPPORTED** for multi-day age |
| J | Restart lost in-memory only | **CONFIRMED** for memory path; durable survived |
| K | Auth/format mismatch | **HYPOTHESIS** for early window |
| L | Monitor misrepresent | Partial: **CONFIRMED** for NO_POLL_YET semantics |

---

## 14. Tests performed

| Test | Result |
|------|--------|
| Source inspection of demo publish, durable queue, pending-batch, ACK, MQ5 stale, monitor poll | Done (not a runtime test) |
| Production DB query | **NOT RUN** (no production session) |
| Broker / OrderSend | **NOT RUN** (prohibited) |
| Isolated unit tests this session | **NOT RUN** |

---

## 15. Proposed corrective action (documentation only — **not implemented**)

No change that weakens stale protection.

**Optional engineering (separate authorization):**

1. Call `note_poll(account_id)` from durable `/pending` and `/pending-batch` so the monitor matches real polls.  
2. Document operator procedure: controlled-demo signals must be executed by an attached Executor **within MaxSignalAgeSec** (default 5 minutes), or they will be stale-rejected.  
3. Optional server-side: mark long-PENDING controlled-demo rows EXPIRED after a documented TTL **without** auto-trading (operator-visible terminal state).  
4. Do **not** requeue `9fc3cb49-…`; any future Demo requires a **new** authorized controlled-test signal under a fresh test plan.

---

## 16. Regression / safety requirements for any future fix

Preserve: MaxSignalAgeSec (or explicit documented policy), account match, controlled_demo vs production gates, claim/lease, failure ACK idempotency, no research promotion, V53.6 frozen, no silent OrderSend on stale.

---

## 17. Remaining operator evidence (minimal)

1. Read-only SQL for signal_id `9fc3cb49-…` current status (expect REJECTED if ACK landed).  
2. Optional: one Experts line from 2026-10-13 ~09:46 with signal_id / stale.  
3. Do **not** recreate the same UUID; do not force re-execute.

---

## 18. Final status and acceptance

| Criterion | Status |
|-----------|--------|
| Original identity | **CONFIRMED** |
| Lifecycle reconstruction | **COMPLETE** to available evidence |
| Stale source | **CONFIRMED** (MQ5 MaxSignalAgeSec) |
| Old vs v2.21 | Separated; old non-execution **UNVERIFIED** mechanism |
| NO_POLL_YET | **EXPLAINED** (in-memory; durable path skips note_poll) |
| Risk | No evidence of open risk from unfilled demo | **STRONGLY SUPPORTED** |
| Root cause | **STRONGLY SUPPORTED** as above; not elevated to absolute CONFIRMED without post-ACK DB row |
| Production safety | No prohibited actions this investigation |

**Before another controlled-demo test:** Executor attached and polling; operator ready to observe within **5 minutes** of publish; presence/heartbeat preferred; do not rely on NO_POLL_YET alone.

---

## Production safety confirmation

No production DB writes, deploys, migrations, queue mutations, new signals, EA installs, broker orders, or `production_authorized` changes were performed.
