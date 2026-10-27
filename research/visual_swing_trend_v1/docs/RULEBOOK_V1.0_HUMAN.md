# AEGIS Visual Swing-Trend Rulebook V1.0
## Human-readable formal specification (research only)

**Version:** AEGIS_VISUAL_SWING_TREND_RULEBOOK_V1.0  
**Timeframe Phase 1:** M15  
**production_authorized=false · execution_authorized=false**

This document maps the operator’s visual MT5 logic (BB17/BB34 on price; RSI9, MA7, oscillator BB34 on the lower panel) into explicit rules.  
Labels: **DIRECT** = operator stated; **DERIVED** = mechanical without changing intent; **DECISION** = requires operator approval before freeze.

---

## 1. Indicators (DIRECT)

### Main chart
| ID | Settings |
|----|----------|
| BB17_U/M/L | Period 17, Deviation 1.0, Close, Shift 0 |
| BB34_U/M/L | Period 34, Deviation 1.0, Close, Shift 0 |

### Lower panel
| ID | Settings |
|----|----------|
| RSI9 | Period 9, Close |
| MA7 | Period 7, SMA, Shift 0, **Previous Indicator’s Data** → applied to **RSI9** (DIRECT from operator) |
| OBB_U/M/L | Period 34, Deviation **1.618**, Shift 0, **Previous Indicator’s Data** |

**DECISION — oscillator band input stream**  
MT5 “Previous Indicator’s Data” depends on indicator stack order. Competing interpretations:

| Option | OBB applied to | Implication |
|--------|----------------|-------------|
| **O1 (provisional default for research)** | **RSI9** | OBB = bands of RSI; MA7 is SMA of RSI plotted with those bands |
| **O2** | **MA7** | OBB = bands of the smoothed MA7 line |

Screenshot shows RSI (cyan), MA7 (magenta), and white bands together. Operator text: both MA7 and OBB use “Previous Indicator’s Data.”  
**Until operator confirms O1 or O2, implementation uses O1 and labels results as provisional.**

Std-dev convention for research: **population (ddof=0)** unless MT5 equivalence is verified otherwise — document any mismatch.

---

## 2. Trend context (DIRECT + DERIVED)

### Bearish context (for SELL family)
- **DIRECT:** White BB34_U is **outside above** cobalt BB17_U (exposed).  
- **DERIVED:** `BB34_U > BB17_U` (strict). Touch equality does **not** count as outside.

### Bullish context (for BUY family)
- **DERIVED mirror:** `BB34_L < BB17_L` (strict).

---

## 3. Causal swing (DERIVED — proposed freeze for Phase 1)

Operator rejects fixed 2–3 candle *requirement* but needs meaningful swings.

**Proposed Phase-1 definition (subject to operator veto):**

- A bar `p` is a **candidate swing high** if  
  `High[p] > High[p-1]` and `High[p] > High[p-2]` and `High[p] >= High[p+1]` and `High[p] >= High[p+2]`.  
- **Confirmed** only after bar `p+2` **closes**.  
- Occurrence time = close of `p`; **confirmation time** = close of `p+2`.  
- Signals may use the swing only at/after confirmation time.  
- Symmetric for swing lows with Low and `<=`.

**DECISION:** Accept this 2-bar confirmation, or specify another causal rule.

---

## 4. INITIAL_SELL (DIRECT structure; timing DERIVED)

Emit `INITIAL_SELL` at the **close** of candle `t` only when **all** are true using data available at `t`:

1. **Band transition (DIRECT):** Earlier, BB17_U was inside BB34 envelope (`BB34_L < BB17_U < BB34_U`); then at some `t_cross <= t`, BB17_U crosses **outside above** BB34_U (`BB17_U > BB34_U`).  
2. **Bearish context still valid at t:** `BB34_U > BB17_U`.  
3. **Lower panel (DIRECT sequence, multi-candle allowed):**  
   - MA7 crossed **above** OBB_M at some `t_ma <= t`.  
   - MA7 has been **between** OBB_M and OBB_U (wavering zone) during the setup window.  
   - MA7 forms a **higher low** (confirmed MA7 swing low higher than prior confirmed MA7 swing low).  
4. **RSI9 (DIRECT):** Corresponding swing on RSI9 (confirmed swing high or low per operator’s visual — **DECISION:** use confirmed RSI swing high in the same window for SELL).  
5. **Price (DIRECT):** A **temporary higher high** in price during the setup (confirmed swing high after a prior lower structure — uses §3).  
6. **No open directional SELL trade** already being managed under this Rulebook instance (adds are separate).  

**DECISION — same-candle vs multi-candle:**  
Operator allows multi-candle development. **DERIVED default:** conditions may complete on different candles; signal fires on the **first** close where **all** required conditions have occurred and remain valid.

**Not required:** Fixed 2 or 3 candle count.

---

## 5. INITIAL_BUY (DERIVED mirror)

| SELL | BUY counterpart |
|------|-----------------|
| BB17_U outside above BB34_U | BB17_L outside below BB34_L |
| BB34_U > BB17_U context | BB34_L < BB17_L context |
| MA7 cross above OBB_M; waver to OBB_U; MA7 higher low | MA7 cross below OBB_M; waver to OBB_L; MA7 lower high |
| RSI corresponding swing | RSI corresponding swing (mirror) |
| Price temporary higher high | Price temporary lower low |

**DECISION:** Confirm full symmetry is intended (no asymmetric thresholds).

---

## 6. ADD_SELL (DIRECT + DERIVED one-add-per-pullback)

While an active **SELL directional trade** exists and bearish context holds (`BB34_U > BB17_U`):

1. Price **pulls back toward** BB34_U (**DECISION:** define as price high within X of BB34_U, or close approaches from below — needs operator language).  
2. MA7 **crosses above** OBB_U.  
3. RSI9 makes a swing **outside** OBB_U (above).  
4. At qualifying candle **close** → emit **one** `ADD_SELL`.

**DERIVED — one add per distinct pullback:**  
After an ADD_SELL, ignore further OBB_U crosses until a **new pullback** is detected: e.g. price moves away from BB34_U then returns (exact distance **DECISION**), or MA7 returns below OBB_M then sets up again.

**ADD_BUY:** mirror.

**No position sizing** in this Rulebook version.

---

## 7. REVERSAL — BLOCKED until operator decision

Operator intent (DIRECT):

1. BB34 outer band **“substantially outside”** corresponding BB17 outer band.  
2. Price crosses BB34_M in the reversal direction.  
3. Close **all** legs of the current directional trade.  
4. Open opposite directional trade.

**Opposite INITIAL setup alone is NOT a reversal** (DIRECT from builder mandate).

### Alternatives (NOT chosen — operator must pick)

| ID | Definition of “substantially outside” |
|----|----------------------------------------|
| **A** | Any strict outside: e.g. SELL→BUY when `BB34_L < BB17_L` (already true by inequality) plus close > BB34_M |
| **B** | Outside by ≥ k × ATR(14); **k chosen by operator** |
| **C** | Outside + additional confirmed structure (operator defines) |

Until approved: emit **no** `CLOSE_FOR_REVERSAL` / `REVERSAL_*` events. Mark reversal tests **BLOCKED**.

---

## 8. Event types (DERIVED research model)

`INITIAL_BUY`, `INITIAL_SELL`, `ADD_BUY`, `ADD_SELL`,  
`CLOSE_FOR_REVERSAL`, `REVERSAL_BUY`, `REVERSAL_SELL` (blocked),  
`SETUP_INVALIDATED`, `SIGNAL_REJECTED`

Each event logs: instrument, timeframe, rulebook version, timestamps (setup/condition/swing confirm/signal/execution-eligible), key indicator values, accept/reject reason.

---

## 9. Explicitly out of scope (Phase 1)

Stops, targets, trails, lot size, risk %, martingale, live execution, M5 mixed results, profitability claims.

---

## 10. Operator decision checklist (must answer to freeze)

1. Oscillator BB input: **O1 (RSI9)** or **O2 (MA7)**?  
2. Accept causal swing §3 (2-bar confirm)?  
3. INITIAL multi-candle completion rule OK?  
4. RSI swing type for SELL (swing high vs other)?  
5. Pullback-to-BB34_U definition for adds?  
6. Reversal: **A / B (with k=?) / C / other**?  
7. Full BUY/SELL symmetry confirmed?

**Until then:** research may implement indicators, swings, provisional INITIAL/ADD detectors labeled **provisional**, and **must not** freeze reversal or claim final fidelity.
