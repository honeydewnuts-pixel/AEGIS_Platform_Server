# AEGIS V39 Checkpoint — Transfer + Native Discovery Status

Date: 2026-09-09

## Purpose
Persistent checkpoint of the AEGIS Platform Server and V39 research artifacts. This checkpoint is intended to preserve the implementation/governance state so work can resume without relying on conversational memory.

## Frozen transfer status
- AUDUSD 36M: V31 numerical gates PASS; V35 numerical gates PASS.
- USDCHF 36M: V31 numerical gates PASS; V35 numerical gates PASS.
- NZDUSD 36M: V31 numerical gates PASS; V35 numerical gates PASS.
- USDJPY 36M: V31 REJECT; V35 REJECT. Do not force. Trading disabled for transferred GBPUSD rulebooks.
- EURUSD 36M: V31 REJECT; V35 REJECT.
- EURJPY: 24M transfer previously failed; now native discovery proceeds without waiting for more history.
- GBPJPY: 24M native-discovery dataset assembled from 2024 Bid-only M1 plus 2025-09 to 2026-08 Bid/Ask M5; this mixed execution quality is explicitly recorded.

## Native discovery results (research screening pass)
### EURJPY 24M
Selected causal candidate from predeclared 64-candidate family set:
- 48-bar preceding compression < 1.0 ATR
- current expansion >= 1.5 ATR
- short direction
- 12-bar structural downside break
- next-bar entry; frozen 1.5 ATR SL, +1R BE, 0.75 ATR trailing, max 72 bars, 0.085R cost
- Train: 903 trades, PF 1.645
- Validation: 195 trades, PF 2.348
- Final Test: 220 trades, PF 1.902
- Six blocks: PF 1.548, 1.286, 2.107, 1.672, 2.111, 1.963
- Result: REJECTED under the immutable 300-trade Validation/Final-Test gates (candidate has good PF but insufficient validation/final sample).

### GBPJPY 24M
Selected causal candidate from predeclared 64-candidate family set:
- 24-bar preceding compression < 1.0 ATR
- current expansion >= 1.5 ATR
- long direction
- low-exhaustion condition
- Train: 2072 trades, PF 0.997
- Validation: 453 trades, PF 0.851
- Final Test: 471 trades, PF 0.873
- Six blocks: PF 0.882, 1.011, 1.013, 1.060, 0.916, 0.849
- Result: REJECTED; PF gate failure.

These are discovery screening outcomes, not production authorization and not a qualified new rulebook.

## USDJPY governance
Keep USDJPY registered in the instrument library with status TRANSFER_REJECTED / TRADING_DISABLED. Do not delete its data or research lineage. Native USDJPY discovery is a separate track and does not modify V31/V35.

## Next research step
- Complete V39 audit/independent reproduction for transfer winners: AUDUSD V31/V35, USDCHF V31/V35, NZDUSD V31/V35.
- EURJPY and GBPJPY are transfer failures / discovery candidates; native discovery may continue under strict chronological nested validation.
- USDJPY native discovery may begin after the V39 transfer cohort is frozen, using clean 36M Bid+Ask data where available.
- No V40 platform release is authorized by this checkpoint.

## Data lineage hashes
- EURJPY.zip: 7ee3f78430fadccef2034acb16452075e7d474b030deb2c54c27b41a9dcdd23f
- GBPJPY.zip: 925661e60819eb2d86d5785fd1d39db8d83824570903ff7e8840fc2d2b5d204d
- EURJPY_NEW12_M5.csv: b93388755ca523ca7e22a8c3e6ab470a951d8aacb2f652a5931a9cae5a47aa22
- Existing EURJPY_M5_BID_ASK.csv: 798eec8cd6e9bfd84e3ba640085dd88d1c01b329685a7614f9cb5b8cdea845fc
- Existing GBPJPY_M5_BID_ASK.csv: 80e212ab20907938b27b53e48c18945fd5e13b01d51cc8dd4f02ef98a96c5ee3
