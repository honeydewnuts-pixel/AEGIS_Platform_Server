# Broker-configurable standard / micro accounts

## Concepts

| Setting | Meaning |
|---------|---------|
| `account_type` | `standard` \| `micro` \| `custom` — **account profile**, not risk tolerance |
| `account_currency` | Equity / P&amp;L currency |
| `broker_instrument_specs` | Contract size, volume min/max/step, tick size/value, margin |

Risk tolerance remains a separate client preference used by `assess_per_trade_risk`.

## API

```http
POST /api/portfolio/account-profile
{ "account_id": "ACC-…", "account_type": "micro", "account_currency": "USD", "broker_id": "BrokerX" }

POST /api/portfolio/instrument-spec
{
  "account_id": "ACC-…",
  "symbol": "USDCHF",
  "account_type": "micro",
  "broker_id": "BrokerX",
  "contract_size": 1000,
  "volume_min": 0.01,
  "volume_max": 500,
  "volume_step": 0.01,
  "tick_size": 0.00001,
  "base_currency": "USD",
  "quote_currency": "CHF",
  "source": "mt5"
}

POST /api/portfolio/size
{
  "account_id": "ACC-…",
  "symbol": "USDCHF",
  "side": "SELL",
  "entry_price": 0.9000,
  "stop_loss": 0.9015
}
```

## MT5 path

1. Feed/EA reads `SymbolInfoInteger` / `SymbolInfoDouble` (volume min/step/max, trade contract size, tick size/value).
2. POST `/api/portfolio/instrument-spec` (and equity via `/api/portfolio/equity`).
3. Autonomous OHLC path calls `size_order` with entry/stop; missing/invalid volume → no publish.

## Migration

Alembic `0016_account_broker_instrument_specs`.
