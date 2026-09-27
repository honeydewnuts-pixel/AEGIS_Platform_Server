# Generalized Position Sizing Engine

## Formula

```
Risk Budget = Equity × Risk%  (or remaining / free slots in MultiSymbol)
Loss per lot = stop_distance × contract_size   (converted to account currency)
Position size = floor(Risk Budget / Loss per lot / volume_step) × volume_step
```

Margin is checked **after** volume is chosen. Margin is never used as a substitute for stop risk.

## Integration

- `app.services.position_sizing_engine` — pure calculation
- `PortfolioRiskService.size_order(..., entry_price=, stop_loss=, side=)` — account state + engine
- `AutonomousOhlcSignalService` — computes 1.5×ATR stop, then sizes before publish

## Limitations

- Default `InstrumentSpec` templates are used until broker Feed overwrites contract data.
- Full USDCHF 5y operational cash ledgers require Bid/Ask dataset not shipped in repo.
- Historical V31/V35 R-metrics remain in R-space (`simulate_short`); sizing engine is for cash volume.
