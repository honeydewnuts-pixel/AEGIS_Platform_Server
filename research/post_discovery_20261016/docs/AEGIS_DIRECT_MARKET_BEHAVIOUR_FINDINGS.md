# Direct Market-Behaviour Findings

**Preregistration hash:** `dd0ff932fb9617fe0a7f5acbe274d607f6aeb5176b08367734115c19ea55ced4`  
**Analysis run:** 2026-10-16  
**Development window:** first 80% of each series (final 20% EXPOSED, not used for selection)

---

## D1 — Directional persistence (H=12 primary)

| Result | Value |
|--------|-------|
| Instruments with mean signed return **> 0** | **0 / 13** |
| Mean continuation rate | **0.476** (< 0.50) |
| Mean (signed return / median spread) | **−0.25** |
| Instruments with \|mean\|/spread > 1 | **0 / 13** |
| Non-overlap robustness | Same sign (negative / sub-50% continuation) |

**Decision: REJECT H1.**  
After a ≥1×ATR move over 12 bars, subsequent 12-bar signed return is on average **against** the prior direction. Continuation probability is below a coin-flip baseline. Effect size is a fraction of one median spread — not economically useful after costs.

Stability: both halves of the development window show negative mean signed returns on nearly all pairs (USDJPY first half is a minor exception; second half negative).

---

## D2 — Volatility expansion after low-vol (H=12 primary)

| Result | Value |
|--------|-------|
| Mean ratio (future range / ATR) | ~3.92 |
| Mean ratio_vs_uncond | **0.96** |
| Instruments with ratio_vs_uncond > 1 | **3 / 13** (barely) |

**Decision: REJECT H1 / INCONCLUSIVE for tradable expansion.**  
Low-vol states do **not** produce systematically larger subsequent ranges than the unconditional baseline. The three instruments slightly above 1.0 are not a robust multi-instrument effect.

---

## Implications for trading hypotheses

- Raw M5 directional persistence after a 1×ATR impulse is **not** present in this dataset under the preregistered definition.  
- Raw M5 volatility expansion after ATR-below-median is **not** present as a general effect.  
- Therefore: **do not** build the next Rulebook family on “momentum continuation after impulse” or “compression → expansion” without a **different, more specific** state definition that is again preregistered.  
- Prior failed strategy scans (Asian→London, HTF pullback, Asian→NY) are consistent with the absence of a simple, large, cost-covering behavioural edge at these horizons.

---

## Limitations (as preregistered)

- Bid-side measurement only.  
- Overlapping events (non-overlap robustness agrees in sign).  
- Simple SE not block-bootstrap (dependence limitation disclosed).  
- Final 20% not used for confirmation.

**Negative results retained as successful research outcomes.**
