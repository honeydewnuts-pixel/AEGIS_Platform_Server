# Final Decision Review and M15 Signal-Engine Preparation
**Branch:** `research/visual-swing-trend-v1-20261027`  
**Base commit verified:** `19ca46ba1a07875eff5f5b6f19bffcde224832cd`  
**production_authorized=false · execution_authorized=false**

---

## 1. Checkpoint and artifacts
**SOURCE-VERIFIED.** Continued from existing inventory, indicators, V75 diagnostics.  
New: `scripts/signal_engine_v1.py`, `tests/test_signal_engine_v1.py`, D5 disagree examples, this report.

Tests:
```text
test_indicators_v1.py  → 7 PASS 0 FAIL
test_signal_engine_v1.py → 9 PASS 0 FAIL
```

---

## 2. D1 — Oscillator Bollinger input (screenshot-based)

### Indicator chains
| | O1 | O2 |
|--|----|----|
| Chain | Close → RSI9 → MA7(RSI9); **OBB(34,1.618) on RSI9** | Close → RSI9 → MA7(RSI9); **OBB(34,1.618) on MA7** |
| White bands surround | RSI stream | MA7 stream |
| Middle band should track | SMA(RSI9,34) | SMA(MA7,34) ≈ slow RSI |

### Screenshot evidence (SOURCE-VERIFIED image inspection)
Lower-panel status line on operator chart:

> **RSI(9) 22.15  MA(7) 14.524  Bands(34) 28.3451  42.2929  14.3972**

- Band **middle = 28.35**, **MA7 = 14.52** → gap ≈ 14 points.  
- If OBB were applied to MA7 (O2), the middle band must stay near the MA7 level (further smoothed). A 14-point gap is inconsistent with O2.  
- Gap is natural under **O1** (bands of volatile RSI; MA7 can sit near the lower band while mid reflects broader RSI average).

### Crossing behaviour (V75 M15, 16 001 bars)
| | O1 | O2 |
|--|---:|---:|
| MA7 cross above OBB_U | **35** | **291** |
| MA7 cross above OBB_M | 524 | 521 |

O2 is far more permissive on upper-band tags.

### Conclusion on D1
**INFERRED from screenshot values → strong support for O1.**  
Not a profitability argument.  
**Recommendation:** freeze **O1** unless the operator states the MT5 stack uses BB on MA explicitly.

**Status after this review:** **PROVISIONAL FREEZE ON O1** (operator may veto). O2 remains available as a switch for comparison only.

---

## 3. D5 — ADD_SELL pullback (A leading candidate)

### Definitions (no pip/%/ATR threshold)
| ID | Mathematical condition (exposed BB34_U context) |
|----|--------------------------------------------------|
| **A** | `high[t] < BB34_U[t]` **and** `(BB34_U[t] − high[t]) < (BB34_U[t−1] − high[t−1])` (closer while still below) |
| **B** | `high[t] ≥ BB34_U[t]` |
| **C** | `close[t] > BB34_U[t]` |

Price measure for A: **candle high** vs BB34_U.  
Must remain **below** the band for A.  
Pullback **begins** on first A bar after non-A (or after trend re-assert).  
Pullback **ends** when A ceases (distance increases / leaves approach) or context lost.  
**One-add-per-pullback:** after a qualifying add in a pullback, further A bars in the **same** pullback are suppressed (state machine implemented; official ADD still disabled).

### V75 M15 candidate bar counts (not complete ADD signals)
| | Count |
|--|------:|
| A bars | 3 856 |
| B bars | 1 069 |
| C bars | 581 |
| Distinct A-style pullback starts (state machine) | 1 668 |

### Disagreement examples
File: `outputs/v75_d5_disagree_examples.csv`  
Typical case: high pierces BB34_U (B true) while close stays below (C false) and A false — A and B disagree on “touch without close-through.”

### Conclusion on D5
A matches “approaches … while remaining below” language best.  
**Status: PROVISIONAL LEADING CANDIDATE A — still needs operator confirmation before official ADD_SELL.**  
B and C retained as comparisons. Official ADD path **disabled** in engine.

---

## 4. D2, D4, D7 — provisional (unchanged policy)
- **D2** two-bar causal swing: PROVISIONAL FREEZE; occurrence ≠ confirmation timestamps recorded separately in design.  
- **D4** RSI swing high (SELL) / low (BUY): PROVISIONAL.  
- **D7** symmetry: PROVISIONAL mirror hypothesis.  
No tuning on V75 counts.

---

## 5. D6 — Reversal **BLOCKED**
Alternatives A/B/C preserved; no ATR multiplier invented; opposite INITIAL alone is not a reversal.  
Engine: `reversal_enabled=False`; no CLOSE_FOR_REVERSAL / REVERSAL_* events emitted (**TEST-VERIFIED**).

---

## 6. Signal-engine preparation (what is implemented)
| Component | Status |
|-----------|--------|
| Indicators O1/O2 switch | Done |
| Causal swings | Done |
| Multi-candle setup scaffolding | Done (INITIAL official emit off) |
| First-valid-close timing rule | Accepted (D3) |
| Pullback state + duplicate suppression | Done (diagnostics) |
| Event log types + rejection hooks | Done |
| Official INITIAL / ADD / REVERSAL | **Disabled** until freezes |
| Stops / sizing / Bid-Ask P&L | Out of scope |

---

## 7. Preliminary V75 findings
- Coverage: 2026-05-12 → 2026-10-26 only; **not** five years.  
- OHLC only → no broker-realistic P&L.  
- Diagnostics ≠ completed Rulebook trades.  
- Screenshot window present in sample (289 M15 bars 23–26 Oct).

---

## 8. Remaining operator decisions (minimum)
1. **Confirm D1 = O1** (or insist O2).  
2. **Confirm D5 = A** (or pick B/C / write own).  
3. **D6:** leave reversal off, or choose A / B with **your k** / C.  
4. Optional: confirm D2/D4/D7 provisionals.

---

## 9. Safety
No production deployment, DB/migration/queue changes, broker orders, EA/VPS changes, auth elevation, or merge to main.

---

## 10. Next recommended action
1. Operator confirms **D1=O1** and **D5=A** (or states alternatives).  
2. Builder enables official INITIAL + ADD paths under those freezes.  
3. Report official signal frequencies on V75 M15 and eligible FX Class A.  
4. Keep reversal off until D6 is explicit.  
5. Ingest five-year V75 later without rewriting frozen rules.

**Not profitable. Not production-ready. Not authorised for live trading.**
