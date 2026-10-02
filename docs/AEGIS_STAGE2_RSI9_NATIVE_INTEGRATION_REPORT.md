# AEGIS Stage 2 — RSI9 Transfer + Native Discovery Integration Report

**Date:** 2026-10-02  
**Status:** Implemented and tested (research-only; `production_authorized=false`)  
**Directive:** Do not restart discovery. Preserve V53.6 short-only as a separate path.

---

## 1. What was implemented

| Component | Change |
|-----------|--------|
| `backend/app/rulebooks/evaluators/rsi9_short_transfer.py` | Live RSI9 SHORT evaluator (loads `registry/v40/rulebooks_rsi9_short/*.json`) |
| `backend/app/rulebooks/evaluators/native_discovery.py` | Live native LONG/SHORT evaluator (loads `registry/v40/rulebooks_native/*.json`) |
| `backend/app/services/universal_analysis_service.py` | `_evaluate_research_ohlc` priority: RSI9 → native → V31/V53.6 → V2-OPT |
| `backend/app/services/autonomous_ohlc_signal_service.py` | Direction policy by methodology (RSI9 short-only; native dual-direction; V31 short-only) |
| `backend/app/api/brain_router.py` | Analysis notifications marked `analysis_only` / not executor-bound |
| `backend/app/services/notification_service.py` | `emit_signal(..., analysis_only=, executor_published=)` labels analysis alerts |
| `backend/app/api/admin_router.py` | Demo count includes `ACC-*`, `DEMO-*`, and active+unknown plan |
| `tests/test_stage2_rsi9_native_evaluators.py` | 15 acceptance tests (all passed) |

Strategies remain **separate**: each signal carries `methodology` + `strategy_id`. Configurations do not override each other.

---

## 2. Direction / execution policy

| Methodology | Allowed sides | Notes |
|-------------|---------------|-------|
| `v31_short_baseline` / V53.6 | SELL only | Unchanged cash-test baseline |
| `rsi9_transfer` | SELL only | Research design |
| `native_discovery` | BUY or SELL | Per pair rulebook entry.side |
| Other experimental | BUY/SELL | Confidence threshold + no auto-flip |

All research rulebooks remain `production_authorized=false`.

---

## 3. Acceptance tests executed

```
15 passed in 0.57s
```

Coverage:

1. Each approved RSI9 rulebook loads (forex + BTCUSD/ETHUSD)
2. Native rulebooks load (USDJPY, GER40, UK100, US100, UKOIL, XAGUSD)
3. Missing rulebooks fail closed → HOLD
4. Insufficient bars → HOLD
5. RSI9 overbought synthetic → SELL; never BUY
6. Native evaluates without crash
7. Universal path prefers RSI9 over V31 when RSI9 rulebook exists
8. USDJPY routes to native_discovery
9. Gate: V31 rejects BUY; RSI9 allows SELL / rejects BUY; native allows both; dedupe same-direction

---

## 4. Screenshot / ops findings (AEGIS_Screenshots)

### Phantom SELL (NZDJPY, conf 100%)

- **Cause:** Mobile settings pair select → `/aegis/analyze` (screenshot/analysis path) evaluated V31 SHORT on NZDJPY and emitted inbox notification **SELL NZDJPY**.
- **Executor:** `SCREENSHOT_PUBLISHES_TO_EXECUTOR` is false → `executor_published=False`. Execution Monitor correctly showed NO_SIGNAL / queue EMPTY / no order ACK.
- **Why no MT5 trade:** Analysis path never publishes to the Executor pending-batch. Live orders only come from OHLC closed-bar → `AutonomousOhlcSignalService` → Executor.
- **Fix applied:** Notifications from analysis path are now titled `[Analysis only]` and type `SIGNAL_ANALYSIS_ONLY`, with explicit text that the signal was not sent to MT5.

### Ops demo count = 0

- Fleet showed: Subs total 6 · paid active 0 · demo 0 · by plan unknown 6.
- **Cause:** Subscription rows had `plan="unknown"` (not `"demo"`) and account IDs like `ACC-*` (not `DEMO-*`), so the old classifier missed them.
- **Fix applied:** Demo classifier now includes `ACC-*` prefix and active/trialing with unknown plan. Summary still exposes `demo_accounts` / `paid_accounts` lists for verification of account IDs.

---

## 5. Remaining limitations

- Production authorization remains false for all RSI9/native rulebooks; deploy is research/demo only.
- BTCUSD/ETHUSD RSI9 JSON packs omit structured `entry` block; evaluator uses defaults (RSI9>70 SHORT).
- End-to-end demo (OHLC → Executor ACK on Deriv) is the next milestone after this commit is deployed.
- Admin UI may still need a hard refresh to show updated demo counts after server deploy.

---

## 6. Files changed (this stage)

- `backend/app/rulebooks/evaluators/rsi9_short_transfer.py` (new)
- `backend/app/rulebooks/evaluators/native_discovery.py` (new)
- `backend/app/services/universal_analysis_service.py`
- `backend/app/services/autonomous_ohlc_signal_service.py`
- `backend/app/api/brain_router.py`
- `backend/app/services/notification_service.py`
- `backend/app/api/admin_router.py`
- `tests/test_stage2_rsi9_native_evaluators.py` (new)
- `docs/AEGIS_STAGE2_RSI9_NATIVE_INTEGRATION_REPORT.md` (this file)
