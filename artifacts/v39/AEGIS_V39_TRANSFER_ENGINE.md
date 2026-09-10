# AEGIS V39 Cross-Instrument Forex Transfer Engine

Version: V39.1
Status: foundation implemented; empirical target transfer pending target datasets.

## Design
The engine transfers the frozen V31/V35 mechanisms by normalizing dimensionless market geometry rather than copying GBPUSD price-scale values. Target execution uses target ATR14; the original GBPUSD `0.00100` 1R is never used as a target absolute distance.

## Causal features
- ATR14 using the recovered Wilder recurrence.
- current range / ATR14.
- preceding 12-bar structural range / ATR14.
- preceding 12-bar mean range / ATR14 compression.
- current expansion ratio.
- 24-bar and 48-bar close displacement / ATR14.
- spread / ATR14 when Bid/Ask exists.
- expected cost / ATR14 when spread exists.

All rolling/shifted features are causal and use completed-bar information.

## Execution mapping
- next-bar entry
- instrument-appropriate Bid/Ask side
- initial stop = 1.5 ATR14
- +1R break-even
- trailing = 0.75 ATR14
- maximum 72 bars
- one position
- source 1R is represented dimensionlessly as source-1R / source median ATR14; target 1R is target median ATR14 times that ratio. This policy is predeclared and versioned.

## Spread policy
No historical spread is invented. A target without Bid/Ask or independently documented spread data is `INSUFFICIENT_SPREAD_DATA` for spread-dependent qualification.

## Qualification
Validation >=300 trades and PF >1.60; Final Test >=300 trades and PF >1.60; six-block robustness; coherent mechanism; causality; execution audit; independent reproduction. Final Test is locked and never used for selection.

## V39 state
No non-GBPUSD Forex target dataset was found in the mounted workspace. Library search located the V38 instrument registry/specification artifacts, but no target OHLC/Bid-Ask dataset. Therefore no empirical transfer result is claimed.
