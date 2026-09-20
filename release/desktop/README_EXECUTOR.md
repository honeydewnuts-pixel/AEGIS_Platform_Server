# AEGIS_Executor.mq5 v2.12 (production)

## Production hardening

| Item | Behaviour |
|------|-----------|
| Broker symbol | ResolveBrokerSymbol: exact → suffixes → Market Watch → terminal |
| Handled timing | Only after success / permanent fail |
| Spread retries | Separate `MaxRetriesSpread` (default 12) |
| Broker retries | Separate `MaxRetriesBroker` (default 5) |
| Position ticket | `FindPositionTicket` by magic+symbol after fill |
| ACK | HTTP 2xx required; queue + retry if POST fails |
| Server | Idempotent ACK by `signal_id` — no double execution if ACK lost |
| Fill modes | From `SYMBOL_TRADE_EXEMODE` + `SYMBOL_FILLING_MODE` |

## Demo / live

Same binary. Server gates (Good pairs, production_authorized, subscription) control live risk.
