# AEGIS Autonomous Per-Trade Risk Assessment

## Separation of concerns

| Layer | Owner | Meaning |
|-------|--------|---------|
| **A. Client risk tolerance** | Client | Overall risk preference (e.g. 10%, 25%). **Not** per-trade size. |
| **B. Per-trade risk %** | AEGIS | Calculated each trade via `assess_per_trade_risk`. |
| **C. Portfolio / drawdown** | AEGIS | Halts and remaining tolerance budget independent of B. |

## Documented rules (R0–R8)

See `backend/app/services/risk_assessment.py` module docstring.

Summary:

1. **R1** Base trade risk = `client_tolerance / 10` (tolerance is an envelope).
2. **R2** Cap at platform max 2% of equity per trade.
3. **R3** Scale by free MultiSymbol slots.
4. **R4** Scale by open-risk utilization of the tolerance budget.
5. **R5** Scale / block on drawdown vs peak relative to tolerance budget.
6. **R6** Scale / block when stop distance is wide vs ATR14.
7. **R7** Reject if resulting % &lt; 0.05% platform floor.
8. **R8** Never exceed client tolerance.

Then: `volume = (equity × assessed_risk%) / loss_per_lot_at_stop` (round down).

## Not client settings

Research scenarios 0.05%, 0.1%, 0.25%, 0.5%, 1%, 2.5%, 5% are for **offline cash tests only**. They are not exposed as required mobile settings.

## Related code

- `risk_assessment.assess_per_trade_risk`
- `PortfolioRiskService.size_order` → assessment → `size_by_stop_risk`
- `AutonomousOhlcSignalService` passes entry, stop, side, atr14
