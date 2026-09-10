# AEGIS V43 — Six-COLAB Neural Intelligence Research Protocol

Version: V43.0
Status: COMPLETED — RESEARCH RESULT REJECTED FOR PRODUCTION
Instrument: GBPUSD
Source lineage: GBPUSD COLAB1.zip … COLAB6.zip
Coverage: January 2024 through August 2026

## Governance
- The six original COLAB archives are the authoritative raw-data lineage for V43.
- Existing RULEBOOK_V3 and legacy Neural V3 are preserved and are not V43.
- Frozen V31/V35 rulebooks are not altered by V43.
- Features are causal and computed only from completed bars.
- Future labels are explicitly separated from features.
- Chronological 70/15/15 train/validation/final-test split.
- Final Test is untouched for model/rule/threshold selection.
- No live execution authorization is produced by V43.

## Data transformation
1. Validate six archive SHA-256 hashes against the V38 inventory.
2. Extract monthly HistData tick CSVs.
3. Aggregate ticks into M1 Bid/Ask OHLC with tick counts.
4. Deduplicate canonical timestamps.
5. Aggregate canonical M1 into M5 Bid/Ask OHLC.
6. Construct causal feature matrix.

## Label
Three-state forward directional label at horizon 12 M5 bars:
- LONG (+1): future midpoint close >= next-bar AskOpen + 0.5 * ATR14(signal bar).
- SHORT (-1): future midpoint close <= next-bar BidOpen - 0.5 * ATR14(signal bar).
- NEUTRAL (0): neither condition; simultaneous opposite threshold crossing is conservatively neutral.

## Neural model
Two independently seeded MLP classifiers were trained and averaged:
- architecture: features -> 64 -> 32 -> 3
- ReLU activations
- Adam solver
- StandardScaler fitted on Train only
- seeds: 4301, 4302
- 40 training iterations per seed

The two-model ensemble is intentionally treated as a research ensemble, not as a production model.

## Threshold selection
Validation-only threshold sweep. A directional signal is emitted when max(P(LONG), P(SHORT)) >= threshold and the higher directional probability determines side. Candidate thresholds require >=100 resolved validation outcomes. Selection prioritizes validation precision >=55%, then PF; Final Test is not used.

## Production gate
The historical V43 research gate requires materially stronger precision/stability than observed here. V43 therefore remains RESEARCH_ONLY and cannot authorize production routing.
