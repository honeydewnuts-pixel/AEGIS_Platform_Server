# Stage 2B — Native LONG transfer integration (2026-10-03)

Integrate 12 research-qualified native LONG transfer rulebooks (USDJPY long_ema_pullback frozen params).
Preserve V53.6 SHORT baseline and RSI9 SHORT transfer. production_authorized=false.

## Research
- LONG transfer: 12/12 QUALIFIED
- NZDUSD RSI9 SHORT and native LONG: NOT_QUALIFIED (val PF below 1.6) — not registered

## Server
1. rulebooks_native/{PAIR}.json for 12 forex LONG books
2. Dual eval: RSI9 + native; actionable wins; RSI9 HOLD does not block native LONG
3. Gates: RSI9 SHORT-only; native BUY/SELL; V53.6 SHORT-only; no auto-flip
