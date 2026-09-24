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
