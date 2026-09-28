# Signal → sizing → execution (fail-closed)

## Paths

1. **Autonomous OHLC** (`AutonomousOhlcSignalService`)  
   CLOSED bar → rule → entry/stop → `size_order(entry, stop, side, atr)` → publish only if volume > 0.

2. **Brain / screenshot publish** (`brain_router`, only if `SCREENSHOT_PUBLISHES_TO_EXECUTOR`)  
   Requires entry + stop (+ optional ATR for stop construction) → `size_order(...)` → no publish without valid volume.

3. **AutonomousDemoExecutionService**  
   No legacy `calculate_lot_size` fallback. Sizing failure → `executed: false`.

## MT5 Feed v2.04

On each cycle after equity:

- `POST /api/portfolio/account-profile` (`InpAccountType`, `InpBrokerId`)
- `POST /api/portfolio/instrument-spec` (contract size, volume min/max/step, tick size/value, margin)
- Legacy `POST /api/portfolio/min-notional` retained

Keep `InpAccountType` / `InpBrokerId` consistent with instrument-spec rows.
