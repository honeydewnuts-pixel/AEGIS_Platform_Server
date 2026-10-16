# AEGIS Failed Price Discovery — Preregistration

**Status:** FROZEN before outcome analysis  
**Date:** 2026-10-16  
**Branch:** `research/failed-price-discovery-20261016`  
**Base checkpoint:** `2331619c2d128e26966951e07be554cf60bf2767`  
**This document must be committed and hashed before outcome-analysis scripts are run.**

---

## 1. Research question

When price attempts to establish a new level beyond a previously known boundary but fails and returns through that boundary, does subsequent price behaviour differ meaningfully from an appropriate baseline in the direction of the return, and is any effect large enough to be economically interesting relative to typical spread?

This is a **measurement study**. It is not a trading Rulebook and does not assert profitability.

---

## 2. Rationale

Prior post-discovery work rejected simple directional persistence after ATR impulses and simple low-vol expansion at M5 horizons 6–24. Failed breakouts (attempted discovery of a new price level that is not sustained) are a distinct economic idea: the market probes beyond a known range and is rejected, after which mean-reversion through the boundary may dominate.

We test whether that rejection episode carries **incremental** directional information versus a matched or unconditional baseline.

---

## 3. Primary boundary definition (ONE only)

**Prior 48-bar range high / low on Bid.**

- Lookback **L = 48** M5 bars (4 hours of completed bars).  
- At bar index `i` (0-based), using only bars `i−48 … i−1` (exclusive of bar `i`):  
  - `boundary_high[i] = max(BidHigh[i−48 : i])`  
  - `boundary_low[i]  = min(BidLow[i−48 : i])`  
- Boundary is frozen at the start of bar `i` for event evaluation on and after `i`.  
- Incomplete / missing bars: if fewer than 48 valid bars exist in the window, no boundary is defined (no event).  
- Price side for boundary: **Bid** high/low only (descriptive state). Executable Ask/Bid distinction is reserved for any later tradability simulation (not this phase).  
- No session filter in the primary definition (session is a secondary exploratory label only).  
- Timezone: timestamps are UTC; no DST adjustment beyond what the source data already encode.

**No other lookbacks** will be tested as primary. L=48 is fixed.

---

## 4. Attempted break and failed break (mechanical)

### 4.1 Attempted break (at bar t ≥ i)

- **Up-break attempt:** `BidHigh[t] > boundary_high[t]` (boundary computed from bars before `t`).  
- **Down-break attempt:** `BidLow[t] < boundary_low[t]`.

### 4.2 Failure condition (confirmation)

After an up-break attempt that first occurs at `t0`:

- Failure is confirmed at the first bar `t_f > t0` where **`BidClose[t_f] < boundary_high[t0]`**  
  (price has closed back through the boundary that was broken).  
- Require `t_f − t0 ≤ H_fail` with **H_fail = 12** bars (failure must occur within 1 hour of the first break).  
- If the close never returns through the boundary within 12 bars, the attempt is **not** a failed break (sustained or open-ended; excluded from the failed-break set).

Symmetric for down-break:

- First `t0` with `BidLow[t0] < boundary_low[t0]`.  
- Failure at first `t_f > t0` with **`BidClose[t_f] > boundary_low[t0]`** and `t_f − t0 ≤ 12`.

### 4.3 Event confirmation time

`t_f` = first bar satisfying the failure close condition.  
All outcomes use information available at the **close of t_f** and bars **after** `t_f` only.

### 4.4 Evaluation start

Descriptive outcomes start at **bar t_f + 1** (first bar after confirmation).  
No same-bar entry using future information. No retrospective fill at the boundary.

### 4.5 Direction of the event

- Failed **up**-break → expected subsequent pressure is **down** (return direction = −1).  
- Failed **down**-break → expected subsequent pressure is **up** (return direction = +1).

Signed outcomes are measured in the **return direction** (so positive signed return means price moved in the hypothesised post-failure direction).

---

## 5. Primary outcome

**Primary horizon H\* = 12** M5 bars (1 hour).

```
r_signed = return_direction × (BidClose[t_f + H*] − BidClose[t_f])
```

**Primary metric:** mean of `r_signed` over eligible failed-break events in the development sample, compared to the preregistered baseline mean.

**Economic relevance proxy:** `mean(r_signed) / median_spread` on the same instrument.  
An effect is **not** considered economically interesting for later trading design if `|mean|/median_spread < 1` on the primary horizon (order-of-magnitude gate only; not a trading simulation).

---

## 6. Secondary outcomes (exploratory; not decision criteria)

- Horizons **H ∈ {6, 12, 24}** for the same signed return.  
- Continuation rate: fraction of events with `r_signed > 0`.  
- MFE / MAE over path `t_f+1 … t_f+H` in the return direction (Bid path).  
- By instrument; by up-fail vs down-fail; by chronological half of the development window.

---

## 7. Null hypothesis and baselines

**H0:** Failed-break events provide no incremental directional information; mean signed return equals (or is not meaningfully larger than) the baseline.

**Baselines (preregistered):**

1. **Unconditional:** mean of `sign_random × (BidClose[j+H] − BidClose[j])` is not used; instead use mean absolute move is secondary. Primary baseline = mean of **direction-matched random times**: for each event, draw a random index in the same instrument’s development window with the same return_direction label rate — simpler primary baseline:  

   **Unconditional signed-as-zero benchmark:** under no information, E[r_signed] = 0. Report whether mean r_signed differs from 0 with a dependence-aware interval.

2. **Matched non-event:** bars that are **not** failed-break confirmations, same instrument, same hour-of-day bucket (0–23), same ATR quartile (quartiles from development sample), same horizon return in a randomly assigned ±1 direction with equal probability — used as secondary control for “any move of similar volatility.”

Primary decision uses baseline (1): difference of mean r_signed from 0, with block-bootstrap CI.

---

## 8. Overlap / de-duplication (preregistered)

- After an event is confirmed at `t_f`, **suppress** new failed-break confirmations on the same instrument until `t_f + H*` (cooldown = primary horizon).  
- Primary analysis uses the **de-duplicated** set.  
- Secondary robustness: also report statistics on the raw (overlapping-allowed) set without choosing the better of the two for the headline.

---

## 9. Data

- Source: `/home/workdir/artifacts/AEGIS_CSV_5Y/*_M5_BIDASK_5Y.csv`  
- Instruments: the 13 Bid/Ask pairs in the post-discovery data manifest.  
- Exclude midpoint-only series.  
- Hashes must match the manifest before analysis.  
- Chronology: **development = first 80%** of each series by row count. Final 20% is **EXPOSED** from prior research — not used for selection; may be reported only as a labelled diagnostic.

---

## 10. Sample requirements

- Per instrument, de-duplicated events in development: if **n < 50**, mark that instrument **INSUFFICIENT** for instrument-level inference.  
- Cross-section: if fewer than **5** instruments have n ≥ 50, overall result is **INCONCLUSIVE**.

---

## 11. Statistical method

- Descriptive means, medians, continuation rates.  
- **Block bootstrap** on the series of event-level r_signed, clustered by calendar day of t_f (all events on the same UTC date form a block).  
  - Resamples: **1000**  
  - Seed: **42**  
  - CI: percentile 95% for mean r_signed  
- If day-blocks < 30 for an instrument, report CI as unreliable and mark instrument-level inference limited.  
- Do not treat overlapping bars as independent observations.  
- Multiple instruments: report effect sizes per instrument; do not declare a universal effect from unadjusted p-hacking across 13 pairs.

---

## 12. Missing data

- Skip boundary computation when lookback incomplete.  
- Skip events where `t_f + H*` exceeds the development window end.  
- No price imputation.

---

## 13. Decision rules (before seeing outcomes)

| Result | Condition |
|--------|-----------|
| **REJECT** | Mean r_signed ≤ 0 on primary, or 95% block-bootstrap CI includes 0 and mean is not economically interesting (\|mean\|/spread < 1) across the majority of sufficient instruments |
| **SUPPORTIVE (not tradable yet)** | Mean r_signed > 0 with CI excluding 0 on ≥5 instruments with n≥50, and median \|mean\|/spread ≥ 1, stability same sign in both chronological halves — still **not** a Rulebook |
| **INCONCLUSIVE** | Insufficient events, unstable sign across halves, or CI too wide |

**Tradability gate (later phase only):** even a supportive measurement does **not** authorise a Rulebook. A separate broker-correct simulation with full-cost R would be required, with frozen rules and no use of EXPOSED finals for tuning.

---

## 14. What will NOT be done

- No grid over L, H_fail, indicators, stops, or targets.  
- No selection of best instrument/horizon after results.  
- No promotion to V53.6 or production.  
- No claim that Bid-path returns equal executable round-trip P&L.

---

## 15. Conditions for amendment

Only if data-quality inspection shows the definition is impossible (e.g. insufficient bars). Amendment requires preserving this file, documenting the reason, and re-hashing before outcomes.

---

**Preregistration frozen. Outcome analysis must cite this file and its content hash.**
