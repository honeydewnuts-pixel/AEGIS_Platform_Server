# Experiment Registry — Data-Driven Pattern Discovery 20261022

## Horizon registration (before outcome inspection)
- Horizons: 3, 6, 12, 24, 48 M5 bars
- Labels: forward signed return close[t+h]/close[t]
- Entry research reference: completed-bar close as decision; tradeability requires next-bar open (documented limitation)

## Pattern catalogue (22 registered)
See scripts/discover.py ALL_PATTERNS:
long_lower_wick, long_upper_wick, bull_engulf, bear_engulf, inside_bar, outside_bar,
close_near_high, close_near_low, range_compression, range_expansion, consec_bull_3, consec_bear_3,
break_20hi, break_20lo, london_open_hour, ny_open_hour, asian_hour,
compress_then_expand_proxy, bull_engulf_after_compression, bear_engulf_after_compression,
long_lower_wick_at_20lo, long_upper_wick_at_20hi

## Methods run
1. Registered binary pattern enumeration
2. Conditional forward-return analysis
3. MFE/MAE on top-3 |val_mean| patterns per instrument (validation window)
4. Cost materiality: mean MFE >= 3× assumed RT cost

## Methods not run
Unrestricted clustering, deep decision trees, sparse regression search, full LOO transfer

## Search space
22 × 5 × 24 = 2640 evaluations. Multiple-testing risk disclosed.

## Candidate freeze for rulebook conversion
SHORTLIST_SIZE = 0
Reason: zero patterns met |val_mean|>10bps & hit>0.55 & val_n>200; MFE/cost gate pending confirmation in mfe_mae_cost.csv
