# Discovery 2026-10-14

## Reproduce Stage 3 (when datasets restored)

```bash
# Place Bid/Ask CSVs where scripts/stage3_broker_correct_discovery.py expects them
# (inspect script for paths), then:
python scripts/stage3_broker_correct_discovery.py
```

## Reproduce V53.6 ledger metrics from committed CSVs

```bash
python3 -c "import csv; ..."  # or use verification CSVs under artifacts/v53_6_verification/
```

## Governance

Do not set production_authorized. Do not merge research into production registries without separate authorization.
