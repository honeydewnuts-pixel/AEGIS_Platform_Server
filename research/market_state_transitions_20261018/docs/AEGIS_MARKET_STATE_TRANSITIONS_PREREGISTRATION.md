# AEGIS Market-State Transitions — Preregistration

**Status:** FROZEN before outcome analysis  
**Date:** 2026-10-18  
**Branch:** `research/market-state-transitions-20261018`  
**Base checkpoint:** `8b46f42a8cae2511f15339fe66354180af09a1fe`  
**Commit this file before any outcome-analysis run.**

---

## 1. Research question

Can a market-state classification based only on information available at time *t* improve understanding of subsequent price behaviour and risk **beyond** what a simple recent-volatility measurement already indicates?

Three possible answers (no preference):

- States add stable incremental information  
- States largely restate recent volatility (no incremental value)  
- Insufficient / inconclusive  

This is **not** a trading strategy. Bid-path measures ≠ executable P&L.

---

## 2. Null / alternative

**H0:** Conditional distributions of subsequent absolute Bid displacement at H*=12, given richer states, do not differ materially from those given a simple recent-volatility baseline strata with comparable recent activity.

**H1:** At least one richer state shows a stable, cross-instrument difference in mean absolute subsequent displacement (or realised range) relative to the matched baseline stratum, with economic materiality |Δ| / median_spread ≥ 1 on ≥5 instruments.

---

## 3. Simple baseline (B0)

At completed bar `i` (observable at close of `i`):

- `rv[i] = mean(|BidClose[j] − BidClose[j−1]|)` for `j ∈ [i−20, i−1]` (20 bars; requires `i ≥ 21`)  
- Baseline strata from **past-only expanding** percentiles of `rv` on bars `[21, i−1]` within the same instrument (UTC weekday only for percentile estimation):  
  - **B_LOW:** rv ≤ P33 of history to i−1  
  - **B_MID:** P33 < rv ≤ P67  
  - **B_HIGH:** rv > P67  

If fewer than 500 historical rv samples, mark state UNKNOWN (exclude).

---

## 4. Richer states (S)

Using same `rv[i]`:

1. **QUIET:** rv ≤ P20 of past-only history to i−1  
2. **ORDINARY:** P20 < rv ≤ P80  
3. **ELEVATED:** rv > P80  
4. **PERSIST_ELEV:** ELEVATED for the current bar and the prior 2 completed bars (all three rv > their respective past P80 at those times)  
5. **Q→A transition:** prior bar was QUIET and current is ELEVATED  
6. **A→Q transition:** prior bar was ELEVATED and current is QUIET  

States 1–3 partition; 4–6 are overlays (a bar can be both ELEVATED and PERSIST_ELEV or Q→A).

All percentiles past-only. Warm-up: exclude until ≥500 historical rv values.

---

## 5. Primary outcome

**H\* = 12** M5 bars.

```
abs_disp = |BidClose[i+H*] − BidClose[i]|
```

Observable only after close of `i`. Primary estimand: mean abs_disp by state vs mean abs_disp in the **corresponding baseline stratum** (QUIET vs B_LOW, ELEVATED/PERSIST_ELEV/Q→A vs B_HIGH, ORDINARY vs B_MID, A→Q vs B_HIGH→B_LOW narrative reported descriptively).

Primary confirmatory contrast: **ELEVATED vs B_HIGH** mean abs_disp difference (does “elevated” add anything beyond being in the high baseline tercile?).

Secondary: QUIET vs B_LOW; PERSIST_ELEV vs ELEVATED; Q→A vs ELEVATED; signed returns; continuation rates; materiality |diff|/median_spread.

---

## 6. Data and chronology

- 13 Bid/Ask M5 pairs under `/home/workdir/artifacts/AEGIS_CSV_5Y/`  
- Timestamps UTC  
- Development = first **60%** of rows (primary decision)  
- Stability = next **20%**  
- Final **20%** = EXPOSED (prior research) — not used for selection  
- Overlap: subsample events every 12 bars within each state for independence approximation; report raw and thinned counts  

---

## 7. Statistics

- Day-clustered bootstrap on event-level abs_disp, **1000** resamples, seed **20261018**, 95% percentile CI for mean differences  
- Minimum 80 thinned events per state per instrument for instrument-level inference  
- Cross-section: ≥5 instruments with sufficient n for a pooled claim  
- Multiple testing: primary contrast is ELEVATED vs B_HIGH only; all else exploratory  

---

## 8. Economic materiality

```
mat = |mean_abs_state − mean_abs_baseline| / median_spread
```

If median mat across sufficient instruments for primary contrast **< 1**, classify as economically weak.

---

## 9. Decision rules

| Code | Condition |
|------|-----------|
| CLOSE | Primary contrast CI includes 0 on ≥10/13 (or majority of sufficient); or mat < 1 on all |
| DESCRIPTIVE_ONLY | Statistically detectable but mat < 1 or unstable across 60%/20% |
| INCONCLUSIVE | Insufficient samples or unstable sign |
| INVALID | Look-ahead / data integrity failure |

No path from this study alone to Rulebook promotion.

---

## 10. Prohibited

- Threshold search after outcomes  
- Trading strategy construction  
- Claiming liquidity from OHLC  
- V53.6 / production changes  

---

## 11. Reproduction

```bash
python3 research/market_state_transitions_20261018/scripts/run_market_state_transitions.py
```

Must fail if preregistration hash mismatch.

---

**Preregistration frozen.**
