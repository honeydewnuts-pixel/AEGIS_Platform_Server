# AEGIS V3 Synchronized Screenshot + MT5 M1 OHLC

## Purpose
At capture time, AEGIS Mobile records `captured_at_ms` and the configured MT5
chart symbol. The server sends a read-only job to the already-connected Windows
MT5 worker. The worker reads tick history from the MetaTrader 5 terminal and
reconstructs the M1 OHLC through the exact capture timestamp.

## Data path
```text
Android screenshot
      | captured_at_ms + symbol
      v
AEGIS /aegis/analyze
      | Redis job
      v
Existing Windows MT5 worker
      | MetaTrader5 Python terminal API
      v
MT5 tick history -> M1 OHLC at capture timestamp
      |
      +--> frame_YYYYMMDD_HHMMSS_mmm_SYMBOL.png
      +--> frame_YYYYMMDD_HHMMSS_mmm_SYMBOL.json
```

## No separate broker market-data API
The feature does **not** call a broker REST/HTTP market-data API. It uses the
MetaTrader 5 terminal connection already owned by the AEGIS Windows worker.
The MT5 terminal itself must of course be connected to the demo broker server
to receive market data.

## Exactness
The snapshot is reconstructed from MT5 ticks whose timestamps fall between the
start of the M1 minute and the screenshot timestamp. Therefore the OHLC does not
include price movement that occurred after the screenshot. If MT5 has no tick
history for the requested instant, the snapshot is rejected rather than guessed.

## Rule-engine safety
The existing V3 pixel-coordinate `price_close` used by the visual rule engine is
not overwritten with a raw price number because pixel Y and market price are
different coordinate systems. The authoritative OHLC is stored under
`market_ohlc` and returned with the analysis. This prevents a silent unit mismatch.
Any future V3 candle rule can consume `market_ohlc` directly.

## Required mobile setting
Set **MT5 Chart Symbol** in the AEGIS Mobile Settings screen (for example,
`EURUSD`, `XAUUSD`, or the broker's exact symbol name). The symbol is sent with
every capture and is preserved for offline replay.
