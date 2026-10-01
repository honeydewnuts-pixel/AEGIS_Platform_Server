# AEGIS Hybrid Ratchet 70/30 Withdrawal Management

**Status:** Implemented; **disabled by default** (`WITHDRAWAL_MODULE_ENABLED=false`).

## Purpose

Separate financial module for profit withdrawal accounting. Does **not** modify V53.6 entry/exit or position sizing.

## Rules

1. **Compound** until equity ≥ 2 × start equity.
2. **Arm:** CAP = 2 × start.
3. **Allocate** when equity > CAP after realized net profit: 70% eligible withdrawal, 30% increases CAP.
4. **CAP never decreases** on trading losses.
5. **Pause** eligibility if equity < CAP × 0.80; resume when equity ≥ CAP.
6. **Idempotent** on `trade_id`.
7. **Withdrawals ≠ trading losses** — reported separately.
8. Actual bank/broker transfer is **not** claimed on request record alone.

## API

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/withdrawal/status` | Module flag |
| POST | `/api/withdrawal/configure` | start_equity, mode, risk % |
| GET | `/api/withdrawal/dashboard/{account_id}` | CAP, eligible, DD |
| POST | `/api/withdrawal/realized-trade` | Closed trade PnL |
| POST | `/api/withdrawal/request` | Request withdrawal |
| GET | `/api/withdrawal/history/{account_id}` | Ledger |

## Enable (after acceptance)

```
WITHDRAWAL_MODULE_ENABLED=true
```

## Tests

```
pytest tests/test_hybrid_ratchet.py -v
```


## Lean CAP v2 (Zero Dead Money)

After arming, CAP grows via 30% retain until it hits a **lean ceiling** derived from the account risk label:

| Risk label | Reference ceiling @ $1,000 start | Multiple of start equity |
|------------|----------------------------------|--------------------------|
| 0.5% | $83,286 | ×83.286 |
| 1.0% | $783,300 | ×783.3 |

**Per-account ceiling** = `start_equity × multiple(risk)`.  
Example: $500 @ 0.5% → $41,643 · $2,000 @ 1.0% → $1,566,600.

When tentative CAP would exceed the ceiling:

1. `OVERFLOW = CAP - LEAN_CAP_CEILING`
2. Overflow is added to **eligible** balance (DEAD FREED — cash available to withdraw, not left as idle broker CAP)
3. `CAP = LEAN_CAP_CEILING` permanently for further growth

While lean-locked, 100% of new excess above CAP goes to eligible. CAP does not fall on losses. Withdrawals remain separate from trading PnL.
