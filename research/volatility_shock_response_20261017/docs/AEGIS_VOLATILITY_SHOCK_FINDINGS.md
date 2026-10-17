# Volatility-Shock Response — Findings

**Preregistration hash:** `3b940d6fe42b07ab95018caa3d49c07ee733434793f59b78e4fff09842e312dc`  
**Preregistration commit:** `c8647f3291412b64c45fddf96b0014df5bf0b5d1`  
**Branch:** `research/volatility-shock-response-20261017`  
**Analysis date:** 2026-10-17  

---

## Executive decision

**D — INSTRUMENT-SPECIFIC / NO GENERAL CONDITIONAL EDGE**  
(with economic magnitude far below materiality gate)

After ≥2× preceding 20-bar mean absolute displacement shocks, direction-adjusted 60-minute Bid displacement does **not** differ from matched non-shock controls in a way that generalises across instruments or exceeds one median spread.

- Sufficient instruments: **13/13**  
- CI of (shock − control) excluding 0: **3/13** (all **reversal**-leaning: EURCHF, NZDJPY, USDCHF)  
- Materiality |diff|/median_spread ≥ 1: **0/13**  
- Continuation rate after shocks ≈ **0.46–0.48** (below 50%)  
- Matched-control continuation similar  

**No Rulebook proposal. No executable experiment authorised.**

---

## Primary definition (fixed before outcomes)

| Parameter | Value |
|-----------|-------|
| Pre-vol | mean \|ΔBidClose\| over prior 20 bars |
| Shock | Disp / pre_vol ≥ 2.0 |
| Horizon H\* | 12 bars (60 min) |
| Outcome | direction × (BidClose[i+H] − BidClose[i]) |
| Controls | same hour, vol ±25%, disp ±50%, non-shock, ≤3 nearest within ±1500 bars |
| Cooldown | 12 bars |

---

## Instrument summary (development 60%)

| Symbol | n_matched | mean_r_shock | mean_r_ctrl | diff | CI excludes 0 | mat |
|--------|----------:|-------------:|------------:|-----:|:-------------:|----:|
| Most pairs | ~9.3k–10k | ~0 | ~0 | ~0 | no | ≪1 |
| EURCHF | 9604 | negative | near 0 | negative | **yes (rev)** | 0.30 |
| NZDJPY | 9893 | negative | near 0 | negative | **yes (rev)** | 0.31 |
| USDCHF | 9770 | negative | near 0 | negative | **yes (rev)** | 0.25 |

Full table: `outputs/instrument_summary.csv` and `outputs/volatility_shock_summary.json`.

---

## Gate table

| Gate | Status |
|------|--------|
| Prereg before outcomes | **PASS** |
| Matched controls (hour/vol/disp) | **PASS** (implemented) |
| Cross-instrument CI effect | **FAIL** (3/13) |
| Materiality ≥1 | **FAIL** (0/13) |
| Chronological same-sign stability (majority) | **FAIL** (5/13) |
| Trading / Rulebook | **NOT AUTHORISED** |

---

## Interpretation

Large M5 moves are common under the 2× definition (~10k de-duplicated events per pair). Subsequent 60-minute direction-adjusted drift is small, slightly more often **against** the shock than with it, and **statistically indistinguishable from matched ordinary moves** on most pairs. Where a CI excludes zero, the effect is a **weak reversal** fraction of one spread — not a tradable edge.

Consistent with: mean-reversion of extremes + no incremental information once size and time-of-day are matched.

---

## Governance

V53.6 unchanged · no production · no orders · Bid-path ≠ executable P&L · final 20% EXPOSED
