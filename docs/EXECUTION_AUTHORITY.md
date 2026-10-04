# AEGIS Execution Authority

## Rules (fail-closed)

1. `production_authorized` must be explicitly true or the autonomous path will not queue Executor work.
2. Registry unavailable → reject symbol authorization (`registry_unavailable_fail_closed`). Never fail-open.
3. Research methodologies (RSI9, Native, V31/V53 research candidates) remain `production_authorized=false`.
4. Signal publication is not a position open.

## Lifecycle

SIGNAL_GENERATED → SIGNAL_QUEUED → ORDER_SENT → BROKER_CONFIRMED_OPEN
→ POSITION_OPEN → POSITION_CLOSED → BROKER_CONFIRMED_CLOSE → RISK_RELEASED

APIs:
- POST /api/executor/ack
- POST /api/executor/position-closed
- POST /api/executor/reconcile-positions

## Position side authority

In-memory side is a cache. Authoritative side after restart comes from broker positions via reconcile.

## V53.6

Historical reconstruction (AskOpen SHORT, optional 0.085R) is separate from broker-correct operational path. Never mixed.
