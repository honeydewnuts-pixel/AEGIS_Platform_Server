# Stage 2.5 — Execution Integrity Remediation

**Date:** 2026-10-03

## Problems addressed

1. **Executor global BUY reject** (`BaselineShortOnly`) blocked Native LONG.
2. **Position manager was SHORT-only** — no BE / trail / 72-bar for LONG.
3. **Executor unauthorized flip** conflicted with server `no_auto_flip`.
4. **`record_open_risk` never called** on the live execution path.

## Changes

### Executor `AEGIS_Executor.mq5` → **v2.20**

| Change | Detail |
|--------|--------|
| Methodology-aware direction | BUY rejected only for RSI9 / V31 / V53 SHORT methods; Native BUY allowed |
| No auto-flip | Opposite-side signal while AEGIS position open → reject (`no_auto_flip`), do not close/reverse |
| Dual position manager | `ManageAegisPositions()` handles BUY and SELL: +1R BE, ATR trail, 72-bar hold |
| Registration | `RegisterManagedPosition(..., side, ...)` for both directions |

### Server

| Change | Detail |
|--------|--------|
| `publish(..., risk_usd_at_open=)` | Stores sized monetary risk on pending signal |
| Autonomous publish | Passes `estimated_monetary_risk` / `risk_allocation_usd` |
| `/api/executor/ack` | On successful non-idempotent ACK → `PortfolioRiskService.record_open_risk(+risk)` |

## Remaining (not in this checkpoint)

- **Risk release on close** — open risk is incremented on ACK but not yet decremented on position close. Prefer MT5 → server position sync or close ACK. Until then, open risk may accumulate until restart/reset.
- **Compile in MetaEditor** — required for production EA binary.
- **One-pair MT5 demo** — next acceptance after compile.

## Production authorization

Unchanged: RSI9 / Native remain `production_authorized=false`.
