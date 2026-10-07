# AEGIS Stage 4 — Recovery, Reconciliation & Operational Readiness

## Governance

```
production_authorized = false
```

V53.6, RSI9, Native, and Generation 3 remain **unchanged** and **not** production-authorized.  
Generation 3 remains closed: **0** qualified candidates.

This stage is **operational readiness**, not strategy development and not autonomous trading authorization.

---

## Starting point

| Item | Value |
|------|--------|
| Expected baseline | `633229ce9aee0670f7cc1eac18946931fedd9c3a` |
| Branch | `main` |

(Ending HEAD recorded after Stage 4 commits land.)

---

## Architecture reviewed

| Component | Recovery role |
|-----------|----------------|
| `ExecutorSignalService` | In-memory pending queue; signal_id ACK completion set → **idempotent ACK** |
| `DurableLifecycleService` | DB lifecycle; `FOR UPDATE` on close/reconcile; single risk release |
| `PortfolioRiskService` | Shared-session open_risk record/release (Stage 3.3) |
| `AEGIS_Executor.mq5` | Startup `reconcile-positions`; `DetectDisappearedPositions`; `WasHandled` signal_id |
| Controlled Demo gate | Separate from production; research methods blocked |

---

## Failure scenarios (expected behaviour)

### 3.1 Server restart after reservation

Durable lifecycle + subscription `open_risk_usd` persist in Postgres.  
In-memory pending queue is **lost** on process restart → Executor may re-poll empty queue (safe).  
Open broker positions remain; restart reconcile attaches tickets to durable rows.

### 3.2 Fill before ACK / server restart

Executor retains local handled-signal state where possible; on restart, broker positions are posted via `reconcile-positions`.  
Server matches by `signal_id` comment when present; otherwise ticket enters **unknown / reconciliation_required** (not auto-adopted as strategy).

### 3.3 Executor restart with open position

`ReconcileBrokerPositionsOnStartup` + position manager resume on MagicNumber positions.  
Does not open a second position for the same handled signal_id.

### 3.4 Network interruption

ACK retry is idempotent (`completed` map).  
Duplicate pending-batch polls return same pending until ACK.  
Reconcile repairs broker-absent vs server-open mismatch by releasing risk **once**.

---

## Idempotency model

| Event | Key | Behaviour |
|-------|-----|-----------|
| Signal pending | `account_id\|symbol` | One pending row per symbol |
| Order / signal | `signal_id` | Executor `WasHandled`; server ACK completed set |
| ACK | `signal_id` | Second ACK → `idempotent=true`, no second risk |
| Close / reconcile | lifecycle row lock | Only first transition to `RISK_RELEASED` releases risk |

---

## Broker / server mismatch

| Case | Server | Broker | Action |
|------|--------|--------|--------|
| A | OPEN | CLOSED / absent | Reconcile → `RISK_RELEASED`, release risk once |
| B | CLOSED | OPEN | **Do not** fabricate close; ticket listed as unknown / needs review |
| C | none | OPEN unknown | `unknown_broker_tickets` reported; **not** auto-classified as AEGIS strategy |

---

## Lifecycle states (vocabulary)

```
SIGNAL_QUEUED → ORDER_SENT → POSITION_OPEN → RISK_RELEASED
                      ↘ ORDER_REJECTED
              → RECONCILIATION_REQUIRED (exception)
```

Terminal: `RISK_RELEASED`, `ORDER_REJECTED`, `POSITION_CLOSED`.  
Repeated close on already-released → `ALREADY_RELEASED` (zero additional risk).

---

## Emergency control (existing — no new kill-switch invented)

1. **Stop new orders:** disable AutoTrading / remove Executor or set `UseServerSignals=false`.  
2. **Stop Feed:** remove OHLC Feed EA (stops autonomous closed-bar path).  
3. **Preserve management:** leave Executor attached to manage existing Magic positions, or  
4. **Manual close:** close in MT5 Trade → `DetectDisappearedPositions` notifies server.  
5. **Restart:** start server → attach Feed/Executor → startup reconcile.  
6. **Do not** set `production_authorized=true` during recovery.

---

## Withdrawal readiness (no actual withdrawals)

Design remains Hybrid 70/30 ratchet with double-up trigger.  
Stage 4 verifies accounting prerequisites only; **no withdrawal is triggered** by recovery tests.

---

## Production safety

Recovery paths **cannot**:

- set `production_authorized=true`;
- promote V53.6 / RSI9 / Native / Generation 3;
- auto-adopt unknown broker positions as strategy trades.

---

## Known limitations

1. Pending signal queue is process-memory — lost on API restart (fail-safe: no ghost executes from stale memory after cold start until new publish).  
2. Live VPS Demo remains a separate human acceptance gate.  
3. Full multi-node distributed lock beyond Postgres row locks is out of scope.

---

## Explicit statement

```
production_authorized = false
V53.6 = unchanged
RSI9 = unchanged
Native = unchanged
Generation 3 = research-only / unchanged
```
