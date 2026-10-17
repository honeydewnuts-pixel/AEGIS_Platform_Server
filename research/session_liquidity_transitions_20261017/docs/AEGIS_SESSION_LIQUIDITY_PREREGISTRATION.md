# AEGIS Session-Specific Liquidity Transitions — Preregistration

**Status:** FROZEN before outcome analysis  
**Date:** 2026-10-17  
**Branch:** `research/session-liquidity-transitions-20261017`  
**Base checkpoint:** `305fbe79e19954adf700071f4ff56646a829e9b6`  
**Commit this file before any outcome-analysis run.**

---

## 1. Research question

Do fixed major FX session-transition windows show a different distribution of short-horizon absolute price displacement and realised range than matched same-instrument non-transition windows at other times of day, after accounting for ordinary intraday seasonality?

**Important:** Available data are Bid/Ask M5 OHLC only. There is **no** volume, depth, or tick intensity. This study measures **price behaviour around session clocks**, not liquidity directly. Any liquidity language is interpretive only.

---

## 2. Primary hypothesis (H1)

At the **London open transition** (defined below), the mean absolute Bid-close displacement over the post-boundary horizon H\* is **larger** than at matched non-transition control times for the same instrument, with an effect that is not explained solely by the unconditional same-hour-of-day distribution.

## 3. Null (H0)

Mean absolute post-boundary displacement at the London open equals (or is not meaningfully larger than) the mean absolute displacement over the same horizon starting at preregistered non-transition control hours.

## 4. Alternative

An effect may exist only for some instruments, some years, or only relative to a weak control; such results are **not** treated as a universal session-transition phenomenon.

---

## 5. Session boundaries (primary set — small, fixed)

All times **UTC**. Source timestamps are treated as **UTC** based on prior research metadata (`+00:00` in CSV); if that convention is wrong, the study is **INSUFFICIENT DATA** for local-session claims.

| ID | Name | Boundary (UTC) | Pre window | Post window |
|----|------|----------------|------------|-------------|
| T1 | **London open** (PRIMARY) | 07:00 | [06:00, 07:00) | [07:00, 07:00+H) |
| T2 | NY open | 12:00 | [11:00, 12:00) | [12:00, 12:00+H) |
| T3 | London–NY overlap start | 13:00 | [12:00, 13:00) | [13:00, 13:00+H) |

**DST note:** Fixed UTC windows do **not** track London/NY local DST. Primary analysis uses fixed UTC. Secondary label only: report whether the calendar date falls in a period when London is on BST (last Sunday March–last Sunday October, approximate rule) — exploratory, not primary.

Weekends: exclude events whose boundary falls on Saturday or Sunday UTC.

---

## 6. Primary outcome

**H\* = 12 M5 bars (60 minutes).**

```
abs_disp = |BidClose[t_end] − BidClose[t_boundary]|
```

where `t_boundary` is the first M5 bar with hour:minute equal to the boundary (or the first bar at/after boundary if exact bar missing), and `t_end = t_boundary + H\*`.

**Primary comparison:** for each instrument, mean `abs_disp` on T1 event days vs mean `abs_disp` on **control starts** at **03:00 UTC** and **15:00 UTC** (non-transition hours), same horizon, same instrument, same weekday filter.

**Primary metric:** ratio `mean_event / mean_control` and difference in means; day-clustered bootstrap CI on the difference.

---

## 7. Secondary outcomes (exploratory)

- Horizons H ∈ {6, 12, 24} bars.  
- Realised range: max(BidHigh)−min(BidLow) over post window.  
- Signed displacement (not primary).  
- Median spread in post window vs pre window.  
- T2 and T3 same structure as T1.  
- By instrument; by chronological half of development sample.

---

## 8. Instrument universe

13 Bid/Ask pairs under `/home/workdir/artifacts/AEGIS_CSV_5Y/*_M5_BIDASK_5Y.csv`. Exclude midpoint-only. Hashes recorded at run time.

---

## 9. Sample rules

- Development = first **80%** of rows per series. Final 20% = **EXPOSED** (diagnostic only, not for selection).  
- Minimum **100** T1 events per instrument for instrument-level primary inference; else INSUFFICIENT.  
- Cross-section: need ≥5 instruments with sufficient n for a pooled claim.

---

## 10. Baselines

1. **Primary control:** same instrument, starts at 03:00 and 15:00 UTC, weekdays, same H.  
2. **Same-hour control:** displacement starting at 07:00 on a **random weekday without requiring “session narrative”** — actually 07:00 **is** T1; so primary contrast is T1 vs 03:00/15:00.  
3. **Unconditional:** all weekday starts every 12 bars (subsample) — secondary.

---

## 11. Statistics

- Day-clustered bootstrap on event-level abs_disp differences (or on paired day means where both event and control exist that day).  
- 1000 resamples, seed **17**, percentile 95% CI.  
- Primary family: 13 instruments × T1 only → report how many have CI for (mean_event − mean_control) entirely above 0.  
- No claim of “confirmation” from secondary horizons/transitions without labelling exploratory.

---

## 12. Economic materiality (not trading P&L)

```
materiality = mean_abs_disp / median_spread
```

Gate: if median across sufficient instruments of `mean_abs_disp_event / median_spread < 2`, effect is **economically immaterial** for trading design even if statistically larger than control.

Does **not** charge commission/slippage into a fake trade; descriptive only.

---

## 13. Decision rules

| Outcome | Condition |
|---------|-----------|
| A NO EFFECT | Primary difference CI includes 0 for ≥10/13 instruments |
| B SEASONALITY ONLY | Event mean similar to other busy hours (if secondary shows 07:00≈12:00≈13:00) — documented |
| C STATISTICAL BUT IMMATERIAL | Difference >0 with CI>0 on ≥5 instruments but materiality < 2 |
| D INSTRUMENT-SPECIFIC | ≥1 but <5 instruments meet statistical + materiality |
| E UNSTABLE | Sign of (event−control) flips across chronological halves on majority |
| F PROMISING | ≥5 instruments: CI of difference >0, materiality ≥2, same sign both halves |
| G INSUFFICIENT DATA | Timestamp/session coverage failure |

**F does not authorise a Rulebook** — only a written proposal for a separate executable experiment.

---

## 14. Prohibited

- Grid over boundaries/horizons after seeing results.  
- Claiming liquidity measurement.  
- Claiming executable profit from Bid displacement.  
- Changing V53.6 / production_authorized / qualification gates.

---

## 15. Reproduction

```bash
python3 research/session_liquidity_transitions_20261017/scripts/run_session_liquidity_research.py
```

Expected outputs under `research/session_liquidity_transitions_20261017/outputs/`.

---

**Preregistration frozen.**
