# AEGIS_Executor.mq5 — v2.20

## Stage 2.5 execution integrity

- **Methodology-aware direction:** RSI9 / V31 / V53 SHORT-only; Native LONG may BUY.
- **No unauthorized flip:** opposite-side signal rejected while AEGIS position is open.
- **Dual position manager:** BUY and SELL get +1R BE, ATR trailing, 72-bar max hold.
- `BaselineShortOnly` remains as legacy default only when methodology is unknown.

## Compile

1. Open `AEGIS_Executor.mq5` in MetaEditor.
2. Compile → deploy `.ex5` to `MQL5/Experts/`.
3. Allow WebRequest to your AEGIS API host in Tools → Options → Expert Advisors.
4. Inputs: `UseServerSignals=true`, `EnablePositionManager=true`, matching `AccountId` with Feed.

## Companion

- Feed: `AEGIS_OHLC_Feed.mq5` **v2.05** (MultiSymbol for 12 pairs).
