# V48 — Independent MT5 OHLC stream

## Channels

| Channel | Role |
|---------|------|
| Android / desktop capture | Screenshot + symbol + timestamps (visual/context) |
| MT5 EA `AEGIS_OHLC_Feed.mq5` | Authoritative OHLC history via `CopyRates` → `POST /api/mt5/ohlc/stream` |

Screenshot is **never** the numerical OHLC source.

## Setup

1. Compile `windows-desktop/mq5/AEGIS_OHLC_Feed.mq5` in MetaEditor.
2. Tools → Options → Expert Advisors → allow `https://your-aegis-api...`
3. Inputs: Server URL, API key, Account ID, Bars=200.
4. Attach to GBPUSD M5 (or your pair).

## Server

- Stores last ≤500 bars per account|symbol|timeframe.
- `/aegis/analyze` prefers fresh stream OHLC over one-shot worker jobs.
- `feature_engine` computes RSI/SMA/ATR from history when bars ≥ 5.

## Live decision path

MT5 CopyRates → stream → features → V40 rulebook path → confidence → HOLD/EXECUTE candidate  
(production_authorized remains false until explicitly enabled)
