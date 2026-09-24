# AEGIS Portfolio Risk (equity × tolerance)

## Client settings

| Setting | Values |
|---------|--------|
| Account equity (USD) | Reported by client or MT5 |
| Risk tolerance | 5, 10, 15, 20, 25, 30, 35, 40, 45 % of equity |
| Trading mode | `multi_symbol` or `chart_only` |

## Behaviour

- **Risk budget** = equity × tolerance%.
- **MultiSymbol**: client does **not** pick pairs. AEGIS takes live signals and opens up to `min(24, floor(budget / min_notional))` concurrent pairs.
- **Min notional / min lot** per symbol: defaults or `POST /api/portfolio/min-notional` from the EA/broker.
- **Lot size**: scaled from remaining budget, hard-capped by plan `max_lot`.
- **Halt**: if drawdown from peak equity ≥ risk budget, trading stops until equity is increased or tolerance is changed.

## API

- `GET /api/portfolio/status?account_id=`
- `POST /api/portfolio/equity` `{account_id, equity_usd}`
- `POST /api/portfolio/risk-tolerance` `{account_id, risk_tolerance_pct}`
- `POST /api/portfolio/trading-mode` `{account_id, trading_mode}`
- `GET /api/portfolio/size?account_id=&symbol=`


## Mobile Settings (v2.4.1+)

- **Account equity (USD)** — saved locally and POSTed to `/api/portfolio/equity`
- **Max risk tolerance %** — 5–45% spinner → `/api/portfolio/risk-tolerance`
- **Trading mode** — MultiSymbol or Chart only → `/api/portfolio/trading-mode`
- Status line shows risk budget, max pairs, halt state after Save

## MT5 OHLC Feed v2.03+

Each timer cycle after OHLC posts:

1. `POST /api/portfolio/equity` with `AccountInfoDouble(ACCOUNT_EQUITY)`
2. `POST /api/portfolio/min-notional` per symbol (min lot + margin/notional estimate)

Allow WebRequest URL for your AEGIS host in MT5 Expert Advisors options.
