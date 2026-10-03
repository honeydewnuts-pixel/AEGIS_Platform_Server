# AEGIS EXECUTION INTEGRITY AUDIT

**Date:** 2026-10-03  
**Stage:** Stage 2 — EXECUTION-INTEGRITY HOLD  
**Commit:** (see git after push)

---

## Mandate

- No new strategy discovery  
- No retune of RSI9 / Native / V53.6  
- No production promotion  
- No deletion of research artifacts  
- USDCHF RSI9 SHORT marked **INVALIDATED — EXECUTION MODEL ERROR** (artifact preserved)

---

## 1. Current execution architecture

| Layer | Role | Bid/Ask behavior |
|-------|------|------------------|
| **OHLC Feed v2.05** | Streams broker OHLC / equity / margin | Server receives mid or bid/ask fields depending on path |
| **Live evaluators** (RSI9, Native, V31) | Signal only on closed bar | Do **not** simulate fills; emit SELL/BUY + stop metadata |
| **Research / transfer scripts** (offline) | PF / gates / rulebook qualification | **Own fill model** — primary integrity risk |
| **Autonomous OHLC → risk → Executor queue** | Operational path | Sizing from close ± ATR; Executor fills at market |
| **Executor v2.20** | OrderSend + position manager | **SELL@BID, BUY@ASK** (broker-correct opens) |
| **live_short_position_manager** | V31/V53.6 short management model | Stop on **BidHigh**; R from BidClose; TIME on BidClose |

Two separate execution worlds must not be conflated:

1. **HISTORICAL V53.6 RECONSTRUCTION** — frozen research convention (`next-bar AskOpen` for SHORT).  
2. **BROKER-CORRECT OPERATIONAL EXECUTION** — LONG open ASK / close BID; SHORT open BID / close ASK.

---

## 2. LONG execution audit

| Path | OPEN | CLOSE / stop trigger | Verdict |
|------|------|----------------------|---------|
| **Broker invariant** | ASK | BID | Required |
| **Executor v2.20** | `ORDER_TYPE_BUY` @ `SYMBOL_ASK` | Close / trail uses bid-side management in dual PM | **Operational OPEN correct** |
| **Native discovery research script** (`run_native_discovery.py`) | `ent_long = bid_open` | Stop/exit uses ask arrays in places | **Research OPEN optimistic** (BID instead of ASK) |
| **Native live evaluator** | Signal only (no fill) | Metadata only | N/A fills |

**Conclusion:** Live Executor LONG open is broker-correct. **Offline Native LONG qualification metrics are not proven broker-correct** because discovery used `bid_open` entries. → Class **B/C**: preserved, requires independent broker-correct re-verification; **not** auto-invalidated by USDCHF SHORT defect alone.

---

## 3. SHORT execution audit

| Path | OPEN | CLOSE / stop | Verdict |
|------|------|--------------|---------|
| **Broker invariant** | BID | ASK | Required |
| **Executor v2.20** | `ORDER_TYPE_SELL` @ `SYMBOL_BID` | Cover via buy at market (ask) | **Operational OPEN correct** |
| **RSI9 rulebooks** | `entry_timing: next_bar_ask_open` | `exit_side: bid` (USDCHF) | **Research inverted vs broker** |
| **Research script** | `ent_short = ask_open` | Exit management on **bid** OHLC | Matches rulebook; **not broker-correct** |
| **V53.6 rulebook** | `entry: next-bar AskOpen` | `stop_trigger: BidHigh` | **Frozen historical reconstruction** — intentional, separate from operational |
| **live_short_position_manager** | Assumes entry price given | Stop on BidHigh; exit at stop or BidClose | Reconstruction-aligned |

**USDCHF RSI9 independent finding (accepted):** reported PF ~2.55–2.82 → ~0.49–0.51 under broker-correct SHORT fills.

---

## 4–8. Stop / TP / BE / trail / max-bar

| Mechanism | Research SHORT (RSI9 / script) | V53.6 / live_short_position_manager | Executor v2.20 dual PM |
|-----------|--------------------------------|--------------------------------------|-------------------------|
| **Initial stop** | entry + 1.0 ATR (entry = ask in research) | entry + 1.5 ATR | From server SL / ATR mult |
| **Stop trigger SHORT** | Bid high vs stop | BidHigh ≥ stop | Broker SL + PM |
| **Stop trigger LONG** | Ask low vs stop (script) | N/A (short-only baseline) | Broker SL + PM |
| **Take-profit** | None (trail/time) | None | `take_profit=None` |
| **Break-even** | +1R then stop → entry | +1R on BidClose R | +1R then stop → entry (both sides) |
| **Trail** | 0.5 ATR from bid close after BE | 0.75 ATR from BidClose after BE | ATR trail both sides |
| **Max hold** | 72 M5 bars | 72 M5 bars | 72 M5 bars |

**Gap:** Research SHORT stop-on-bid vs broker cover-at-ask is a known optimistic bias for shorts (triggers/fills differ).

---

## 9. V53.6 reconstruction audit

- Direction: SHORT only  
- Documented entry: **next-bar AskOpen** (historical)  
- Stop trigger: **BidHigh**  
- Governance: `production_authorization: false`, `historical_research_only: true`  
- Live V31 evaluator sets `entry_side: AskOpen_next_bar` (documentation of cash-test semantics)

**Determination:**

1. Implementation is consistent with **frozen historical V53.6 reconstruction**.  
2. **Operational** Executor SHORT open is **BID** (broker-correct) — **not** the same as historical AskOpen entry.  
3. Numerical identity between historical reconstruction PF and live broker results is **not** guaranteed; they are different contracts.

**Do not silently replace historical V53.6 with broker-correct fills.** Any operational validation must be labeled separately.

---

## 10. Cash-test audit

Cash / multipair matrices built from the same research `simulate()` path inherit the research fill model:

- SHORT entry ask / exit bid-side management  
- LONG entry bid / mixed exit  

Cash-test numbers from that path are **not** broker-correct operational proofs.

---

## 11. Research evaluator audit (live)

| Evaluator | File | Fills? |
|-----------|------|--------|
| RSI9 SHORT | `backend/app/rulebooks/evaluators/rsi9_short_transfer.py` | No — signal + metadata |
| Native | `backend/app/rulebooks/evaluators/native_discovery.py` | No — signal + metadata |
| V31 SHORT | `backend/app/rulebooks/live_v31_short.py` | No — signal + metadata |

Live path integrity depends on **Executor + risk + stop metadata**, not on research PF numbers.

---

## 12. Affected artifacts (classification)

| Artifact | Class | Notes |
|----------|-------|-------|
| USDCHF RSI9 SHORT rulebook + PF | **C — invalidated** | Marked `INVALIDATED_EXECUTION_MODEL_ERROR` |
| Other RSI9 SHORT forex rulebooks | **C — require rerun** | Same `next_bar_ask_open`; flagged PENDING |
| RSI9 BTC/ETH | **D** | Confirm same simulator before use |
| Offline research scripts (`run_native_discovery` fill model) | **C** for SHORT; **B/C** for LONG | Source of ask/bid inversion |
| Cash tests / multipair matrix from those scripts | **C** | Derived |
| V53.6 historical reconstruction | **A as reconstruction** / **B for operational claim** | Frozen; not operational proof |
| Live short position manager | **A for V53.6 reconstruction** | Matches BidHigh short model |

---

## 13. Unaffected / preserved

| Artifact | Class | Notes |
|----------|-------|-------|
| Architecture / registry / risk engine / withdrawal design | **A** | Preserved |
| Qualification **thresholds** | **A** | Unchanged; execution integrity is prerequisite |
| Executor v2.20 open prices | **A (opens)** | BUY@ASK, SELL@BID |
| Screenshot isolation | **A** | Unchanged |
| production_authorized=false enforcement | **A** | Enforced |

---

## 14. Native LONG status

**Not discarded.**

- 12-pair transfer rulebooks **preserved**  
- **Not** automatically invalidated by USDCHF SHORT defect  
- Discovery script used `ent_long = bid_open` → **optimistic vs ASK**  
- Status: **PRESERVED — requires independent broker-correct LONG verification**  
- `production_authorized = false`

---

## 15. 12-pair Native LONG transfer status

Same as §14. Rulebooks remain in registry for Stage 2 routing tests; **metrics not re-certified** under broker-correct LONG until re-eval.

---

## 16. RSI9 SHORT status

| Pair | Status |
|------|--------|
| **USDCHF** | **INVALIDATED — EXECUTION MODEL ERROR** (JSON updated; artifact kept) |
| Other RSI9 forex | **PENDING execution audit / Class C** — same entry timing |
| Production | **false** |

Do **not** retune USDCHF JSON to pass gates. Corrected research = **new** evaluation.

---

## 17. Required code corrections (future work — not done in this audit)

1. **Broker-correct research simulator** (separate from V53.6 reconstruction):  
   - SHORT open BID, close/stop ASK  
   - LONG open ASK, close/stop BID  
2. Re-run **Class C** SHORT research under that simulator without lowering thresholds.  
3. Re-verify **Native LONG** under LONG open ASK / close BID.  
4. Optional: risk release on position close (Stage 2.5 residual).  
5. Do **not** change frozen V53.6 historical definition.

---

## 18. Tests added

`tests/test_execution_integrity_bidask.py`

- Broker-correct LONG/SHORT entry/exit  
- Stop-side probes  
- Spread / zero-spread controls  
- USDCHF invalidation status  
- RSI9 ask_open documentation  
- V53.6 AskOpen reconstruction documentation  
- Executor SELL@BID / BUY@ASK presence  
- Native not auto-invalidated  
- production_authorized false  

---

## 19. Test results

```text
PYTHONPATH=backend pytest tests/test_execution_integrity_bidask.py -q --noconftest
```

(Results recorded at commit time.)

---

## 20. Commit hash

See git log after push of this audit.

---

## 21. Remaining uncertainties

1. Exact offline script version that produced each published RSI9 PDF (pathology confirmed in rulebook fields + known script).  
2. Full numerical delta V53.6 AskOpen reconstruction vs BID-entry operational replay (not computed in this audit).  
3. Native LONG PF under pure ASK-entry / BID-exit (not re-run here — no discovery).  
4. Intrabar bid/ask path dependency (M1) not modeled — M5 OHLC only.  
5. Open-risk release on close still pending Stage 2.5 follow-up.

---

## Final status

**EXECUTION INTEGRITY AUDIT COMPLETE — HOLD REMAINS**

- No strategy promotion  
- No discovery  
- USDCHF RSI9 SHORT invalidated (evidence preserved)  
- Native LONG preserved pending broker-correct verification  
- V53.6 frozen as historical reconstruction, separated from operational broker execution  
- Automated Bid/Ask invariant tests added  

**Does not claim PASS for research qualification under broker-correct execution** until Class C artifacts are re-evaluated under a corrected simulator.
