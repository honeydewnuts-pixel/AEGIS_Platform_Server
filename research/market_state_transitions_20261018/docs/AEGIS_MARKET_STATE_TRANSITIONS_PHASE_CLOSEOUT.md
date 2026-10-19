# Phase 5 Formal Closure — Market-State Transitions and Volatility Clustering

**Date:** 2026-10-19  
**Branch:** `research/market-state-transitions-20261018`  
**Final commit before this closure record:** `e931f3f331ee4497e0696630f5692a46b6d2bd77`

---

## 1. Research question

Can a market-state classification based only on information available at time t improve understanding of subsequent price behaviour and risk beyond what a simple recent-volatility measurement already indicates?

## 2. Final decision

**RETAIN AS DESCRIPTIVE MARKET-BEHAVIOUR EVIDENCE ONLY.**

- DO NOT promote a Rulebook.
- DO NOT open another volatility-threshold optimisation.
- DO NOT claim executable alpha.

## 3. Key findings

- Primary contrast: ELEVATED (rv > past-only P80) vs B_HIGH (rv > past-only P67), H*=12 absolute Bid displacement.
- CI of difference excludes 0 on 13/13 instruments (positive, small).
- Materiality >= 1 on 5/13 instruments.
- Same-sign stability on 13/13.
- Interpretation: a threshold refinement of the same recent-volatility feature, not a distinct economic mechanism.

## 4. Materiality correction

Authoritative count is 5 of 13 (not any external "15/13" prose). Formula: |mean_abs_ELEVATED - mean_abs_B_HIGH| / median_spread_development.

## 5. Remaining methodological limitations

- 50-bar percentile refresh vs continuous expanding wording in preregistration.
- Bootstrap unpaired (not day-clustered matched).
- Full bit-exact pipeline regeneration not repeated at closeout.
- Final 20% historical data is EXPOSED.
- OHLC-only: not liquidity, not executable P&L.

## 6. Why closed as a current alpha path

Incremental information is modest and is explained as a stricter cut on the same rv already used by the baseline. Further percentile grids on the same feature would not constitute a new economic hypothesis.

## 7. Branch and final commit

research/market-state-transitions-20261018 @ e931f3f331ee4497e0696630f5692a46b6d2bd77 (plus this documentation-only closure commit).

## 8. Rule for future work

Future research must use a genuinely different economic hypothesis, not a relabelled volatility-threshold or session-open seasonality study on the same M5 Bid path measures.

V53.6 and production authorization remain unchanged.
