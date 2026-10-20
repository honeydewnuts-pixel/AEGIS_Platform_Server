# AEGIS_DBT_RSI_REVERSAL_V1 — Research Specification

**Research ID:** AEGIS_DBT_RSI_REVERSAL_V1  
**Branch:** research/dbt-rsi-reversal-v1-20261020  
**Base commit:** 21839708e614c3a20105a4c3d58566690bfb0701  
**Authorization:** research only — production_authorized=false, execution_authorized=false  

---

## Indicator stack (exact)

### Main chart (price Close)
| Indicator | Period | Dev | Shift | Applied |
|-----------|--------|-----|-------|---------|
| BB34 | 34 | 1.000 | 0 | Close |
| BB17 | 17 | 1.000 | 0 | Close |

SMA of Close ± k * sample stdev of Close over period (population/sample: **sample stdev, ddof=1** — documented convention).

### Lower panel
| Indicator | Spec |
|-----------|------|
| RSI9 | Period 9, Close, Wilder smoothing |
| RSI_MA7 | SMA(7) of RSI9 |
| RBB | BB period 34, dev 1.618 on RSI9 series |
| WPR60 | Williams %R period 60 on High/Low/Close |

---

## PROVISIONAL_SWING_DEFINITION (RSI9)

**Not operator-final.** Labelled provisional for engineering/tests.

- Left bars L=2, right bars R=2  
- Swing low at index i: RSI9[i] ≤ RSI9[i−k] for k=1..L and RSI9[i] < RSI9[i+k] for k=1..R  
- Swing high: mirror with ≥ / >  
- Confirmation time = i+R (first bar when right side is complete)  
- Actionable only at close of confirmation bar  
- Minimum swing size: none beyond strict inequality (provisional)

Eligibility uses RSI at **swing extreme** candle for band position; signal time = confirmation close.

---

## Unresolved specification register

1. Exact RSI swing L/R and minimum size — **PROVISIONAL** above  
2. Structural reversal: definition of required higher-high/lower-low sequence and max bars after B17_M/B34_M cross  
3. Full stop / TP / trail / sizing for net-profitability test  

---

## Design locks (operator confirmed)

- M5 only  
- Early RSI reversal independent of main-chart weakening  
- MA7/WPR60 not mandatory for reversal in base model  
- Long and short both implemented  
- Retracement ≠ automatic reversal  

---

## Governance

Do not promote to production. Do not set production_authorized=true.
