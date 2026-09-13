# V47.1 — Market Observation Package + low-power M5 cycle

## Package (multipart `/aegis/analyze`)

| Field | Role |
|-------|------|
| image | Chart screenshot (visual evidence) |
| symbol / instrument | Pair for V40 router |
| timeframe | Default M5 |
| candle_ts_ms | Floored M5 boundary |
| device_ts_ms | Device clock |
| sequence | Monotonic observation id |
| ohlc_* / quote_* | Optional numerical layer from client |
| (server) | OHLC from MT5 worker when connected |

## Mobile

- Schedules captures near **next M5 boundary** (not a fixed 3–5s spam loop).
- Always sends Settings chart symbol for routing.
- Analysis panel shows **Last HTTP code**.
- Does not embed trading intelligence; server decides.

## Desktop (Win/Mac)

Same protocol: region screenshot + symbol + M5 candle_ts + sequence.
Prefer worker OHLC; screenshot is evidence only.
