# D1/D5 Evidence Closure and Controlled Signal Validation
**Branch:** `research/visual-swing-trend-v1-20261027`  
**Starting checkpoint (VERIFIED):** `413c96cf05f4022079d69bb341ca68528eeedcdc`  
**Preceding:** `19ca46ba1a07875eff5f5b6f19bffcde224832cd`  
**production_authorized=false · execution_authorized=false**

---

## 1. Checkpoint and worktree

| Item | Result |
|------|--------|
| Branch | `research/visual-swing-trend-v1-20261027` |
| HEAD at start | `413c96c…` **SOURCE-VERIFIED** (matches reported) |
| Prior | `19ca46b…` present in history |
| Tests at start | indicators 7 PASS; signal_engine 9 PASS |

Artifacts preserved: Rulebook, decision register, V75 diagnostics, disagree CSV, indicator/signal scripts.

---

## 2. D1 — OBB input evidence

### Source material
- Operator screenshot present at `docs/operator_screenshot_ref.png` (copied from workspace).  
- Status line on chart (SOURCE-VERIFIED by prior image inspection):

> **RSI(9) 22.15 · MA(7) 14.524 · Bands(34) 28.3451  42.2929  14.3972**

### OBB value order
Interpretation of the three band numbers as **middle / upper / lower**:
- 28.3451 (mid) · 42.2929 (upper) · 14.3972 (lower)  
Consistent with upper > mid > lower on an RSI 0–100 scale.

### Calculation chains (research implementation)
| | O1 | O2 |
|--|----|----|
| Applied stream | RSI9 | MA7(RSI9) |
| Period / dev | 34 / 1.618 | 34 / 1.618 |
| Shift | 0 | 0 |
| Std convention | population (ddof=0) | same |
| Warm-up | ≥34 RSI bars | ≥34 after MA7 exists |

**Limitation:** Research RSI uses Wilder RMA; MT5 may differ slightly in first-seed / rounding. Exact numeric match to the screenshot bar was **not** reproduced (tick-level MT5 series not available). Structure is what is claimed.

### Why middle ≈ 28.35 supports O1
- MA7 on that bar = **14.52**.  
- OBB middle = **28.35** → gap ≈ **14 points**.  
- Under **O2** (bands of MA7), the middle band is a further smooth of MA7 and **must** track near MA7. A 14-point gap is inconsistent with O2.  
- Under **O1** (bands of RSI), middle ≈ SMA(RSI,34) while MA7 can sit near the lower band during a local RSI low — gap is expected.

### Crossing counts (descriptive only — not selection criteria)
V75 M15 (16 001 bars): MA7×OBB_U crosses **O1=35**, **O2=291**.

### D1 classification
**PROVISIONAL — SCREENSHOT-SUPPORTED (lean O1).**  
Not SOURCE-VERIFIED MT5 config export. Not settled by independent recomputation of the exact screenshot bar.  
**O2 retained** as comparison switch.  
**Recommendation:** Operator may **freeze O1** on this evidence, or supply MT5 indicator properties export to SOURCE-VERIFY.

---

## 3. D5 — Candidate A review

### Definition under test
```
A: high < BB34_U  AND  (BB34_U − high) < (BB34_U_prev − high_prev)  AND  bb34u_exposed
```
- Distance uses **candle high**.  
- Strict decrease (`<`); equal distance **excludes** A (**TEST-VERIFIED**).  
- B: high ≥ BB34_U; C: close > BB34_U (same exposed context).

### V75 M15 candidate counts (diagnostics, not trades)
| Metric | Count |
|--------|------:|
| A bars | 3 856 |
| B bars | 1 069 |
| C bars | 581 |
| A-style pullback starts (state machine) | 1 668 |
| A run length median / p90 / max | 2 / 5 / 16 |
| Singleton A runs | **706** |
| Single-bar interruption then resume (split risk) | **635** |
| Exact high==BB34_U | 0 |
| Equal-distance bars | 0 |

### Disagreement examples (from `v75_d5_disagree_examples.csv`)

**Example 1 — B only (touch/pierce high, close still below)**  
`2026-05-12 16:45`  
high=31940.49 close=31697.53 BB34_U=31704.67 → **A=False B=True C=False**  
Prior high was also above the band. This is a **wick-through** of BB34_U without close-through. Operator “approach while remaining below” would **not** count this as A; B would. Material distinction.

**Example 2 — B only, mild pierce**  
`2026-05-12 21:00`  
high=31716.18 close=31645.31 BB34_U=31700.18 → dist=−16  
Prior bar was still below (prior_dist=+25). Transition from below to high-above: **B**, not A.

**Example 3 — A-only cluster (far below, getting closer)**  
`2026-05-13 10:00`  
high=31407.38 BB34_U=32422.09 dist≈+1015 → **A=True B=False C=False**  
Price is still ~1000 points below the band but distance fell vs prior. Whether this is an “approach toward BB34 Upper” in the **visual** sense is **ambiguous** (far-field drift vs near-band pullback).

### State-machine assessment
| Concern | Finding |
|---------|---------|
| Noise split | **635** cases where A is true, false for one bar, true again while still exposed → current machine **starts a new pullback** after the gap. Risk of **multiple starts for one continuous visual approach**. |
| Merge separate pullbacks | If two approaches are separated only by non-A bars while exposed, they can be merged or split depending on interruption pattern — **no minimum separation** defined. |
| One-add-per-pullback | Infrastructure present (`add_emitted` flag) but **official ADD disabled**, so `duplicate_approaches_blocked=0` in runs (flag never set). Logic path exists; not exercised on real ADD emit. |
| Reset | Context loss (`not exposed_u`) clears state. Non-approaching bar ends pullback. |
| Causal observability | Start/end use only completed-bar high and BB34_U — causal. |

### D5 classification
**LEADING CANDIDATE A — NOT FROZEN.**  
Reasons:
1. Far-field A bars may not match “pullback toward the band” visually.  
2. One-bar noise can split one approach into multiple starts (635 instances).  
3. Operator has not confirmed A vs B vs C.

**Do not enable official ADD.**

Evidence that would freeze D5:
- Operator confirms “closer while still below using high” **and** accepts far-field approaches, **or**  
- Operator restricts A to a near-band regime **without** inventing a threshold here (operator must specify), **or**  
- Operator chooses B or C explicitly.

---

## 4. Signal-engine causal validation

| Check | Result |
|-------|--------|
| Swing occurrence ≠ confirmation | **TEST-VERIFIED** (write at p+2 only; conf > occ) |
| No early swing in first 4 bars | **TEST-VERIFIED** |
| Official ADD off | **TEST-VERIFIED** |
| Reversal off | **TEST-VERIFIED** |
| INITIAL default off | **TEST-VERIFIED** |
| O1/O2 explicit per call | **TEST-VERIFIED** |
| Deterministic re-run counts | **TEST-VERIFIED** |
| Equal distance ∉ A | **TEST-VERIFIED** |

Commands:
```text
python3 research/visual_swing_trend_v1/tests/test_indicators_v1.py   → 7 PASS
python3 research/visual_swing_trend_v1/tests/test_signal_engine_v1.py → 9 PASS
python3 research/visual_swing_trend_v1/tests/test_causal_edges_v1.py  → 11 PASS
```
**Total: 27 PASS / 0 FAIL**

---

## 5. V75 coverage and limits

| Field | Value |
|-------|--------|
| File | `VOL_CSV/V75_M5_5Y.csv` |
| M5 rows | 48 000 |
| Range | 2026-05-12 08:05 → 2026-10-26 00:00 UTC (**~5.5 months**) |
| M15 bars | 16 001 |
| Bid/Ask | **None** |
| Filename “5Y” | **Not** five-year coverage |

Insufficient for profitability, regime stability, or broker-realistic P&L.

---

## 6. Status of other decisions (unchanged)

| ID | Status |
|----|--------|
| D2 two-bar swing | PROVISIONAL |
| D3 first completed close | **ACCEPTED** |
| D4 RSI swing high/low | PROVISIONAL |
| D6 substantially outside | **BLOCKED** (reversal disabled) |
| D7 symmetry | PROVISIONAL |

---

## 7. Freeze readiness

| Decision | Ready to freeze? | Recommendation |
|----------|------------------|----------------|
| **D1 = O1** | **Conditionally yes** | Freeze as **PROVISIONAL—SCREENSHOT-SUPPORTED O1** if operator agrees; else supply MT5 config |
| **D5 = A** | **No** | Keep **LEADING CANDIDATE — NOT FROZEN**; resolve noise-split + far-field intent first |
| Official ADD | **No** | Remains disabled |
| Reversal | **No** | Remains BLOCKED |

---

## 8. Remaining operator actions
1. Confirm **D1 → O1** (or reject and specify O2 / export MT5 settings).  
2. Confirm **D5**: accept A as-is, restrict A, or choose B/C; comment on far-field approaches and one-bar gaps.  
3. D6: leave off or define A/B(k)/C.  

---

## 9. Next step
After D1 confirmation: keep O1 as default in frozen config.  
After D5 confirmation: only then enable official ADD path and report **signal** counts (still not P&L).  
Continue research-only; no production actions.

---

## 10. Status table

| Item | Label |
|------|--------|
| Checkpoint `413c96c` | **SOURCE-VERIFIED** |
| Screenshot status values | **SOURCE-VERIFIED** (image) |
| D1 lean O1 | **PROVISIONAL — SCREENSHOT-SUPPORTED** |
| Exact MT5 OBB chain export | **UNVERIFIED** |
| D5 A definition fidelity | **LEADING CANDIDATE — NOT FROZEN** |
| D5 noise-split risk (635) | **SOURCE-VERIFIED** (computed) |
| Swing causal timing | **TEST-VERIFIED** |
| Official ADD disabled | **TEST-VERIFIED** |
| Reversal disabled | **TEST-VERIFIED / BLOCKED** |
| V75 ~5.5 months OHLC | **SOURCE-VERIFIED** |
| Profitability / broker P&L | **NOT CLAIMED** |
| Production / live auth | **BLOCKED (false)** |

**Not profitable. Not production-ready. Not authorised for live trading.**
