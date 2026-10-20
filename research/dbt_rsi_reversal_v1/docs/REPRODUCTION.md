# Reproduction

```bash
cd /path/to/AEGIS_Platform_Server
python3 research/dbt_rsi_reversal_v1/tests/test_dbt_indicators.py
python3 research/dbt_rsi_reversal_v1/scripts/run_dbt_rsi_research.py
```

Data: `/home/workdir/artifacts/AEGIS_CSV_5Y/*_M5_BIDASK_5Y.csv` (or equivalent path).  
Flags: production_authorized=false, execution_authorized=false.
