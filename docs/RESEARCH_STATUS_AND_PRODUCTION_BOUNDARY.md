# Research Status and Production Boundary

## Frozen production methodology

**V53.6** remains frozen. Historical reconstruction and evaluator behavior are not modified by Executor remediation or exploratory research.

## Production status

Executor remediation (filling, lifecycle, close detection) is **separate** from strategy research.

- Executor compile / live MT5 validation: user VPS gate
- Strategy production authorization: **fail-closed registry**; research methods are not authorized

## Research streams

| Stream | Status | Qualified | Execution model | Production authorized |
|--------|--------|-----------|-----------------|------------------------|
| V53.6 SHORT | RESEARCH ONLY (REPRODUCTION VERIFIED vs stored ledger) | Historical path only | Historical AskOpen / BidHigh | **NO** |
| RSI9 SHORT | RESEARCH ONLY | NOT QUALIFIED under broker-correct | Broker-correct fails gates | **NO** |
| Native LONG | RESEARCH ONLY | NOT QUALIFIED under broker-correct | Broker-correct fails gates | **NO** |
| Stage 3B Multi-TF | RESEARCH ONLY | **0 candidates** | Broker-correct M5/M15/H1 | **NO** |

### Stage 3B detail

Artifacts:

- `artifacts/stage3b_multitf/STAGE3B_REPORT.json`
- `docs/STAGE3B_MULTITF_DISCOVERY.md`
- `scripts/stage3b_multitf_broker_correct_discovery.py`

Result: **n_selected = 0**, **n_winners = 0**, `production_authorized = false`.

Pairs/timeframes/families searched under frozen PF gates; no rulebook promoted to production configuration, signal publication, or Executor behavior.

## Isolation

Research scripts and artifacts:

- Are **not** loaded into production rulebook registries for live execution
- Do **not** alter V53.6 evaluator or locks
- Do **not** change Executor order logic
- Cannot become production without a separate, explicit authorization decision after chronological/walk-forward, Final Test, broker-correct economics, and risk gates

## Promotion requirements

A positive backtest alone is insufficient. Promotion requires:

1. Broker-correct economics
2. Chronological / walk-forward validation
3. Untouched Final Test
4. Execution-integrity (lifecycle) checks
5. Explicit production authorization flag
6. Separate integration proposal — never silent merge
