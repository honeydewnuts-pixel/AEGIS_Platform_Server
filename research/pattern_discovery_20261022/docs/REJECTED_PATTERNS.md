# Rejected Pattern Register

All 22 registered patterns were evaluated on all 24 instruments.

## Rejection classes
1. **Insufficient support** — development occurrences < 200
2. **Sign flip** — development and validation mean returns disagree in sign
3. **Low validation count** — val_n < 50
4. **Immaterial effect** — |val_mean| ≤ 10 bps or hit ≤ 0.55
5. **Cost-inadequate MFE** — mean favourable excursion < 3× assumed RT cost

## Aggregate
- 2640 evaluations total
- 1837 passed support+same_sign+val_n≥50 (still mostly immaterial)
- 0 passed 10bps materiality filter
- Full per-row outcomes retained in outputs/pattern_outcomes.csv
