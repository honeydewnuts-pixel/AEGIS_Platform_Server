# Data-Driven Pattern Discovery — Final Report (updated)

**Branch:** `research/data-driven-pattern-discovery-20261022`  
**Commit (prior discovery):** `9168b74c8c95e7a323b5a9c2efb469803289fd5f`  
**production_authorized=false · execution_authorized=false**

## Summary decision

**No tradeable rulebook qualifies.**

Patterns show weak same-sign conditional mean returns and large path excursions, but **mean MFE ≈ mean MAE** on validation. Net path advantage does not clear realistic round-trip costs in a way that supports strategy construction under V7 gates.

## Datasets

All **24** verified (13 Class A Bid/Ask, 11 Class B OHLC). Inventory + SHA-256 in `outputs/dataset_inventory.csv`. None excluded.

## Methods run

1. Registered binary price-structure pattern enumeration (22 patterns; no RSI/BB/MA prerequisites)
2. Conditional forward returns at horizons 3/6/12/24/48
3. Chronological 60/20/20 splits
4. Support + same-sign filters
5. Class A MFE/MAE vs 2.8-pip RT cost model on top-2 |val_mean| patterns per instrument
6. Leakage tests (5 PASS)

## Search space

2,640 pattern–horizon–instrument evaluations. Multiple-testing risk disclosed.

## Materiality findings

| Gate | Result |
|------|--------|
| Support ≥200 + same-sign + val_n≥50 | 1,837 rows |
| \|val_mean\| > 10 bps and hit > 0.55 | **0** |
| mean MFE ≥ 3× RT cost (raw) | many (misleading) |
| (mean MFE − mean MAE) > RT cost | **≈0 meaningful** |

Raw MFE/cost ratios of 6–13× appear because 48-bar path range is large in both directions. MAE is nearly equal to MFE → **no durable directional edge after costs**.

## Rulebook conversion

**Empty shortlist.** No candidate advanced to stops, exits, or cash PF.

## Three-gate qualification

Not entered. Would fail Gate 2 (net PF > 1.6) given cost realism.

## Historical test exposure

Final 20% **EXPOSED** from prior AEGIS work. Not independent confirmation.

## Next step

1. Stop expanding pattern catalogues without a pre-registered cost-aware expectancy gate of the form E[MFE−MAE] ≫ RT cost.
2. If continuing, freeze ≤3 structural hypotheses (e.g. compression→expansion) and evaluate **next-bar Bid/Ask entry** with stop at MAE-linked level — not open-ended horizon returns.
3. Do not promote any pattern from this run to a Rulebook.

## Governance

No merge to main. No V53.6 change. No trading authorization. Failed candidates retained in `pattern_outcomes.csv`.
