# AEGIS V42 — Execution, Risk & Safety Integration Specification
Version: V42.0
Date: 2026-09-09
Status: ENGINEERING COMPLETE — PAPER-ONLY / PRODUCTION CLOSED

## 1. Objective
V42 establishes a deterministic safety boundary between AEGIS signal/rulebook intelligence and broker execution. The boundary is fail-closed and broker-independent.

## 2. Required execution states
`IDLE -> SIGNAL_ACCEPTED -> ORDER_QUEUED -> FILLED -> MANAGING -> EXIT_REQUESTED -> CLOSED -> IDLE`.
Rejected and halted paths are explicit. Illegal state skips raise an error.

## 3. Pre-order gates
Every order intent must pass:
- instrument/timeframe identity match
- qualified rulebook eligibility
- valid Bid/Ask relationship
- positive ATR
- spread/ATR ceiling
- fresh completed-bar timestamp
- valid direction and stop side
- minimum 1.5 ATR initial stop distance
- one-position-per-symbol and total-position limits
- known execution mode
- live authorization gates when LIVE is requested

## 4. Frozen risk controls
The V39/V41 execution model remains frozen:
- initial stop = 1.5 ATR
- break-even at +1R
- trailing distance = 0.75 ATR after BE
- maximum duration = 72 bars
- one open position at a time
- no invented spread

V42 does not retune these parameters.

## 5. Data safety
A stale, future-dated, malformed, or missing-side market snapshot is rejected. Bid/Ask side semantics remain instrument-appropriate.

## 6. Kill switch
A kill switch has priority over normal eligibility and returns `KILL_SWITCH`. Reset is explicit; no automatic recovery is permitted.

## 7. Idempotency
Client order IDs are treated as idempotency keys. Duplicate IDs are rejected to prevent repeated submission after retries/timeouts.

## 8. Auditability
Operational events are represented by an append-only hash-linked audit ledger. Chain verification detects mutation or ordering breaks.

## 9. Paper/live separation
Paper mode can be allowed when all research/risk/data gates pass. LIVE mode additionally requires both `live_enabled=true` and `production_authorized=true`. Default values are false.

## 10. Relationship to V40/V41
V40 remains the authority for rulebook eligibility and fail-closed routing. V41 remains the forward/paper protocol. V42 supplies the execution boundary used by those stages; it does not convert research qualification into production authorization.

## 11. Non-goals
- no live broker activation
- no parameter optimization
- no forward-performance claims
- no modification of legacy RULEBOOK_V3
- no substitution of legacy Neural V3 for future V43 lineage
