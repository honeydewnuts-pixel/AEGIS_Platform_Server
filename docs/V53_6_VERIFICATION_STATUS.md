# V53.6 Independent Verification Status

## Historical reconstruction
- Simulator: `simulate_short` / `simulate_short_legacy` in `evaluators/common.py`
- Convention: next-bar AskOpen, BidHigh stop, BidClose time, BE +1R, trail 0.75 ATR, 72 bars
- Legacy cost: 0.085R when `cost_mode=legacy_fixed_r`
- Status: IMPLEMENTATION PRESENT — locked-event stream reproduction NOT VERIFIED in this checkpoint

## Broker-correct operational (separate)
- `simulate_short_broker_correct` / `simulate_long_broker_correct`
- No universal 0.085R
- Status: IMPLEMENTATION PRESENT — structural probe only; not a substitute for historical V53.6

## Cash matrix (7×7×3 × horizons)
- Status: NOT VERIFIED (not regenerated in this checkpoint)
- Existing USDCHF cash artifacts: classified only; generator completeness unresolved

## Cash compounding
- Required model when regenerated: per-trade equity update; risk = current_equity × risk%
- Rejected trades must not change equity
