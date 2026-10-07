# AEGIS Stage 3 Final Engineering Acceptance

## Governance (mandatory)

```
production_authorized = false
```

This document closes **engineering / human-controlled Demo plumbing**.

It does **not**:

- promote V53.6, RSI9, Native, or Generation 3;
- enable autonomous live trading;
- rewrite research verdicts.

Generation 3 research remains closed: **0 qualified candidates**, research-only.

---

## Repository

| Item | Value |
|------|--------|
| Starting engineering baseline (Stage 3.3 intro) | `52b4015d4628834ff564a1a64fad1e0685a73cc7` |
| Prior CI-green HEAD | `9f7ebe4faaef2a6ed1b4c9ad820bf4cc8be79906` |
| Branch | `main` |

(Actual ending HEAD is recorded after the acceptance commit is pushed.)

---

## What Stage 3 engineering includes

1. **Stage 3.1** — lifecycle `reconcile()` row lock (`FOR UPDATE`); single risk release.
2. **Stage 3.2** — portfolio `open_risk_usd` row lock on record/release.
3. **Stage 3.3** — ACK / position-closed / reconcile use **same AsyncSession** for lifecycle + open_risk (flush only; caller commits).
4. **Controlled Demo gate** — `controlled_demo_authorized` separate from `production_authorized`; methodology `controlled_demo_test` only.
5. **Executor v2.20** — methodology-aware direction; `CONTROLLED_DEMO` allows both BUY and SELL for engineering Demo only.

---

## Human-controlled Demo path

```
POST /api/demo-monitor/controlled-test-signal
  (controlled_demo_authorized=true, production_authorized=false)
        ↓
ExecutorSignalService pending queue
        ↓
GET /api/executor/pending-batch
        ↓
AEGIS_Executor v2.20 OrderSend (Demo)
        ↓
ACK → durable lifecycle + open_risk (same DB transaction)
        ↓
Position management (BE / trail / TIME) or manual MT5 close
        ↓
position-closed / DetectDisappearedPositions
        ↓
risk release (once) + audit/monitor events
```

**This is a human-controlled engineering Demo and does not constitute production strategy authorization.**

### Operator steps (summary)

1. Confirm MT5 Demo + Feed + Executor running; server `https://aegis-api-0z1p.onrender.com` healthy.
2. Use API key from Executor/Feed inputs (do not publish the key).
3. Send **one** controlled test signal (see operator procedure / curl in prior ops notes).
4. Confirm pending → fill on Demo → ACK on demo-monitor.
5. Close position in MT5 Trade (manual close is the preferred Demo completion method).
6. Confirm monitor/events reflect close; **stop** — do not repeat.

Full non-programmer checklist remains the separate operator procedure document.

---

## Acceptance matrix (software)

| Test | Expected | Evidence basis |
|------|----------|----------------|
| LONG authorized controlled-demo queue | PASS | `controlled_demo_test` + BUY publish → pending |
| SHORT authorized controlled-demo queue | PASS | SELL publish → pending |
| Research cannot enter queue | PASS | RSI9/Native/V53/transfer blocked |
| production_authorized stays false | PASS | publish payload + settings default |
| No unauthorized flip (autonomous gate) | PASS | gate_signal rejects flip/same-dir |
| Stage 3.3 shared session wiring | PASS | `session=session` ×3; helper FOR UPDATE |
| Concurrent reconcile single release | PASS | prior PG tests + CI |
| Rollback contract (shared session no self-commit) | PASS | unit tests |
| Executor CONTROLLED_DEMO both directions | PASS | MQ5 source branch |
| Bid/Ask research integrity suite | PASS | existing CI tests |
| Full CI | PASS | GitHub Actions on push |
| Live MT5 Demo order | **HUMAN** | not claimed by CI |

---

## Withdrawal

Withdrawal policy unchanged (Hybrid 70/30 ratchet design).  
Demo success does **not** trigger withdrawals.

---

## Research separation

Do not import Generation 3 artifacts into production configuration.  
Do not create production rulebooks from Generation 3.

---

## Known limitations

1. Live broker Demo fill/ACK/close must be confirmed by the human operator on the VPS.
2. MetaEditor compile of Executor is a VPS-side gate (not claimed by CI).
3. Full multi-statement DB rollback under injected mid-transaction failure is covered by shared-session design + unit patterns; concurrent PG tests cover double-release.

---

## Final governance statement

```
production_authorized = false
V53.6 = unchanged (historical research contract)
RSI9 = unchanged (research only)
Native = unchanged (research only)
Generation 3 = research-only / 0 qualified / unchanged
```
