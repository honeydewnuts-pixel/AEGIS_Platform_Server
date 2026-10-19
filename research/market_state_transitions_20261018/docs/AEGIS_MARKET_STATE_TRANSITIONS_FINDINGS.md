# Market-State Transitions — Findings

**Preregistration hash:** `c90a055afad2b84b2d00a508e2fa04788751e15a7beda165e7d66e943e6779f7`  
**Preregistration commit:** `bed45657c9953ad3210360f76d5a02eb3a49b834`  
**Branch:** `research/market-state-transitions-20261018`  

---

## Executive decision

**RETAIN AS DESCRIPTIVE MARKET-BEHAVIOUR EVIDENCE ONLY**

The richer ELEVATED state (rv > past P80) shows a **small, stable, positive** difference in subsequent 60-minute absolute Bid displacement versus the simple baseline B_HIGH (rv > past P67) on **all 13** instruments (CI excludes 0). Materiality |diff|/median_spread ≥ 1 on **5/13** pairs.

Interpretation: a stricter high-vol cut (P80 vs P67) predicts modestly larger subsequent moves — largely a **refinement of the same volatility information**, not a new mechanism. Effect sizes are often below one median spread. **Not a basis for a trading Rulebook.**

---

## What was tested

| Item | Value |
|------|-------|
| Primary contrast | ELEVATED (P80+) vs B_HIGH (P67+) |
| Horizon | H*=12 M5 bars |
| Baseline | Expanding past-only terciles of 20-bar mean \|ΔBid\| |
| Richer states | QUIET/ORDINARY/ELEVATED + PERSIST + Q→A / A→Q |
| Development | first 60%; stability next 20%; final 20% EXPOSED |

---

## Primary results (ELEVATED vs B_HIGH)

| Metric | Value |
|--------|------:|
| Sufficient instruments | 13/13 |
| CI of diff excludes 0 | **13/13** |
| Materiality ≥ 1 | **5/13** |
| Same-sign stability | **13/13** |
| Typical materiality | ~0.2–1.9 |

Full table: `outputs/instrument_state_summary.csv`, `outputs/market_state_summary.json`.

---

## Baseline vs richer state

The simple baseline already ranks activity. ELEVATED is a **stricter subset** of B_HIGH; the residual difference is small and expected (higher recent vol → higher subsequent abs moves). Secondary contrasts (QUIET vs B_LOW, etc.) are in `baseline_vs_state_comparison.csv`.

---

## Decision vs preregistered rules

- Not CLOSE (CI excludes 0 widely)  
- Not INVALID  
- **DESCRIPTIVE_ONLY** because materiality is mixed and the effect is a vol-threshold refinement, not incremental structure beyond volatility  

No Rulebook path from this study alone.
