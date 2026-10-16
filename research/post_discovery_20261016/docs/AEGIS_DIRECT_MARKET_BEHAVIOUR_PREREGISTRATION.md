# AEGIS Direct Market-Behaviour Study — Preregistration

**Status:** FROZEN before outcome analysis  
**Date:** 2026-10-16  
**Research branch:** research/broker-realistic-discovery-20261014  
**Checkpoint commit:** 8385fc60ea16a195ba00a64697ddc07d4f526b9c  
**This file must be committed / hashed before outcome scripts are run.**

---

## 1. Research questions

**D1 — Directional persistence**  
After a measurable directional move on M5 Bid data, does the subsequent market show statistically and economically meaningful continuation in the same direction beyond an appropriate null baseline?

**D2 — Volatility expansion after low volatility**  
After a defined low-volatility state on M5 Bid data, does subsequent realised range expand more often or more strongly than an unconditional matched baseline?

These are **measurement studies**, not trading Rulebooks.

---

## 2. Economic / behavioural rationale

- Short-horizon momentum and volatility clustering are classical microstructure / statistical properties of FX.  
- Prior strategy scans failed under full costs; before inventing more rules we ask whether any raw behavioural effect is large enough to matter after spread.  
- A null or economically tiny effect would justify **rejecting** persistence/expansion as a foundation for the next Rulebook family.

---

## 3. Hypotheses

| ID | Primary (H1) | Null (H0) |
|----|--------------|-----------|
| D1 | Mean signed subsequent return over horizon H, conditional on a prior directional move of size ≥ k·ATR, differs from the unconditional mean return over H in the same direction with effect size large enough that |mean|/spread_proxy > 1 | No difference from unconditional baseline; or difference too small to exceed typical half-spread |
| D2 | Mean future range over H after a low-vol state (ATR below its trailing median) exceeds the unconditional mean future range over H | No excess expansion vs unconditional baseline |

**Alternative:** Effects exist but are instrument-specific, session-specific, or unstable across chronological periods → INCONCLUSIVE for a universal Rulebook.

---

## 4. Data requirements

- Source: `/home/workdir/artifacts/AEGIS_CSV_5Y/*_M5_BIDASK_5Y.csv`  
- Instruments: the 13 true Bid/Ask pairs listed in `AEGIS_RESEARCH_DATA_MANIFEST.csv`  
- Exclude: NZDUSD (mid-only)  
- Price side for state/outcome measurement: **Bid** OHLC (directional study does not require executable Ask for measurement; tradability conclusions later will)  
- Hashes: must match manifest before analysis  
- Timezone: UTC  
- No forward-fill of missing bars  

---

## 5. Instrument inclusion / exclusion

- Include if Bid/Ask columns present and SHA256 matches manifest.  
- Exclude midpoint-only or incomplete coverage.  
- Report every instrument separately; do not pool without disclosing dependence.

---

## 6. Fixed observation horizons (preregistered; not tuned after results)

Horizons in **M5 bars** (justified by M5 resolution and prior session-scale research interest):

- **H ∈ {6, 12, 24}**  (30 min, 1 h, 2 h)

No other horizons will be examined in this study.

---

## 7. Market-state definitions (past information only)

### D1 — Directional move event (at bar i, using bars ≤ i)

- `move = BidClose[i] − BidClose[i − L]` with **L = 12** (1 hour lookback).  
- ATR = Wilder ATR14 on Bid high/low/close, value at i.  
- Event if `|move| ≥ 1.0 × ATR[i]` and ATR[i] is finite and > 0.  
- Sign of event = sign(move).  
- Observation time = close of bar i. Outcomes use bars **i+1 … i+H** only.

### D2 — Low-volatility state (at bar i)

- ATR14 at i.  
- Trailing median of ATR14 over the prior **100** bars (exclusive of i if needed to avoid leakage: use rolling median ending at i−1).  
- Low-vol event if `ATR[i] < median_ATR[i−1]` and both finite.  
- Outcomes: realised range over i+1 … i+H = max(BidHigh) − min(BidLow) on that window.

---

## 8. Outcome definitions

**D1**

- `r_H = BidClose[i+H] − BidClose[i]` (signed).  
- `cont_H = 1` if sign(r_H) == sign(move), else 0.  
- MFE / MAE over the path i+1…i+H relative to BidClose[i], signed with event direction.

**D2**

- `range_H = max(BidHigh[i+1:i+H]) − min(BidLow[i+1:i+H])`.  
- `ratio_H = range_H / ATR[i]`.  
- Expansion indicator: `range_H > median unconditional range_H` estimated on the same chronological development sample (not including future relative to i).

---

## 9. Primary and secondary metrics

**Primary D1:** mean signed return in event direction over H=12, vs unconditional mean |return| baseline; report also continuation probability.  
**Primary D2:** mean ratio_H at H=12 after low-vol vs unconditional mean ratio_H.  

Secondary: H=6 and H=24; by instrument; by long vs short events; by London (07–16 UTC) vs Asian (00–07) session of the event bar.

---

## 10. Baselines / null comparisons

1. **Unconditional:** same horizon returns/ranges on all bars (or random sample of equal size) in the same chronological window.  
2. **Sign-randomised:** keep event times and |move|, randomly flip sign 500 times; distribution of mean continuation.  
3. **No-information:** probability 0.5 continuation for D1.

---

## 11. Statistical method

- Descriptive means, medians, continuation rates.  
- Non-overlapping event subsample as robustness (keep event only if ≥ H bars after previous kept event).  
- Block bootstrap (block length 288 M5 bars ≈ 1 trading day) for 95% CI on mean signed return / mean ratio — if computationally feasible; otherwise report simple SE under independence **and state the limitation**.  
- Do not treat correlated bars as independent for p-value claims.  
- Multiple instruments × 3 horizons: report effect sizes; avoid declaring “significant” solely from unadjusted p-values.

---

## 12. Missing data

- Skip events where i+H exceeds series end.  
- Skip if ATR or median undefined.  
- No imputation of prices.

---

## 13. Chronological boundaries

- **Development / measurement window:** first 80% of each series by row count (through end of prior “validation” region).  
- **Do not** use the final 20% to choose definitions, thresholds, or horizons (that segment is **EXPOSED** from prior scans).  
- Final 20% may be reported only as a **labelled diagnostic**, not as confirmation.

---

## 14. Known limitations

- Bid-side measurement ≠ executable round-trip P&L.  
- M5 OHLC cannot resolve intrabar path.  
- 0.7 pip commission assumption is not used here (measurement study); cost relevance assessed qualitatively vs median spread.  
- Overlapping events induce dependence.  
- No economic calendar filter.

---

## 15. Conditions to proceed to a trading simulation

All must hold:

1. Effect clearly defined and visible in development data.  
2. Not explained solely by lookahead or overlap artifact (non-overlap robustness consistent in sign).  
3. Reasonably stable across first vs second half of the 80% window.  
4. Effect size and uncertainty reported.  
5. Instrument dependence disclosed.  
6. Plausible executable entry/exit can be stated.  
7. Expected move has a plausible chance of exceeding typical spread + 0.3+0.3+0.7 pips.  
8. Next trading hypothesis can be stated with a **small fixed** rule set without using exposed final 20% to pick parameters.

If effect is detectable but smaller than ~5× median spread in price units over the horizon → **do not advance** as tradable.

---

## 16. Conditions for reject / inconclusive

- **Reject:** mean effect opposite to H1, or indistinguishable from baseline within uncertainty, on the primary horizon.  
- **Inconclusive:** effect positive but unstable across time halves, or present on fewer than 3 instruments, or sample of non-overlapping events < 100 per major pair.  
- Negative or inconclusive results are **successful research outcomes**.

---

## 17. What will NOT be done in this study

- No trading-rule grid.  
- No parameter search over L, k, ATR windows.  
- No promotion to V53.6 or production.  
- No use of exposed final 20% for selection.

---

**Preregistration frozen. Outcome analysis must cite this file and its content hash.**
