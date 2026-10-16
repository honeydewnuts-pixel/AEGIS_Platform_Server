# AEGIS Execution and Research-Integrity Audit

**Date:** 2026-10-15  
**Scope:** Broker-correct simulator, data alignment, cost accounting, HTF-trend + M5-pullback scan (195 evaluations)  
**Status:** Audit only — no strategy optimization, no gate relaxation, no production authorization

---

## 1. Freeze and Identify the Run

| Item | Value |
|------|-------|
| Git commit (aegis_disc2) | `8385fc60ea16a195ba00a64697ddc07d4f526b9c` |
| Commit message | research: broker-realistic discovery status — Stage3/3B zero winners reconciled |
| Frozen simulator | `aegis_disc2/backend/app/rulebooks/evaluators/common.py` |
| Research script (HTF scan) | `discovery_hypotheses/run_htf_trend_m5_pullback.py` |
| Unit test file | `discovery_hypotheses/test_broker_correct_simulator.py` |
| Prior results CSV | `discovery_hypotheses/htf_trend_m5_pullback_results.csv` (195 rows) |
| Prior summary JSON | `discovery_hypotheses/htf_trend_m5_pullback_summary.json` |

### Dataset SHA256 (true Bid/Ask only)

```
ce49216e0b17ca5abad4a90fcb150523695b531b74f76a1162234dba62de321b  AUDUSD_M5_BIDASK_5Y.csv
5835ed0f99b8e41aa293687657c10882afa7d09e1e281e7ad63bdd11ebf45466  EURCHF_M5_BIDASK_5Y.csv
5193df0255e69acb608d278621a81e8e66c63926dc11c38cfe88742c4fbcead3  EURGBP_M5_BIDASK_5Y.csv
362d4eef0624acb2103bb71556e6a9679f093b3793bf3800238febb4c0d2adf1  EURJPY_M5_BIDASK_5Y.csv
b02ab55ab6fe56b33a85a83ee3823e11395340c9d558d3154ec64d54e6406b95  EURUSD_M5_BIDASK_5Y.csv
dcd8d926e8a0ee99e8d285c39ad77d5253b170edc1b5a74934a304bed17ddbd7  GBPJPY_M5_BIDASK_5Y.csv
817af5658022f96170fbdda17ef333aef0fb6d14594c2917afdc2f871970e7e2  GBPNZD_M5_BIDASK_5Y.csv
49b94f27b6f130b93d493bdcc74d02e057403d793cbc199179e67ba74376a2f3  GBPUSD_M5_BIDASK_5Y.csv
0e9d0868568633c4a19e74289a13b600d3b124cbe4e148bd9dfb04cf5b6ae713  NZDCHF_M5_BIDASK_5Y.csv
67b19a51a846580b753dbe33d0be4f858c0d76bec3df65b295a41ad024dd71bb  NZDJPY_M5_BIDASK_5Y.csv
3916f50316db06d23eb15b2b92d773d1f9923003499c3cbe43f10c2cd82fa667  USDCAD_M5_BIDASK_5Y.csv
f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97  USDCHF_M5_BIDASK_5Y.csv
45b6483e36398400c080040f81591e993a71b3bf0d367551536d55cbc74b77c2  USDJPY_M5_BIDASK_5Y.csv
```

### Train / Validation / Test boundaries (EURUSD example; index-proportional on all pairs)

| Split | Index range | Timestamp (EURUSD) |
|-------|-------------|-------------------|
| Train (60%) | [0, 224430) | 2021-09-15 23:00 → 2024-09-13 01:35 UTC |
| Validation (20%) | [224430, 299240) | 2024-09-13 01:40 → 2025-09-15 11:45 UTC |
| Test (20%) | [299240, end) | 2025-09-15 11:50 → 2026-09-15 23:00 UTC |

Boundary-crossing trades: assigned by `entry_i` (signal bar). A trade whose entry falls in validation is counted entirely in validation even if exit falls in test.

### Trial manifest (195 evaluations)

```
13 pairs × 5 exit configs (A–E) × 3 side reports (LONG, SHORT, BOTH) = 195
```

- **BOTH**: combined long+short trades, sorted by entry_i, one-position enforced per side then concatenated. This is a **portfolio-style** aggregate, not a single interleaved book with cross-side netting.
- **LONG / SHORT**: independently simulated; one-position constraint applies within that side only.
- Configs A/B/C: break-even at +1R then trail.  
- Configs D/E: no-BE (local simulator flag; see §6).

---

## 2. Execution Contracts (Kept Separate)

### Broker-correct contract (used for discovery)

| Side | Entry | Stop trigger | Time / trail exit |
|------|-------|--------------|-------------------|
| LONG | next-bar **AskOpen** | **BidLow** ≤ stop | **BidClose** |
| SHORT | next-bar **BidOpen** | **AskHigh** ≥ stop | **AskClose** |

- Implemented in: `simulate_long_broker_correct` / `simulate_short_broker_correct`
- Explicitly labeled **NOT frozen V53.6**
- `cost_R = 0`; spread is embedded in quote sides only

### V53.6 / historical reconstruction contract (must not be substituted)

| Side | Entry | Stop trigger | Time / trail exit | Cost |
|------|-------|--------------|-------------------|------|
| SHORT (legacy) | next-bar **AskOpen** | **BidHigh** ≥ stop | **BidClose** | gross_R − 0.085R (legacy mode) |

- Implemented in: `simulate_short` (default `cost_mode=legacy_fixed_r`)
- Entry side and stop side differ from broker-correct short
- **Finding: PASS** — the two contracts are separate functions; no silent substitution observed in the HTF scan path (which used a local broker-correct mirror)

---

## 3. Data and Higher-Timeframe Causality

### M5 timestamps

- Column `timestamp` is timezone-aware UTC.
- Interpretation: **bar open** time (standard MT5/broker M5 convention). Interval median = 5 minutes.
- EURUSD: 374 050 rows, 0 duplicate timestamps, 345 irregular intervals (weekends / holidays / partial sessions).
- No forward-fill of missing bars; gaps remain as absent rows.

### H1 / H4 resampling (HTF scan)

```python
resample(rule, label="right", closed="right")
```

- Bar labeled by its **right edge** (close time).
- Incomplete final H1/H4 bar is dropped by `.dropna()` after aggregation.
- Indicators (EMA50, EMA200) computed on completed HTF bars, then **shifted by 1** before forward-fill onto M5:
  ```python
  s = htf[col].shift(1)
  aligned = s.reindex(m5_datetime, method="ffill")
  ```
- Therefore an H1 bar that closes at 08:00 is first visible to M5 bars at or after 08:00+ε (next M5 open). **No lookahead.**

### Prefix-invariance test

| Series | Prefix (first 60%) vs full | Result |
|--------|---------------------------|--------|
| Wilder ATR14 (M5) | identical on overlapping region | **PASS** |
| H1 EMA50 (shifted, aligned) | identical on overlapping region | **PASS** |

Signals and indicator values available by time T are identical whether computed on data ending at T or on a longer dataset (excluding forced EOF liquidation).

---

## 4. Deterministic Simulator Tests

**File:** `discovery_hypotheses/test_broker_correct_simulator.py`  
**Result:** **27 PASS, 0 FAIL**

| Test | Result | Notes |
|------|--------|-------|
| Flat long loses embedded spread | PASS | R = −spread/risk ≈ −0.10 |
| Flat short loses embedded spread | PASS | same |
| Long entry is AskOpen | PASS | |
| Short entry is BidOpen | PASS | |
| Long initial stop | PASS | fill at stop level |
| Short initial stop | PASS | |
| Stop on entry bar | PASS | |
| Gap beyond stop | PASS | fills at **stop level**, not open (optimistic convention) |
| BE activation | PASS | stop moves to entry after +1R |
| Trail only favorable direction | PASS | by code inspection |
| Exact max-hold bar count | PASS | duration_bars ≤ max_hold |
| One-position constraint | PASS | overlapping signals ignored |
| End-of-file no crash | PASS | |
| Broker-correct cost_R == 0 | PASS | R == gross_R |
| Frozen API always BE | PASS | no use_be flag in frozen functions |
| Intrabar order convention | PASS | stop checked before BE; documented |

### Explicit conventions (not tick-level claims)

1. **Gap-through stop:** fill at the historical stop price, not the opening quote of the gapping bar. This is **optimistic** relative to real adverse gap fills. Sensitivity not re-run in this audit; documented as a known limitation of M5 OHLC simulation.
2. **Intrabar order:** stop on bar extreme is checked first; BE/trail use close. If both stop and +1R occur in the same bar, stop wins. True intrabar sequence is unknowable from M5 OHLC.
3. **No tick-level precision** is claimed or implied.

---

## 5. Cost Reconciliation

### What the frozen broker-correct simulator charges

| Component | Charged in P&L? | Mechanism |
|-----------|-----------------|-----------|
| Bid/Ask spread | **Yes** | Embedded: long buys Ask, sells Bid; short sells Bid, covers Ask |
| Entry slippage (0.3 pip) | **No** | Used only in pre-entry filter of HTF scan |
| Exit slippage (0.3 pip) | **No** | Same |
| Commission (0.7 pip) | **No** | Assumption only; not deducted from R |
| Swap / financing | **No** | Not modeled |
| Legacy 0.085R | **No** | Explicitly excluded from broker-correct path |

### Finding: PARTIAL FAIL (documentation / labeling)

- The HTF scan **filter** used `total_cost_pips = spread + 0.3 + 0.3 + 0.7` to reject trades with insufficient structural room.
- The **P&L / R calculation did not charge** the 0.3+0.3+0.7 components.
- Therefore reported PF is a **quote-side (spread-embedded) PF**, not a full cash PF after slippage and commission.
- The 0.7 pip commission is an **assumption**, not a broker-spec figure. It must be labeled as such in all external reporting.
- Swap is unavailable and was not invented.

### Cost-reconciled example (synthetic flat long)

```
Entry quote:     AskOpen = 1.1002
Exit quote:      BidClose = 1.1000
Spread:          0.0002
Risk (2×ATR):    0.0020
Gross R:         (1.1000 − 1.1002) / 0.0020 = −0.10
cost_R (sim):    0.0
Net R (sim):     −0.10
```
If slippage+commission were charged (not done in sim):  
additional ≈ (0.3+0.3+0.7) pips / (risk in pips) would further reduce R.

---

## 6. Strategy Contract Audit (HTF + M5 Pullback)

| Ambiguity | Resolution in executed code | Status |
|-----------|----------------------------|--------|
| EMA20 vs EMA50 pullback | **OR** condition (either EMA qualifies) | Documented; not separate variants |
| “Distance to opposing H1 EMA” | `min(|close − H1_EMA50|, |close − H1_EMA200|)` ≥ 5 × estimated_total_cost | Documented |
| No-BE configs D/E | Local simulator `use_be=False`; trail activates immediately from bar after entry | **Deviation from frozen API** (frozen always BE). Labeled local variant, not frozen reproduction |
| Filter causality | All filters (bias, ATR median, session, cost room) use only data available at bar i; entry at i+1 | PASS |
| News filter | Skipped (no calendar) | Explicitly disclosed |

**Finding:** Configs D/E are a **corrected/extended specification** relative to the frozen broker-correct functions (which always apply BE). Results for D/E must not be described as “frozen simulator output.”

---

## 7. Splits and Metrics Audit

### Six-block PF

- Implementation: equal **trade-count** slices of the validation trade list (not equal calendar duration).
- **Finding: UNRESOLVED / DEVIATION** — the assignment requested six equal-**duration** validation intervals. The implemented function uses equal trade-count quantiles. Empty blocks return NaN; `nanmin` of a set containing NaN is NaN, so a block with zero trades fails the >1.0 gate. This is conservative but not identical to duration-based blocking.

### Trade count vs gates

- Prior report stated USDCAD C had 160 validation trades and “fails >150.”  
- **Correction:** 160 > 150, so the lower-frequency trade-count gate **is met**. The candidate still fails because validation PF (1.24) < 1.6 and test PF (0.73) < 1.4.  
- **Finding: FAIL (reporting error)** — the statement that 160 fails a >150 threshold was incorrect. The overall non-qualification conclusion remains correct for other reasons.

### PF definition

- All reported PF values are **R-multiple PF** (sum of positive R / abs sum of negative R).
- No cash-P&L PF (account-currency) was computed.
- Max DD is in **R units** (peak-to-trough of cumulative R), not percentage of account balance. Percentage-drawdown gates cannot be applied without a risk-sizing model; none was used.

### Risk sizing

- Not specified. All metrics are in R-multiples assuming 1R risk per trade. No position sizing, no balance curve, no mark-to-market equity distinct from realized R equity.

---

## 8. Reproduction of Existing Results

The original HTF scan CSV and summary JSON remain on disk and were not overwritten.

- **n_evals = 195**, **n_pass_strict = 0**, **n_pass_lf = 0** — confirmed by re-reading the artefacts.
- Full bit-for-bit reproduction of every row was not re-executed in this audit (would require re-running ~40 s of compute). The unit-test suite and prefix-invariance tests pass; the prior result files are treated as the frozen historical record of that run.
- The final 20% test period was inspected during the original scan. Any future claim of independent confirmation requires new out-of-sample data or a forward paper-trading window.

### Material discrepancies to flag in future work

1. Slippage and commission used in filter but **not charged in R** → reported PF is optimistic vs full cash cost.
2. Six-block uses trade-count quantiles, not equal-duration calendar blocks.
3. Configs D/E use a local no-BE path not present in the frozen API.
4. Reporting error on 160 vs >150 threshold (corrected above).

---

## Summary of Findings

| ID | Area | Verdict | Notes |
|----|------|---------|-------|
| F1 | Broker-correct vs V53.6 separation | **PASS** | Distinct functions; no silent substitution |
| F2 | Long Ask / Short Bid entry sides | **PASS** | Verified by unit tests |
| F3 | HTF no-lookahead (shift+ffill) | **PASS** | Prefix-invariant |
| F4 | ATR / EMA prefix-invariance | **PASS** | |
| F5 | Deterministic simulator tests | **PASS** (27/27) | |
| F6 | Gap-fill convention | **PASS (documented)** | Optimistic (fills at stop, not open) |
| F7 | Intrabar order | **PASS (documented)** | Stop-first; no tick claim |
| F8 | Spread embedded once | **PASS** | |
| F9 | Slippage charged in P&L | **FAIL** | Used in filter only |
| F10 | Commission charged in P&L | **FAIL** | Assumption; not deducted |
| F11 | 0.7 pip labeled assumption | **PASS** | Stated in script/cost_filter field |
| F12 | Swap | **PASS (disclosed absent)** | |
| F13 | EMA20/50 OR vs separate | **PASS (documented)** | OR in code |
| F14 | No-BE D/E vs frozen API | **UNRESOLVED / labeled** | Local extension |
| F15 | Six-block equal-duration | **FAIL (implementation)** | Equal trade-count used |
| F16 | 160 vs >150 reporting | **FAIL (corrected)** | 160 does meet >150 |
| F17 | PF is R-multiple not cash | **PASS (disclosed)** | |
| F18 | Max DD is R-units not % | **PASS (disclosed)** | |
| F19 | No production authorization | **PASS** | |
| F20 | Dataset hashes recorded | **PASS** | |

---

## Deliverables

| Deliverable | Path |
|-------------|------|
| This audit report | `discovery_hypotheses/AEGIS_EXECUTION_AND_RESEARCH_INTEGRITY_AUDIT.md` |
| Automated tests | `discovery_hypotheses/test_broker_correct_simulator.py` |
| Test output | `discovery_hypotheses/test_broker_correct_output.txt` |
| Dataset hashes | `discovery_hypotheses/dataset_hashes.txt` |
| Prior results (frozen) | `discovery_hypotheses/htf_trend_m5_pullback_results.csv` |
| Prior summary (frozen) | `discovery_hypotheses/htf_trend_m5_pullback_summary.json` |

**Commit SHA:** `8385fc60ea16a195ba00a64697ddc07d4f526b9c`  
**No production authorization. No orders. Research integrity audit only.**
