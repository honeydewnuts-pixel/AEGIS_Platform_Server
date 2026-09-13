# V47.3 — OHLC synchronization + HOLD reasons

## Why WAITING_FOR_OHLC persists on mobile-only installs

Numerical OHLC is read from the **account MT5 worker** (Windows/desktop linked via MT5 LINK),
not from the Android screenshot. The phone supplies screenshot + symbol + timestamps.

When worker is running, server enqueues `get_m1_ohlc_at`. If no worker:
`hold_reason=WAITING_FOR_OHLC` with detail that MT5 LINK is required.

## HOLD reason taxonomy

- WAITING_FOR_OHLC
- WAITING_FOR_CAPTURE
- NO_ELIGIBLE_RULEBOOK
- NO_QUALIFIED_SIGNAL
- CONFIDENCE_BELOW_THRESHOLD
- RISK_GATE

Neural discovery is not required for live path.
