# Failed Price Discovery — Findings

**Preregistration hash:** `9b545abdf7635766c75d5b13e45c9d71290f6c33e25dd016cabac28fe1ec1fc1`  
**Preregistration commit:** `4915c357d09a532849f4c15b0e153742351f5797`  
**Branch:** `research/failed-price-discovery-20261016`  
**Analysis date:** 2026-10-16  

Development sample: first 80% of each series. Final 20%: **EXPOSED** (not used for selection).

---

## Primary result (H\* = 12, de-duplicated events)

| Metric | Value |
|--------|-------|
| Instruments with n ≥ 50 | **13 / 13** |
| Instruments with mean r_signed > 0 | **12 / 13** |
| Instruments with 95% block-bootstrap CI excluding 0 (positive) | **5 / 13** |
| Instruments with \|mean\| / median_spread ≥ 1 | **0 / 13** |
| Typical continuation rate | ~0.51–0.53 |
| Typical \|mean\| / median_spread | **0.02–0.26** |

**Decision (preregistered rules): INCONCLUSIVE**

There is a mild, often positive signed return in the post-failure direction on most pairs, and five pairs show a CI that excludes zero. However, **no instrument clears the economic-relevance proxy** (|mean|/spread ≥ 1). Effect sizes are a small fraction of one median spread over one hour — not a foundation for a cost-aware Rulebook without a different design.

USDJPY shows a **negative** mean (against the hypothesis) with CI spanning zero.

---

## Interpretation

- Failed 48-bar range breaks that close back through the boundary within 12 bars are **frequent** (~11k de-duplicated events per pair in development).  
- Subsequent 12-bar Bid-path drift in the return direction is **small** relative to spread.  
- Statistical detectability on a subset of pairs ≠ economic tradability after spread, slippage, and commission.  
- **Do not promote** to a trading simulation solely on these measurement results. A separate, frozen broker-correct proposal would require a larger expected move or a different state definition, and would still need fresh confirmation data.

---

## Disclosures

- Bid-path measurement ≠ executable round-trip P&L.  
- Block bootstrap: day-clustered, 1000 resamples, seed 42.  
- Overlap policy: cooldown = 12 bars after confirmation (primary).  
- Final 20% not used for hypothesis selection.  
- Independent confirmation: **PENDING**.

Negative/inconclusive outcome retained as a valid research result.
