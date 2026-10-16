# Post-discovery research checkpoint (2026-10-16)

Preserved artefacts from the broker-realistic discovery phase and post-discovery integrity / market-behaviour study.

**Branch:** research/broker-realistic-discovery-20261014  
**Prior HEAD at packaging:** 8385fc60ea16a195ba00a64697ddc07d4f526b9c  

## Conclusions (do not dilute)

- Asian→London, HTF→M5 pullback, Asian→NY: **no qualifying Rulebook** under tested specs.
- HTF→M5 reported PF was **not fully cost-adjusted** (slip/comm in filter only).
- Directional persistence (preregistered H=12): **REJECTED**.
- Volatility expansion after low-vol: **REJECTED**.
- Final 20% periods from prior scans: **EXPOSED**, not independent confirmation.
- Block-bootstrap CIs: **not run** (disclosed limitation).
- **No production authorisation. No Rulebook promoted.**

## Layout

- `docs/` — preregistration, findings, final report, integrity audit, execution contract
- `outputs/` — experiment register, data manifest, audit findings, behaviour results
- `scripts/` — `run_direct_market_behaviour.py`
- `tests/` — broker-correct and Asian-NY unit tests + outputs
- `prior_scan_outputs/` — completed scan CSVs/JSON/logs and runner scripts

Preregistration hash: see `outputs/preregistration_hash.txt` (must match preregistration file).
