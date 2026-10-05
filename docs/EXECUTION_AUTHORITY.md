# AEGIS Execution Authority

## Fail-closed
- Registry unavailable → reject
- production_authorized must be explicit true for autonomous queue
- Research (RSI9, Native, V53.6 research candidates) remain unauthorized

## Lifecycle (durable + memory mirror)
States: SIGNAL_QUEUED → ORDER_SENT → BROKER_CONFIRMED_OPEN → POSITION_OPEN → RISK_RELEASED

- Open risk only when position_ticket > 0 and risk_usd known (durable row)
- Close: server risk only; client amount cannot invent release
- Disappearance detection (EA): SL/BE/trail/manual → POST /position-closed
- Restart: EA reconcile-positions; durable DB rows vs broker tickets
- Idempotent: account_id+signal_id / account_id+position_ticket

## V53.6
REPRODUCTION VERIFIED against stored operational ledger — not ORIGINAL RESEARCH INDEPENDENTLY VERIFIED; not production.

## Portfolio open_risk_usd
- `record_open_risk` / `release_open_risk` use `SELECT … FOR UPDATE` on the subscription row.
- Concurrent releases both apply (no lost update).
- Lifecycle row lock (Stage 3.1) remains the authority for *which* risk amount is released; portfolio aggregate is updated under its own lock.
