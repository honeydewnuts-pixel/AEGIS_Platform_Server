# AEGIS Stage 6 — Production Readiness & Controlled Promotion Gate

## Governance (mandatory)

```
production_authorized = false
```

| Methodology | Status |
|-------------|--------|
| V53.6 | FROZEN / unchanged |
| RSI9 | NOT PROMOTED |
| Native | NOT PROMOTED |
| Generation 3 | CLOSED / 0 qualified |

**ENGINEERING READY ≠ PRODUCTION AUTHORIZED**

---

## Baseline

| Item | Value |
|------|--------|
| Starting HEAD | `1d70ea0a120e8715240ac57af7bcdb3fc309b801` (Stage 5 complete) |

---

## What Stage 6 adds

1. **Durable emergency stop** (`aegis_operational_control`) — survives API restart; blocks **new** orders only; open positions continue management; audited.
2. **Configuration fail-closed** — `PRODUCTION_AUTHORIZED` defaults to `false` in settings.
3. **Execution gates** — enqueue + pending poll + controlled-demo publish respect emergency stop.
4. **Governance regression tests** — research cannot execute; production stays false.
5. **Documentation** of observability authority model and promotion gate.

### State authority

| Fact | Authority |
|------|-----------|
| Broker position / fill | Broker / MT5 |
| AEGIS risk / lifecycle | Durable lifecycle + portfolio risk (DB) |
| Pending execution | Durable execution queue + memory cache |
| Emergency stop | `aegis_operational_control` |
| Notifications | **Not** authoritative |

### Correlation

`signal_id` links: queue row ↔ lifecycle ↔ ACK ↔ broker ticket (when present).

### Emergency stop API

- `GET /api/admin/operational/status`
- `POST /api/admin/operational/emergency-stop` `{ "enabled": true|false }` (admin)

### Controlled Demo

BUY and SELL remain allowed for `controlled_demo_test` when not emergency-stopped.  
Controlled Demo does **not** enable production.

### Migration

`0021_aegis_operational_control` — additive.

---

## Human VPS acceptance (mandatory, separate)

```
Updated Executor → MetaEditor compile → controlled-demo signal
→ MT5 Demo fill → ACK → manual close → reconciliation → risk release
```

**LIVE HUMAN DEMO: PENDING** until operator evidence exists.

---

## Explicit statement

```
ENGINEERING READINESS: PASS (when CI green)
PRODUCTION AUTHORIZATION: NOT GRANTED
HUMAN VPS ACCEPTANCE: PENDING
production_authorized = false
```
