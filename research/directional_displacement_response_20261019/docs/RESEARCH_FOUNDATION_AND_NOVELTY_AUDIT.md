# Phase 6 Novelty Audit — Directional Displacement / Acceptance / Rejection

**Date:** 2026-10-19  
**Branch:** `research/directional-displacement-response-20261019`  
**Base:** Phase 5 closure @ `e7904c4b87fc5b0aea817fc32801a8fdea9413d1` (Phase 5 branch tip)  
**Phase 5 authoritative closeout:** `e931f3f331ee4497e0696630f5692a46b6d2bd77`

---

## 1. What exact behaviour was already tested?

| Study | Mechanism | Primary outcome | Result |
|-------|-----------|-----------------|--------|
| **Failed price discovery** (20261016) | Prior 48-bar Bid range boundary; break; **failure = close back through boundary within 12 bars**; then signed return in return direction | H*=12 signed Bid path | INCONCLUSIVE; mild post-failure drift; **0/13** mat≥1 |
| **Volatility-shock response** (20261017) | Bar disp / 20-bar mean\|ΔBid\| ≥ 2.0; direction at bar close; matched non-shock on hour/vol/size | H*=12 direction-adjusted Bid | **D**; 3/13 weak reversal; **0/13** mat≥1 |
| **Session transitions** (20261017) | Fixed UTC session boundaries vs quiet-hour controls | H*=12 abs Bid disp | Seasonality, not transition-specific |
| **Market-state transitions** (20261018) | QUIET/ELEVATED vs baseline vol terciles on same rv | H*=12 abs Bid disp | Descriptive threshold refinement; closed as alpha path |
| Asian→London / Asian→NY / HTF+M5 pullback | Structural range / trend pullback **trading** scans | Full-cost PF gates | **0 passers** |

## 2. Overlap with the proposed Phase 6 hypothesis

Proposed Phase 6:
> After a meaningful directional displacement, behaviour depends on **acceptance beyond the boundary** vs **rejection back into the preceding area**, beyond initial size, recent vol, and time-of-day.

| Component | Failed price discovery | Proposed Phase 6 |
|-----------|------------------------|------------------|
| Pre-event reference area | 48-bar Bid high/low | “Pre-displacement reference area” |
| Displacement / break | High/Low beyond boundary | “Meaningful directional displacement” |
| Rejection / failure | Close back through boundary ≤12 bars | “Rejection back inside preceding area” |
| Acceptance | (implicit: non-failure) | “Remain/close beyond boundary for a period” |
| Classification time | After failure close | After acceptance/rejection bars complete |
| Outcome | Signed path H*=12 | Signed path H*=12 (candidate) |
| Controls | (weaker in FPD) | Size, vol, TOD — same spirit as vol-shock matching |

**Conclusion:** The proposed mechanism is a **relabelling and mild generalisation** of failed-price-discovery (rejection path) plus a symmetric “acceptance” arm. It is **not** a genuinely new economic hypothesis under M5 Bid OHLC.

## 3. Relevant earlier results

- Post-**rejection** (failed break) drift is mild and **economically weak** vs spread (FPD).  
- Post-**large move** (shock) continuation is not distinguishable from matched ordinary moves of similar size/vol/hour (vol-shock).  
- Therefore an acceptance/rejection classifier on the same price path is unlikely to produce a new, material edge without a **new information source**.

## 4. What would be genuinely new?

Something that uses information **not** already exhausted by FPD / vol-shock / session / state studies, for example:

1. **Spread-regime conditioning (recommended):** At displacement (or any fixed event) time, is contemporaneous Bid/Ask **spread** elevated or compressed relative to its own past-only distribution, and does that condition subsequent path **after** matching on size, vol, and hour?  
   - Distinct because prior studies used spread only as a materiality denominator, not as a **state variable**.  
   - Uses the true Bid/Ask property of the 13-pair dataset.  
   - Still descriptive; not liquidity depth.

2. **Cross-instrument lead-lag at session opens:** Requires simultaneous multi-pair analysis (not done).

3. **Weekend/Monday gap path:** Structural discontinuity; different event definition (gap at open), not a range-break failure.

## 5. Distinguishing evidence requirement

To claim Phase 6 as specified is distinct, one would need to show that acceptance/rejection adds information **after** matching on the exact FPD-style boundary event and on vol-shock size/hour — i.e. a nested test. That is a robustness check on FPD, not a new family.

## 6. Is OHLC sufficient for the proposed mechanism?

For pure acceptance/rejection of a price boundary: **yes, data suffice** — and that is why FPD already tested it.

For claims about liquidity, order-flow, or institutional “acceptance”: **no** — M5 OHLC cannot support those terms.

## 7. Claims that cannot be made from M5 OHLC alone

- Liquidity, depth, participation  
- Executable net P&L without broker-correct simulation  
- Independent confirmation from the exposed final 20%

---

## Novelty audit decision

**REJECT the proposed Phase 6 directional-displacement / acceptance / rejection study as currently framed.**

It substantially duplicates **failed-price-discovery** and overlaps **volatility-shock response**. Proceeding would violate the Phase 5 closure rule: future work must use a **genuinely different** economic hypothesis.

**Do not run outcome analysis** under the rejected hypothesis.

---

## Recommended alternative (for a later, separate assignment)

**Spread-regime conditioned path after displacement**

- Event: same-style displacement OR a simpler fixed bar move, classified only after bar close.  
- State: contemporaneous spread vs past-only P80/P20 of spread (past-only).  
- Question: does high-spread vs normal-spread at event time change subsequent abs or signed path after matching on move size, rv, and hour?  
- Why distinct: spread was not previously a conditioning **state**; Bid/Ask data enable it.  
- Still measurement-first; no Rulebook path without separate executable work.

This alternative is **not** started in this assignment unless separately authorised after this audit is accepted.

---

## Phase 5 status (confirmed)

CLOSED as current alpha path @ `e7904c4` (closure doc) / `e931f3f` (integrity closeout). Decision: descriptive only.
