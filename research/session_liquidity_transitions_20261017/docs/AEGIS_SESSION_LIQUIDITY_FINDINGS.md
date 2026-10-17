# Session Liquidity Transitions — Findings

**Preregistration hash:** `bfea37d1411c07d6ed8113a1e1dfac5a02346ba6620b641fa972d881cddf07a3`  
**Preregistration commit:** `966214a261d2a15e0c9fa6b4335b3c5c3babde23`  
**Branch:** `research/session-liquidity-transitions-20261017`  
**Analysis date:** 2026-10-17  

---

## Executive decision

**RETAIN AS BEHAVIOURAL / SEASONALITY FINDING — DO NOT AUTHORISE TRADING EXPERIMENT.**

Against quiet-hour controls (03:00 and 15:00 UTC), London-open (07:00) absolute 60-minute Bid displacement is larger on 11/13 instruments with CI of the difference above 0, and materiality (mean abs disp / median spread) ≥ 2 on all 13.

**However:** the same elevation appears at **NY open (12:00)** with median ratio **1.37**, nearly identical to London-open median ratio **1.35**. That pattern is the signature of **ordinary intraday seasonality** (quiet Asian hours vs active London/NY hours), not a London-open *transition-specific* effect under Baseline 1 as intended.

**Outcome classification (preregistered labels):** numerically meets **F** against the chosen quiet controls, but substantive interpretation is **B — apparent effect explained by intraday seasonality** when T2 is compared. Therefore **no separate executable trading proposal is authorised**.

This is **not** a measurement of liquidity (no volume/depth data).

---

## What was tested

| Item | Value |
|------|-------|
| Primary transition | T1 London open 07:00 UTC |
| Primary horizon | H*=12 M5 bars (60 min) |
| Primary metric | mean \|Δ BidClose\| vs controls at 03:00 & 15:00 UTC |
| Instruments | 13 Bid/Ask pairs |
| Development | first 80% of each series |
| Final 20% | EXPOSED — not used for selection |

---

## Primary results (T1, H=12)

| Symbol | n_event | ratio vs control | CI(diff)>0 | materiality |
|--------|--------:|-----------------:|:----------:|------------:|
| AUDUSD | 1041 | 1.07 | no | 6.9 |
| EURCHF | 1040 | 1.76 | yes | 7.7 |
| EURGBP | 1041 | 1.58 | yes | 7.0 |
| EURJPY | 1041 | 1.46 | yes | 16.5 |
| EURUSD | 1041 | 1.39 | yes | 34.3 |
| GBPJPY | 1041 | 1.40 | yes | 10.4 |
| GBPNZD | 1038 | 1.30 | yes | 3.7 |
| GBPUSD | 1041 | 1.32 | yes | 13.8 |
| NZDCHF | 1039 | 1.35 | yes | 3.6 |
| NZDJPY | 1040 | 1.22 | yes | 9.7 |
| USDCAD | 1041 | 1.01 | no | 6.5 |
| USDCHF | 1040 | 1.45 | yes | 9.2 |
| USDJPY | 1041 | 1.25 | yes | 24.7 |

Median T1 ratio ≈ **1.35**; median T2 (NY open) ratio ≈ **1.37**.

---

## Gate table

| Research gate | Required evidence | Result | Status |
|---------------|-------------------|--------|--------|
| Prereg before outcomes | Commit precedes analysis | 966214a before run | PASS |
| Timestamp convention | Documented UTC assumption | CSV +00:00; local DST not modelled in primary | PASS (with limitation) |
| Primary effect vs quiet controls | CI diff > 0 on ≥5 instruments | 11/13 | PASS (vs chosen controls) |
| Not only seasonality | T1 distinct from other active hours | T2 ratio ≈ T1 ratio | **FAIL** |
| Chronological stability | Both halves ratio > 1 | 13/13 | PASS |
| Cross-instrument | ≥5 instruments | 13 | PASS |
| Economic materiality | median mat ≥ 2 | all ≥ 2 vs spread | PASS (descriptive) |
| Liquidity mechanism | Volume/depth | **Unavailable** | NOT TESTED |
| Executable P&L | Broker-correct simulation | **Not performed** | NOT TESTED |
| Rulebook promotion | — | — | **NOT AUTHORISED** |

---

## Interpretation

Larger absolute moves after 07:00 UTC than after 03:00/15:00 are real in this sample but **consistent with the known active London session**, not evidence of a special *transition* shock beyond “the day got busy.” A trading hypothesis built only on “trade London open because displacement is large” would be optimising known seasonality and still requires full-cost executable simulation (not done here).

---

## Recommended next action

**CLOSE the tested session-transition hypothesis as a path to a Rulebook under this specification**, or retain only as a **behavioural seasonality description**.

Do **not** start an executable strategy grid from these results.

If future work continues, it must preregister controls that contrast **transition minutes vs adjacent active-session minutes** (not vs Asian quiet hours), and still cannot claim liquidity without volume/depth data.

---

## Governance

- V53.6 unchanged; production_authorized unchanged; no orders; no promotion.  
- Bid displacement ≠ trading P&L.  
- Independent confirmation PENDING (exposed final period).
