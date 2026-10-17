# AEGIS Volatility-Shock Response — Preregistration

**Status:** FROZEN before outcome analysis  
**Date:** 2026-10-17  
**Branch:** `research/volatility-shock-response-20261017`  
**Base checkpoint:** `1706bd5242276a98f49bd02e79065a1b45039274`  
**Commit this file before any outcome-analysis run.**

---

## 1. Research question

Do unusually large M5 Bid price displacements (volatility shocks) contain information about subsequent **direction-adjusted** Bid displacement beyond what is explained by preceding volatility, initial move size, and time-of-day?

Three possible answers (no preference):

- **Continuation** after shocks vs matched controls  
- **Reversal** after shocks vs matched controls  
- **No material conditional edge** after matching  

---

## 2. Null / alternative

**H0:** Mean direction-adjusted subsequent displacement after a shock equals that after matched non-shock moves.  
**H1:** Shock and matched-control means differ (two-sided).

---

## 3. Primary shock definition (ONE)

At completed bar index `i` (0-based):

1. **Pre-vol** = mean of `|BidClose[j] − BidClose[j−1]|` for `j ∈ [i−20, i−1]` (20 completed bars; requires `i ≥ 21`).  
2. **Disp** = `|BidClose[i] − BidClose[i−1]|`.  
3. **Shock** if `pre_vol > 0` and `Disp / pre_vol ≥ 2.0`.  
4. **Direction** `d = sign(BidClose[i] − BidClose[i−1])` ∈ {−1, +1}; skip if zero.  
5. Event is **observable** only at the **close of bar i**. Outcomes use bars **after** `i` only.

Threshold **2.0** and lookback **20** are fixed research choices, not tuned on outcomes.

Secondary (exploratory only): threshold 2.5 — not decision criteria.

---

## 4. Primary outcome

**Horizon H\* = 12** M5 bars (60 minutes).

```
r = d × (BidClose[i + H*] − BidClose[i])
```

Positive `r` = continuation in shock direction; negative = reversal.

**Primary estimand:** difference of mean `r` between shock events and matched controls (development sample).

---

## 5. Secondary outcomes

- Horizons H ∈ {6, 12, 24}  
- Continuation rate P(r > 0)  
- Median r  
- Materiality: mean(|r|) / median_spread (descriptive)  
- By instrument; by chronological 60%/20% stability window  

---

## 6. Overlap rule

After accepting a shock at `i`, **suppress** new shocks until `i + H*` (cooldown = 12).  
Report raw count and de-duplicated count.

---

## 7. Matched controls

For each shock at bar `i`:

- Same instrument  
- Non-shock bars (`Disp / pre_vol < 2.0`)  
- Same hour-of-day (UTC)  
- Preceding volatility within **±25%** of the shock’s `pre_vol`  
- Absolute initial disp within **±50%** of shock’s Disp (ordinary moves of similar size, not shocks)  
- Weekday only if shock is weekday  

Pick up to **3** nearest controls in time within ±5 trading days; if none, mark unmatched.

**Do not match on future outcomes.**

Primary comparison uses **matched pairs** where at least one control exists. Unmatched shocks reported separately.

---

## 8. Data

- 13 Bid/Ask M5 CSVs under `/home/workdir/artifacts/AEGIS_CSV_5Y/`  
- Timestamps treated as UTC (prior research convention)  
- Development = first **60%** of rows; stability = next **20%**; final **20%** EXPOSED (prior research) — not used for primary decision  
- Primary decision uses **development only**

---

## 9. Sample requirements

- Per instrument: ≥ **80** matched shock events in development → sufficient  
- Cross-section: ≥ **5** sufficient instruments for a pooled claim  

---

## 10. Statistics

- Mean r_shock − mean r_control  
- Day-clustered bootstrap (cluster by calendar date of event), **1000** resamples, seed **20261017**, 95% percentile CI  
- Report instrument-level and pooled (equal-weight instruments with sufficient n)  
- Secondary rates: Fisher/bootstrap exploratory  

---

## 11. Economic materiality (not trading P&L)

```
mat = |mean r_shock − mean r_control| / median_spread
```

If median mat across sufficient instruments **< 1**, effect is economically weak for Rulebook design even if statistically nonzero.

Bid-path displacement ≠ executable profit.

---

## 12. Decision rules

| Code | Condition |
|------|-----------|
| A | CI of (shock−control) includes 0 on ≥10/13 instruments (or majority of sufficient) |
| B | Apparent effect vanishes when matched on hour/vol/disp (same as A if matching works) |
| C | CI excludes 0 on ≥5 instruments but median mat < 1 |
| D | Effect only on <5 instruments or flips sign across 60%/20% windows |
| E | ≥5 instruments: CI excludes 0, same sign both windows, median mat ≥ 1 — **proposal only**, no Rulebook |
| F | Insufficient events/matches |

---

## 13. Prohibited

- Threshold search after outcomes  
- Trading strategy / stops / targets  
- Claiming liquidity or news mechanisms  
- V53.6 / production changes  

---

## 14. Reproduction

```bash
python3 research/volatility_shock_response_20261017/scripts/run_volatility_shock_research.py
```

Must fail if preregistration hash mismatch.

---

**Preregistration frozen.**
