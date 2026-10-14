# Data Quality and Limitations

**Date:** 2026-10-14

## Hashes

| Artifact | SHA-256 / note |
|----------|----------------|
| USDCHF_M5_BIDASK_5Y.csv (manifest) | f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97 |
| File in current Git clone | **ABSENT** |

## Timestamp defects

- Prior audit: 484 gaps &gt; 5 minutes on USDCHF M5 series.  
- Re-audit: **blocked** without file.

## Price-side authenticity

- Manifest labels dataset Bid/Ask.  
- Without file bytes, authenticity cannot be re-verified in this session.

## Broker specifications missing

- Account-specific commission, swap, freeze level, min stop distance: **not verified**.

## Impact on conclusions

- Cannot claim new broker-realistic **discovery winners**.  
- Can claim Stage 3/3B historical search results (0 selected) and V53.6 ledger reproduction metrics from committed CSVs.  
- Cannot claim full independent side-convention requalification without restored OHLC.
