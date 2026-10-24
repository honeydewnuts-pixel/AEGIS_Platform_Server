# M5_VariantB_V Rulebook

M5min pullback-failure reversal with main-window trend filter and volatility filter.

## Filters
- Main-window: block longs in confirmed BB17/BB34 downtrend; block shorts in confirmed uptrend.
- Volatility: trade only when ATR(14) > rolling 100-bar median ATR.

## Short entry
1. MA7 and RSI9 cross below BB34 middle band within 30 bars.
2. MA7 between middle and lower bands.
3. RSI9 or WPR60 pulls back above middle band.
4. RSI9 crosses back below MA7 or middle band.
5. Enter short.

## Long entry
Mirror conditions after upside break.

## Exits
- Initial stop: 1.5 x ATR(14)
- Chandelier trail: 2.5 x ATR(14), activated after 1 x ATR favorable move
- Time stop: 48 hours
- Opposite-signal exit
- Cooldown: 30 bars
- Risk: 1% per trade; cost 1.9 pips round trip

## Result
See M5_VariantB_V_summary.csv
