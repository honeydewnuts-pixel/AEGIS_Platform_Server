# D1 Working Configuration, D5 Pullback Semantics, Controlled Signal-Frequency Study
**Branch:** `research/visual-swing-trend-v1-20261027`  
**Starting checkpoint (VERIFIED):** `a32b452301d5a1a699937f26b829fcd5dd83dc97`  
**production_authorized=false · execution_authorized=false**

---

## 1. Checkpoint and preservation

| Item | Result |
|------|--------|
| Branch | `research/visual-swing-trend-v1-20261027` |
| HEAD at start | `a32b452…` **SOURCE-VERIFIED** |
| Worktree | Research artifacts intact; prior reports preserved |
| Tests at start | 7 + 9 + 11 = **27 PASS / 0 FAIL** |

No restart of inventory, Rulebook, or prior evidence.

---

## 2. D1 — Working configuration

| Field | Value |
|-------|--------|
| **WORKING CONFIGURATION** | **O1** |
| **EVIDENCE STATUS** | **PROVISIONAL — SCREENSHOT-SUPPORTED** |
| Chain | Close → RSI9 → OBB(34, 1.618) on **RSI9**; MA7 = SMA(RSI9,7) plotted with it |
| O2 | Retained as labelled comparison only |

Screenshot values (SOURCE-VERIFIED image): RSI9=22.15, MA7=14.524, OBB mid/upper/lower = 28.3451 / 42.2929 / 14.3972.  
Mid−MA7 gap supports O1 over O2; **not** MT5-export source-verified.

Selection is **not** based on signal frequency or profitability.

---

## 3. D5 — One-bar-gap analysis

### Definition under test (unchanged)
Exposed BB34_U · high < BB34_U · distance (BB34_U − high) **strictly decreased** vs prior bar.

### Gap population (SOURCE-VERIFIED computed)
**635** interruptions: A true → one non-A bar → A true again, while still exposed.

**Gap reason breakdown (all 635):**

| Reason | Count |
|--------|------:|
| Distance **increased** for one bar (then decreased again) | **635** |
| B-style touch on the gap bar | 0 |
| Left exposed context | 0 |

**Interpretation:** Every split is a **one-bar pause in “getting closer”**, not a band touch and not context loss. The state machine **ends** the pullback on that bar and **starts a new episode** on the next A bar.

### Representative samples
File: `outputs/v75_d5_one_bar_gap_samples.csv`

Example `2026-05-13 10:30`:  
prior dist≈900.9 (A) → gap dist≈901.0 (not A, +0.1) → next dist≈898.7 (A).  
Tiny distance regression; **visually one continuous far approach**, machine sees **two episodes**.

Similar pattern across sampled gaps (May–Oct): small outward wobble, then resume inward.

### Can one pullback yield multiple add candidates?
Under the **current** machine: **yes** — each resumed A run after a one-bar gap is a **new** pullback start. With official ADD still disabled, no add is emitted; the **start count (1 668)** already over-segments relative to a human “one approach.”

### Reset condition
Observable: (1) not exposed, or (2) not approaching (A false).  
**Not** “next qualifying bar only” in isolation — any non-A bar ends the episode.

### Alternative interpretations (evidence-supported discussion only — **not implemented**)
| Idea | Support | Risk |
|------|---------|------|
| Treat one-bar distance regression as continuation of same approach | Matches sampled gaps (all 635 are pure dist noise) | **New rule**; not in operator text; would be inventing tolerance |
| Require N consecutive A bars to start | Reduces singletons | Invented parameter |
| End pullback only on B/C or context loss | Would merge approaches until touch | Changes semantics of A |

**No grace period or tolerance was added.** Any merge rule needs operator approval.

---

## 4. D5 — Far-field analysis

A has **no** maximum distance. Descriptive ATR buckets of A bars (not a strategy threshold):

| Distance of high below BB34_U | A bars |
|-------------------------------|-------:|
| < 0.5 ATR | 532 |
| 0.5–1 ATR | 512 |
| 1–2 ATR | 951 |
| 2–5 ATR | 1 530 |
| **≥ 5 ATR** | **331** |

Far-field sample (`outputs/v75_d5_farfield_samples.csv`): e.g. `2026-05-13 10:00` high≈31407, BB34_U≈32422, **dist≈1015 ≈ 5.3 ATR**, still classified A because distance fell vs prior.

| Assessment | |
|------------|--|
| Near-band A (<~1 ATR) | Plausibly “pullback toward the band” |
| Mid (1–2 ATR) | Ambiguous without operator chart intent |
| Far (≥5 ATR) | **Clearly inconsistent** with a visual pullback *to* BB34 Upper; it is only “less far than before” |

**Missing evidence:** Operator has not defined whether “toward” implies near-band only. **Smallest useful clarification:**  
> “Does a valid pullback require the high to be near BB34 Upper (e.g. already in the vicinity of the band), or is any move that reduces distance while below the band enough?”

No pip/ATR threshold invented here.

---

## 5. Controlled A / B / C comparison (O1, V75 M15)

| Definition | Bars | Episodes (current machine) | Median run | Max run |
|------------|-----:|---------------------------:|-----------:|--------:|
| **A** | 3 856 | **1 668** | 2 | 16 |
| **B** | 1 069 | 393 | 2 | 8 |
| **C** | 581 | 311 | 2 | 5 |

**Overlap (bars):**
- A ∩ B = **0** (mutually exclusive by construction: high < vs high ≥)
- A ∩ C = **0**
- B ∩ C = **581** → **C ⊆ B** on this OHLC sample
- A only = 3 856 · B only = 488 · C only = 0

**Segmentation effect:** A produces ~4× more episodes than B because every decreasing-distance segment counts, including far-field and post-gap resumes.

**Disagreements:** Prior B-only wick-through examples remain valid (high pierces band, close below → B not A).

**Context loss / duplicate protection:** Official ADD disabled → no official adds; diagnostic pullback starts = 1 668; duplicate_blocked stays 0 (add_emitted never set).

---

## 6. Causality and tests

| Check | Result |
|-------|--------|
| Conditions use completed-bar data only | **TEST-VERIFIED** |
| Swing occ ≠ conf | **TEST-VERIFIED** |
| Official ADD / reversal off | **TEST-VERIFIED** |
| Deterministic re-run | **TEST-VERIFIED** |
| O1 working / O2 comparison switch | **TEST-VERIFIED** |

```text
python3 …/test_indicators_v1.py      → 7 PASS
python3 …/test_signal_engine_v1.py   → 9 PASS
python3 …/test_causal_edges_v1.py    → 11 PASS
```

No official ADD or reversal enabled.

---

## 7. V75 coverage

| Field | Value |
|-------|--------|
| M5 rows | 48 000 |
| Range | 2026-05-12 → 2026-10-26 (~5.5 months) |
| M15 bars | 16 001 |
| First finite BB34_U | bar 33 (2026-05-12 16:15) |
| Bid/Ask | None |
| Config id | O1 RSI9→OBB34/1.618 |

**Limitations:** Short sample; OHLC-only; candidate counts ≠ trades; no profitability / regime claim.

---

## 8. Freeze status

| ID | Status | Notes |
|----|--------|-------|
| **D1 O1** | **WORKING CONFIGURATION** · **PROVISIONAL — SCREENSHOT-SUPPORTED** | Appropriate for preliminary research; not MT5-export verified |
| **D5** | **NOT FROZEN** | Leading A still; one-bar-gap over-segmentation + far-field ambiguity unresolved |
| Official ADD | **Disabled** | |
| D6 reversal | **BLOCKED** | |
| D2 / D4 / D7 | **PROVISIONAL** | Unchanged |
| D3 | **ACCEPTED** | Unchanged |

**Can D5 be frozen without guessing?** **No.**

---

## 9. Smallest operator inputs needed

1. **Near-band intent:** Is any decreasing distance below BB34_U enough, or must price already be near the band?  
2. **One-bar pause:** Should a single bar of increased distance still count as the **same** approach, or correctly end it?  
3. Optional: prefer **B** (touch) or **C** (close through) instead of A.

---

## 10. Explicit final answers

| Question | Answer |
|----------|--------|
| Is O1 the appropriate working configuration? | **Yes**, as **WORKING CONFIG / PROVISIONAL — SCREENSHOT-SUPPORTED**, with O2 retained for comparison. |
| Can D5 be frozen without guessing? | **No.** |
| Supporting evidence | Screenshot mid vs MA7 for O1; 635/635 gaps = distance noise; 331 A bars at ≥5 ATR far-field. |
| Unresolved | D5 near-band scope; whether to merge one-bar pauses; B/C vs A; D6. |
| Next step | Await the two clarifications above; until then keep ADD off, continue diagnostics only under O1. |

---

## 11. Status table

| Item | Label |
|------|--------|
| Checkpoint `a32b452` | **SOURCE-VERIFIED** |
| O1 working config | **PROVISIONAL — SCREENSHOT-SUPPORTED** |
| 635 gaps all dist_increased | **SOURCE-VERIFIED** (computed) |
| Far-field A ≥5 ATR (331) | **SOURCE-VERIFIED** (computed) |
| A/B/C counts & mutual exclusion | **SOURCE-VERIFIED** (computed) |
| Causal / disabled ADD tests | **TEST-VERIFIED** |
| D5 freeze | **UNRESOLVED** |
| Official ADD / reversal | **BLOCKED** (disabled) |
| Profitability / live auth | **NOT CLAIMED / false** |

**Not profitable. Not production-ready. Not authorised for live trading.**
