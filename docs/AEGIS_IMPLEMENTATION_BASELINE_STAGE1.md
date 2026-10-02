# AEGIS Implementation Baseline — Stage 1

**Date:** 2026-10-02  
**Repo HEAD at audit:** `b1f373a` (and successors on `main`)  
**Purpose:** Authoritative inventory of completed research vs server execution path.  
**Directive:** Do not restart RSI discovery. Use completed research as baseline; verify and complete integration.

---

## 1. What exists and is preserved

### 1.1 Research artifacts (completed — do not re-run without defect)

| Package / path | Content | Status |
|----------------|---------|--------|
| USDCHF discovery JSON | RSI(9)>70 SHORT, val PF~2.55 class | Research baseline |
| `registry/v40/rulebooks_rsi9_short/` | 14 pair rulebooks (12 forex + BTC/ETH) | Registered CSV + JSON |
| `registry/v40/rulebooks_native/` | USDJPY, GER40, UK100, US100, UKOIL, XAGUSD | Registered CSV + JSON |
| `registry/v40/AEGIS_V40_*_REGISTRY.csv` | Instrument + rulebook indexes | Loaded at runtime |
| V31 / V53.6 short lineage | Cash-test SHORT methodology | **Active live evaluator** |

### 1.2 Server components present

| Component | Location | Implementation status | Demonstrated E2E |
|-----------|----------|----------------------|------------------|
| MT5 OHLC Feed EA | `windows-desktop/mq5/` | Present (multi-symbol) | Partially (stream 200s observed) |
| MT5 Executor EA | `windows-desktop/mq5/` | Present (multi-pair, ACK, restart guards) | Partially (demo fills observed historically) |
| OHLC stream API | `ohlc_router` / `ohlc_stream_service` | Present | Yes (HTTP 200 logs) |
| Autonomous OHLC signals | `autonomous_ohlc_signal_service` | Present | Partial |
| Universal Router | `universal_router` + registry | Present | Yes (eligibility gates) |
| Universal Analysis | `universal_analysis_service` | Present | **V31 SHORT path only** |
| Risk / position sizing | `position_sizing_engine`, portfolio risk | Present | Unit tests; live E2E partial |
| Executor pending-batch | API + EA poll | Present | Partial |
| Notifications | NotificationService + mobile inbox | Present | Partial |
| Hybrid Ratchet withdrawal | Separate module, default off | Present | Not production-enabled |
| Mobile monitor / community | Android app | Present | UI exists; not sole trade trigger |
| Admin summary (paid/demo counts) | `/api/admin/summary` | Present | Code complete |

---

## 2. Critical integration gap (Stage 2 work)

**Registry contains RSI9 transfer and native discovery rulebooks, but the live OHLC evaluation path does not execute them.**

Authoritative live path today:

```
MT5 OHLC stream
  → AutonomousOhlcSignalService
  → UniversalAnalysisService._evaluate_research_ohlc
  → evaluate_live_v31_short (V31 / V53.6 SHORT only)
  → gate: baseline_short_only (BUY rejected)
  → Executor pending-batch
```

Evidence in code (`universal_analysis_service.py`):

- Methodology string: `v31_short_baseline`
- Evaluates V31/V53.6 IDs; falls back to V31 GBPUSD-style short logic
- Does **not** load `rulebooks_rsi9_short/*.json` or `rulebooks_native/*.json` evaluators
- V2-OPT path exists but is gated off (`ALLOW_V2OPT_LIVE_SIGNALS`)

Evidence in autonomous gate:

- BUY signals rejected on baseline methodology
- Native discovery winners are mostly **LONG** — incompatible with short-only gate until Stage 2 defines dual-direction policy

### Implication

| Layer | Status |
|-------|--------|
| Builder RSI research | **Complete (baseline)** |
| Pair registry listing | **Complete** |
| RSI9 / native **execution engine** | **Not integrated** |
| Live trades (when any) | Driven by **V31 SHORT**, not RSI9 transfer JSON |

Marking “RSI research done” is correct. Marking “server runs RSI9 strategy” is **not** correct until Stage 2 lands an evaluator and tests.

---

## 3. Pair / rulebook inventory (registry)

### Research-eligible (GOOD / router RESEARCH_ELIGIBLE) — examples

- Forex RSI9 SHORT transfer: AUDUSD, EURCHF, EURGBP, EURJPY, EURUSD, GBPJPY, GBPNZD, GBPUSD, NZDCHF, NZDJPY, USDCAD, USDCHF (+ BTCUSD, ETHUSD crypto transfer)
- Native discovery: USDJPY (long EMA pullback), GER40, UK100, US100, UKOIL, XAGUSD

### Rejected / disabled examples

- USDJPY under RSI9 transfer (failed); later **native** qualified as LONG
- US500, USOIL, XAUUSD — native discovery no qualified rule
- All research rulebooks: `production_authorized = false`

Exact rows: `registry/v40/AEGIS_V40_INSTRUMENT_REGISTRY.csv` and `AEGIS_V40_RULEBOOK_REGISTRY.csv`.

---

## 4. Authoritative execution rules (today)

| Topic | Authoritative rule |
|-------|-------------------|
| Live OHLC signal methodology | **V31 SHORT / V53.6 transfer structural short** |
| Direction on baseline path | **SELL only** |
| RSI9 SHORT research JSON | Registry only — **not live evaluator** |
| Native LONG discovery JSON | Registry only — **not live evaluator** |
| Production live money | **Disabled** (`production_authorized` / env gates) |
| Mobile | Monitor / analysis; must not invent autonomous entries |
| Risk sizing | Server-side stop-based sizing; fail-closed on missing margin data |

---

## 5. Component status board

| Component | Status |
|-----------|--------|
| Builder's RSI research | **Existing baseline — complete** |
| Pair-specific RSI rulebooks (files + CSV) | **Present — verify packaging in Docker image** |
| RSI **server integration** (evaluate JSON → signal) | **Incomplete — Stage 2** |
| MT5 OHLC feed | Implemented — **demo retest required** |
| MT5 executor | Implemented — **demo retest required** |
| Risk engine | Implemented — **controlled tests required** |
| Notifications | Implemented — **workflow test required** |
| Mobile monitoring | Implemented — **acceptance test required** |
| End-to-end demo | **Acceptance testing pending** |
| Production readiness | **Pending acceptance** |

---

## 6. Stage 2 acceptance criteria (next)

Do **not** restart discovery. Implement and test:

1. Loader for `registry/v40/rulebooks_rsi9_short/{PAIR}.json` (and optional native packs).
2. OHLC evaluator matching research: RSI(9), entry/exit, ATR stop, BE, trail, max hold, bid/ask sides as specified.
3. Router selects pair-specific rulebook from registry eligible list.
4. Autonomous path publishes only when evaluator fires; still respect risk, margin, market hours, dedupe.
5. Explicit policy for LONG native rules vs short-only baseline (document; do not silently mix).
6. Automated tests: unit evaluator + integration “CLOSED bar → signal → pending-batch”.
7. Demo checklist unchanged: feed → server → signal → EA → ACK → notification → exit management.

---

## 7. What we will not do

- Restart full RSI discovery without a documented defect in the research artifacts.
- Claim live trading uses RSI9 solely because the registry lists it.
- Treat a green Render deploy or HTTP 200 as strategy correctness.
- Enable production authorization before Stages 3–6 acceptance.

---

## 8. Stage 1 acceptance

**Stage 1 is complete when this document is reviewed and the gap in §2 is acknowledged as the Stage 2 work item.**

No research re-run is required for Stage 1.
