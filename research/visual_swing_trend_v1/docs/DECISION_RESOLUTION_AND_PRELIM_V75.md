# Decision Resolution, Preliminary V75 Research — Visual Swing-Trend V1.0
**Checkpoint verified:** `96dcbb6e25c5e1fc5d1d7b03d159a55561c1ad4f`  
**Branch:** `research/visual-swing-trend-v1-20261027`  
**production_authorized=false · execution_authorized=false**

---

## 1. Checkpoint
**SOURCE-VERIFIED.** HEAD matches reported SHA. Indicator tests **7 PASS 0 FAIL** (re-run).

---

## 2. V75 dataset (preliminary — not five years)

| Field | Value | Label |
|-------|--------|--------|
| File | `/home/workdir/artifacts/VOL_CSV/V75_M5_5Y.csv` | SOURCE-VERIFIED |
| SHA256 | `1f7ce38ce9e2e172fab2a9afefb5fff561a7c1a0431317aa600910a71384f1e8` | SOURCE-VERIFIED |
| Rows | 48,000 | |
| Start–end | 2026-05-12 08:05 UTC → 2026-10-26 00:00 UTC | **~5.5 months** |
| Interval | median 5.0 min; 47999/47999 steps = 5 min | |
| Duplicates | 0 | |
| OHLC inconsistencies | 0 | |
| Bid/Ask | **None** | OHLC-only |

**Filename “5Y” is not five-year coverage.**

### M5 → M15
- Rule: `resample('15min', label='left', closed='left')`; OHLCV = first/max/min/last.
- M15 bars: **16,001**
- Spot-check aggregation high/low: **match True** (TEST-VERIFIED on sample bar).

---

## 3. Evidence for D1–D7

### D1 — OBB on RSI9 (O1) vs MA7 (O2)
| Metric | O1 (RSI9) | O2 (MA7) |
|--------|----------:|---------:|
| MA7 cross above OBB_U | **35** | **291** |
| MA7 cross above OBB_M | 524 | 521 |
| Mean \|OBB_U O1−O2\| | ~4.19 RSI points | |

**Material difference:** O2 produces ~8× more MA7/OBB_U crosses. O1 is stricter for “MA7 outside upper band.”

Screenshot shows MA7 weaving **inside** white bands with occasional upper tags — consistent with **fewer** upper crosses → **leans toward O1**, but is **not proof**.

**Status: UNRESOLVED — operator must confirm O1 or O2.**  
No freeze. Both remain documented. Provisional code default still O1 for diagnostics only, labeled provisional.

### D2 — Two-bar swing confirmation
**Accepted as provisional research definition** (causal; occurrence ≠ confirmation).

On V75 M15: **2,049** new swing-high confirms; **2,038** new swing-low confirms.

**Status: PROVISIONAL FREEZE for Phase-1 diagnostics** (not optimized on sample). Operator may veto.

### D3 — Initial signal timing
**Accepted:** first **completed** candle close when all required conditions are true; multi-candle development allowed; no unfinished candle.

**Status: ACCEPTED** for implementation of setup state machine.

### D4 — RSI swing in setup
**Provisional for SELL:** confirmed RSI9 swing high (same 2-bar rule applied to RSI series) within the active setup window.  
**BUY mirror:** confirmed RSI9 swing low.

Visual match is **INFERRED** from operator text (“RSI makes physical swing”), not pixel-measured from screenshot.

**Status: PROVISIONAL — operator may refine.**

### D5 — Pullback toward BB34 Upper (ADD_SELL)
Candidate **condition counts** (bars in BB34_U-exposed context only) — **not** complete ADD signals:

| Definition | Meaning | Count (bars) |
|------------|---------|-------------:|
| **A** | Still below BB34_U; distance to band decreased vs prior bar | 3,856 |
| **B** | High ≥ BB34_U (reach/touch) | 1,069 |
| **C** | Close > BB34_U (cross) | 581 |

No pip/%/ATR threshold invented.

**Status: UNRESOLVED — operator picks A, B, or C (or writes own).**  
ADD_SELL official events remain **BLOCKED** until D5 (+ D1) closed.

### D6 — “Substantially outside” (reversal)
**Reversal engine remains DISABLED.**

| Alt | Nature | V75 diagnostic |
|-----|--------|----------------|
| **A** | Strict outside + close vs BB34_M | BUY-side new edges **602**; SELL-side **580** (candidate bars only) |
| **B** | Outside by ≥ k×ATR | Separation when exposed: median **~0.94 ATR**, p25 **0.38**, p75 **1.77** — **k not chosen** |
| **C** | Outside + extra structure | Needs operator structure rule |

Opposite INITIAL alone does **not** reverse.

**Status: BLOCKED** pending operator choice of A / B(k=?) / C.

### D7 — BUY/SELL symmetry

| Component | Classification |
|-----------|----------------|
| Band expose / transition | Direct mirror |
| MA7 vs OBB sequence | Direct mirror |
| RSI swing high/low | Direct mirror (provisional) |
| Price higher-high / lower-low | Direct mirror |
| Initial timing (D3) | Direct mirror |
| Pullback (D5) | Mirror once D5 chosen |
| Reversal (D6) | Mirror once D6 chosen |

**Status: PROVISIONAL SYMMETRY** as starting hypothesis; no material asymmetry forced. Operator confirms.

---

## 4. Decision summary board

| ID | Status |
|----|--------|
| D1 OBB input | **UNRESOLVED** (evidence favors discussion of O1 vs O2, not silent freeze) |
| D2 Swing | **PROVISIONAL FREEZE** |
| D3 Initial timing | **ACCEPTED** |
| D4 RSI swing | **PROVISIONAL** |
| D5 Pullback | **UNRESOLVED** (A/B/C counts only) |
| D6 Substantially outside | **BLOCKED** |
| D7 Symmetry | **PROVISIONAL** |

**Official complete INITIAL / ADD / REVERSAL signal tallies: not published** as final Rulebook results.

---

## 5. Tests
```text
python3 research/visual_swing_trend_v1/tests/test_indicators_v1.py
→ 7 PASS 0 FAIL
```
Resample spot-check: **PASS** on sampled bar.

---

## 6. Preliminary findings (diagnostics, not trades)

- Short V75 sample only; **not** regime-robust performance evidence.  
- No Bid/Ask → no broker P&L.  
- Band/oscillator cross counts are **condition diagnostics**, not completed strategy signals.  
- O1 vs O2 changes ADD-related upper-cross frequency by ~8× — D1 is material.

---

## 7. Five-year V75 preparation
When longer CSV arrives: validate coverage/schema; compare overlap with current SHA `1f7ce38c…`; keep both files; re-run **frozen** rules; report preliminary vs extended **separately**; no silent overwrite; no retune on short sample first.

---

## 8. Reproducibility
- `outputs/v75_decision_diagnostics.csv`  
- `outputs/v75_m15_sample_timeline.csv`  
- Scripts/tests under `research/visual_swing_trend_v1/`

---

## 9. Safety
No production, executor, EA, broker, auth, or main-merge activity.

---

## 10. Minimum remaining operator decisions
1. **D1:** O1 or O2?  
2. **D5:** Pullback A, B, or C?  
3. **D6:** Reversal A, B with your **k**, or C?  
4. Optional confirm **D2/D4/D7** provisionals.

## 11. Next step
After D1+D5 (and D6 if reversal needed), implement approved event engine and report **official** INITIAL/ADD counts on V75 M15 and eligible FX Class A — still research-only, still no invented exits.
