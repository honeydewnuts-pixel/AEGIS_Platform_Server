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
