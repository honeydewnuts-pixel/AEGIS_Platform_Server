# Chronological Validation Design (preregistered structure — not yet executed for PF)

**Status:** Design only. No performance optimization. No holdout peeking for parameters.

| Split | Fraction | Use |
|-------|----------|-----|
| Train | first 60% | Signal-frequency characterisation only |
| Validation | next 20% | Stability of event rates |
| Test | final 20% | **EXPOSED** in prior AEGIS phases — not independent confirmation |

Metrics when cash model exists: trade count, PF after costs, six-block PF>1, max DD — per established AEGIS gates. **Not applied in this task.**

Frozen rules are not optimized on any split.
