# Preregistration — P7 Price-Action Extension
**Date:** 2026-10-22  
**Branch:** research/p7-price-action-extension-20261022  
**production_authorized=false · execution_authorized=false**

## Hypotheses (frozen before outcome inspection)

### P7-L1 (Track A — H1 XAUUSD)
Conditions on completed H1 features (exact original thresholds):
- relative_range <= 0.5401154458522797
- upper_wick > 0.048643046990036964
- overlap > 0.6506349742412567
Source: long_tree leaf value ≈ +0.05877R (SOURCE_REPORTED model prediction, not realized expectancy).

### P7-L2 (Track A — H1 XAUUSD)
- relative_range > 0.5401154458522797
- lower_wick <= 0.07916074246168137
- overlap <= 0.21034089475870132
Source: long_tree leaf value ≈ +0.02786R; admitted under TH025 0.025R threshold.

### Short-side
SOURCE_REPORTED: max short-tree leaf ≈ +0.01499R < 0.025R. No short hypothesis registered in this phase.

### Track B
No M5 threshold transplant registered. M5 analogue remains UNRESOLVED pending principled mapping.

## Feature formulas (from P7_Gold_Cash_Replay_Engine.py — SOURCE_VERIFIED)
- body = (close-open)/range; range=0 → NaN
- upper_wick = (high-max(open,close))/range
- lower_wick = (min(open,close)-low)/range
- close_location = (close-low)/range
- relative_range = range / rolling_median(range, 20)
- move{k} = (close - close.shift(k)) / rolling_median(range, 20) for k in 3,6,12
- overlap = intersection(curr,prev ranges) / union; denom 0 → NaN
- inside = (high<=prev_high) & (low>=prev_low)  [equality counts as inside]
- outside = (high>prev_high) & (low<prev_low)

## H1 aggregation
- floor to UTC hour
- complete = count==12 AND first_observed==bucket AND last_observed==bucket+55min AND regular 5-min spacing
- decision_time = bucket + 1 hour (after H1 completes)
- Features only on complete H1 bars

## Evaluation design
- Primary instrument Track A: XAUUSD (hash match 88e00425…)
- Class A transfer: FX Bid/Ask instruments — structural occurrence + forward association only; no claim of gold edge transfer
- Horizons: 1, 2, 4, 8 H1 bars (aligned to original 4-bar horizon focus) PLUS M5-equivalent notes
- Entry convention for association layer: after completed H1 decision_time; forward from next H1 open
- No cash PF as property of pattern alone (no new stop/target invented)
- Cost model for economic interpretation: XAU roundtrip 0.42 price units (SOURCE_REPORTED); FX 2.8 pips
- Chronological 60/20/20; final 20% EXPOSED — exploratory only
- Overlap: report raw counts and non-overlapping (skip until prior horizon ends)

## Materiality (preregistered)
Association is EXPLORATORY_PROMISING only if:
1. Validation mean forward return same sign as development
2. Validation n >= 50 non-overlapping
3. |mean return| in price units exceeds 1× stated RT cost on validation
Else EXPLORATORY_NEGATIVE or EXPLORATORY_INCONCLUSIVE

## Multiple testing
Two primary hypotheses × one primary instrument × limited horizons. No threshold sweeps.

## Status vocabulary
NOT_EVALUATED | INPUTS_UNAVAILABLE | IMPLEMENTATION_UNVERIFIED | EXPLORATORY_NEGATIVE | EXPLORATORY_INCONCLUSIVE | EXPLORATORY_PROMISING_UNCONFIRMED | CONFIRMATORY_TEST_REQUIRED
