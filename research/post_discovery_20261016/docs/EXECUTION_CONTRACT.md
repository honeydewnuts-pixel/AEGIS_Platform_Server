# Execution Contracts

## Broker-correct (discovery / operational)

**Functions:** `simulate_long_broker_correct`, `simulate_short_broker_correct`  
**File:** `aegis_disc2/backend/app/rulebooks/evaluators/common.py`  
**Cost model:** Bid/Ask embedded only; `cost_R = 0`; no 0.085R

| Side | Entry | Stop trigger | Trail / time exit |
|------|-------|--------------|-------------------|
| LONG | AskOpen[i+1] | BidLow[j] ≤ stop | BidClose[j] |
| SHORT | BidOpen[i+1] | AskHigh[j] ≥ stop | AskClose[j] |

- Break-even at +1R (always on in frozen functions).
- Trail distance = `trail_atr_mult × ATR[j]` after BE.
- Max hold counted from signal bar `i`.
- One position at a time (`next_allowed = exit_i`).
- Gap through stop: fill at stop price (optimistic vs real open).
- Intrabar: stop checked before BE; close used for trail/BE.

## V53.6 historical reconstruction (do not mix)

**Function:** `simulate_short` (default `cost_mode=legacy_fixed_r`)  
**Entry:** AskOpen[i+1]  
**Stop:** BidHigh[j] ≥ stop  
**Exit:** BidClose[j]  
**Cost:** gross_R − 0.085R (legacy)

These contracts are intentionally different. Discovery work must use broker-correct. Historical cash-test reproduction of V31/V35/V53.6 must use the legacy path.
