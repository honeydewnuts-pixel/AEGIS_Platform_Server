# AEGIS OHLC Stream and HOLD Root-Cause Report

**Inspected main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Report date:** 2026-10-13  
**Overall status:** **INCOMPLETE** for production-time correlation; **CONFIRMED** source-level explanation of pipeline separation

---

## 1. Executive conclusion

**The continuous OHLC Feed streaming path and the HOLD / `v40_research_awaiting_ohlc` path are not the same pipeline.**

Successful repeated `POST /api/mt5/ohlc/stream` HTTP 200 responses prove the server **accepted** Feed posts (and, when bars validate, updated **in-memory** stream state). They do **not** prove that a later **screenshot / mobile analyze** request obtained a non-stale, symbol-matched snapshot with enough bars for research evaluation.

HOLD records with `rule_name=v40_research_awaiting_ohlc` are produced on the **observation / universal analysis** path when synchronized OHLC is missing or insufficient for that analysis call. The detail text that mentions “worker offline or chart not ready” is a **generic fail-safe phrase** in source; it is **not** a precise assertion that the Python `mt5_worker` or the OHLC Feed process was down.

**Do not conclude that OHLC streaming stopped** based only on HOLD rows, if Feed HTTP 200s are observed in the same operational window.

**Do not conclude the full OHLC→tradeable-signal path is healthy** based only on HTTP 200.

This HOLD path is **unrelated by design** to the pending controlled-demo EURUSD queue UUID unless the same `signal_id` is proven to appear in both stores.

---

## 2. Source files and functions inspected

| Area | Location |
|------|----------|
| Stream ingest API | `backend/app/api/ohlc_router.py` — `POST /ohlc/stream` |
| Stream store | `backend/app/services/ohlc_stream_service.py` — `OhlcStreamService.ingest`, `.get`, `.status` |
| Startup log line | `backend/app/core/startup.py` — `"OHLC stream service ready (independent of screenshots)"` |
| Analyze / screenshot path | `backend/app/api/brain_router.py` — stream prefer over one-shot job; observation flags |
| Acquisition state | `backend/app/services/observation_package.py` — `derive_acquisition_state`, `derive_hold_reason` |
| Research HOLD rule | `backend/app/services/universal_analysis_service.py` — `v40_research_awaiting_ohlc` when bars &lt; 5 or no OHLC |
| Symbol normalize | `app.utils.symbol_normalize.normalize_symbol` |
| Executor poll | `backend/app/api/executor_router.py` — `pending-batch` (separate from HOLD) |

---

## 3. End-to-end data flow (two paths)

### Path A — Continuous Feed (owner’s Render log)

```
AEGIS_OHLC_Feed.mq5
  → POST /api/mt5/ohlc/stream  (account_id, symbol, timeframe, bars, …)
  → ohlc_router validation
  → OhlcStreamService.ingest  (in-memory dict keyed account|base_symbol|TF)
  → HTTP 200 { ok, … } when bars parse
```

**Not** derived from screenshots. Startup explicitly logs independence from screenshots.

**Storage:** **process memory only** (`self._store`). Lost on Render restart/redeploy until the Feed posts again.

**Freshness:** `get(..., max_age_ms=15*60*1000)` marks `stale=True` if `received_at_ms` older than 15 minutes.

**Symbol key:** normalized base symbol (suffixes stripped) + account + TF.

### Path B — Screenshot / mobile analysis (HOLD generation)

```
Client upload / brain analyze
  → optional one-shot MT5 worker snapshot job (legacy path)
  → preferred: ohlc_stream.get(account, symbol, TF)
  → if stream missing/stale → ohlc_missing_reason set
  → UniversalAnalysisService.analyze(market_snapshot)
  → if no usable bars (e.g. len(bars) < 5) → HOLD + v40_research_awaiting_ohlc
  → validate_observation → ohlc_valid flag
  → derive_acquisition_state → WAITING_FOR_OHLC when screenshot OK but ohlc_valid false
  → signal_history style HOLD (research; production_authorized false)
```

**Executor `pending-batch`:** polls durable/memory **execution** queue for authorized signals. HTTP 200 on pending-batch proves **poll reached the API**, not that screenshot OHLC was synchronized.

---

## 4. What the 2026-10-11 Render log proves / does not prove

**Log window (operator):** ~14:26–14:28 UTC; startup; Redis; neural/rulebook init; “OHLC stream service ready (independent of screenshots)”; repeated `POST .../ohlc/stream` 200; repeated `GET .../pending-batch` 200; account `ACC-1987D3D2E6`; multi-symbol list on batch poll.

| Proves | Does not prove |
|--------|----------------|
| API process was up and handling those requests | Continuous 24/7 uptime beyond the excerpt |
| Stream endpoint returned success for those POSTs | Every symbol the mobile app later analyzes was in the store |
| Feed↔API HTTP path worked for that interval | Payloads always contained ≥5 valid bars (need body audit) |
| Executor (or client) was polling pending-batch | Any OrderSend or claim occurred |
| Stream service was initialized in that process | State survived later restarts |
| | Screenshot path had `ohlc_valid=true` for each HOLD timestamp |
| | Python worker_registry “connected” |

Internal container IPs are **not** mapped here to named VPS identities without additional evidence.

**Successful POST meaning (from source):**

1. Request reached the route (**yes** if 200).  
2. Payload validated enough to ingest **or** returned ok:false in body while still possibly 200 — operator should confirm response **body** `ok` field in future logs.  
3. State stored **in memory for that process** when ingest succeeds.  
4. Available to signal/analyze **only if** same account+symbol+TF key and not stale.  
5. Fresh/usable for research eval **only if** snapshot includes sufficient `bars` for `UniversalAnalysisService`.

These stages are **distinct**.

---

## 5. HOLD correlation

| Question | Finding |
|----------|---------|
| HOLD path screenshot-dependent? | **Yes** (observation package + analyze upload path) |
| Same as continuous stream? | **No** — stream can succeed while a given analyze call still lacks OHLC |
| Message “worker offline”? | **Generic text** in `derive_acquisition_state` when screenshot OK and `ohlc_valid` false — **not** a live probe of worker_registry |
| Link to controlled-demo queue `9fc3cb49-…`? | **Not established** — different creation path (`controlled-test-signal`) |
| Production HOLD timestamps vs stream | **NOT TESTED** (no production DB access this session) |

### Operator read-only queries (production)

```sql
-- Recent HOLD / awaiting OHLC (adjust time window)
SELECT id, account_id, symbol, signal, rule_name, confidence, created_at
FROM signal_history
WHERE rule_name = 'v40_research_awaiting_ohlc'
ORDER BY created_at DESC
LIMIT 50;
```

(Exact `signal_history` column names may vary; confirm with `\d signal_history` or information_schema if needed.)

---

## 6. Failure-class evaluation

| ID | Candidate | Classification | Evidence |
|----|-----------|----------------|----------|
| A | Feed invalid payload despite HTTP 200 | **SUPPORTED BUT UNCONFIRMED** | Possible if status 200 with body ok:false; need response body samples |
| B | Accept but not retain usable state | **CONFIRMED** partial | In-memory only; lost on restart — by design |
| C | Symbol alias / suffix mismatch | **SUPPORTED BUT UNCONFIRMED** | Normalize exists; mismatch still possible if analyze symbol ≠ streamed base |
| D | Timeframe mismatch | **SUPPORTED BUT UNCONFIRMED** | Key includes TF; default M5 |
| E | Stale timestamps | **SUPPORTED BUT UNCONFIRMED** | 15-minute stale threshold in `get()` |
| F | Sequence/duplicate reject | **NOT SUPPORTED** as primary | Ingest sorts/cleans bars; no evidence of seq kill-all |
| G | Signal worker different state source | **CONFIRMED** | Screenshot path vs stream store; optional one-shot job |
| H | Worker-presence false offline | **SUPPORTED BUT UNCONFIRMED** | Mobile “worker” ≠ stream; HOLD text over-generalizes |
| I | Screenshot readiness coupled to OHLC | **CONFIRMED** | WAITING_FOR_OHLC when screenshot OK and ohlc not valid |
| J | Race stream vs signal check | **SUPPORTED BUT UNCONFIRMED** | Possible around restart or first post |
| K | HOLD message too broad / misleading | **CONFIRMED** | “worker offline or chart not ready” used generically |
| L | Other | — | e.g. analyze symbol empty / wrong pair in app settings |

**Root cause (source-level):** HOLD reflects **missing usable OHLC on the observation/analyze package**, not a proven stop of the Feed HTTP stream.  
**Runtime root cause for specific HOLD rows:** **BLOCKED / INCOMPLETE** without timestamps + stream status for the same account/symbol.

---

## 7. Tests

| Item | Result |
|------|--------|
| New isolated OHLC/HOLD unit tests this session | **NOT RUN** (no code change) |
| Existing CI on main `f546af7` | Green (prior verification); not re-executed as OHLC-specific suite here |

Recommended future isolated tests (not implemented this session): ingest→get visibility; stale flag; symbol normalize; analyze HOLD when bars&lt;5; HOLD reason when stream healthy but analyze symbol missing.

---

## 8. Correction policy outcome

**No code correction merged or proposed for deploy.**

Justified **future** improvement (isolated branch only if owner authorizes):

- Narrow HOLD / acquisition summary text to distinguish: no stream row / stale stream / insufficient bars / symbol mismatch — **without** relaxing freshness or authorization.

Improving copy does not authorize trades.

---

## 9. Operator evidence still useful

1. One raw **JSON body** of a successful stream POST response (`ok` field) — redact keys.  
2. After Feed runs ≥1 minute: any admin/stream status endpoint output if exposed, or log line counts per symbol.  
3. HOLD rows timestamps + **symbol** vs symbols the Feed is configured to send.  
4. Whether Render **restarted** between Feed “always on” belief and HOLD times.  
5. App **Trade pair** setting at HOLD time.

---

## 10. Production / trading confirmation

No production DB writes, deploys, EA changes, queue mutations, controlled-demo signals, or broker orders were performed for this report.
