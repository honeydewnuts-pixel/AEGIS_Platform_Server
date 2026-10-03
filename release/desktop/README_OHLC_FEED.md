# AEGIS_OHLC_Feed.mq5 — v2.05

Posts closed M5 bars (+ equity / free margin / instrument specs) to `POST /api/mt5/ohlc/stream`.

## Required for multi-pair autonomous

- `InpMode = FEED_MODE_MULTI_SYMBOL`
- `InpSymbolsList` = your pairs, e.g.  
  `AUDUSD,EURCHF,EURGBP,EURJPY,EURUSD,GBPJPY,GBPNZD,GBPUSD,NZDCHF,NZDJPY,USDCAD,USDCHF`

## Compile

MetaEditor → compile → `MQL5/Experts/`. Allow WebRequest to API host.

`AccountId` must match Executor and the API key account.
