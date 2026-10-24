# M15 Variant B-V Rulebook

GBPUSD M15 pullback-failure reversal with main-window trend filter and volatility filter.

## Indicators
- RSI(9) on close
- SMA(7) of RSI(9) = MA7
- Bollinger Bands(34, 1.618) on MA7
- Williams %R(60)
- ATR(14)

## Filters
- Main-window trend filter: block longs in confirmed BB17/BB34 downtrend; block shorts in confirmed uptrend.
- Volatility filter: trade only when ATR(14) is above its rolling 100-bar median.

## Short entry
1. MA7 and RSI9 cross below the BB34 middle band within the last 30 bars.
2. MA7 remains between the BB34 middle and lower bands.
3. RSI9 or WPR60 pulls back above the middle band.
4. RSI9 crosses back below MA7 or the middle band.
5. Enter short.

## Long entry
Mirror conditions after an upside break.

## Trade management
- Initial stop: 1.5 x ATR(14)
- Trailing stop: 2.5 x ATR(14) chandelier, activated after 1 x ATR favorable movement
- Time stop: 48 hours
- Opposite-signal exit
- Cooldown: 30 bars
- Risk: 1% equity per trade
- Cost: 1.9 pips round trip

## Cash-test result
- Trades: 233
- Profit factor: 1.99
- Win rate: 53.2%
- Net P&L: +$11,014.42
- Final balance: $21,014.42
- Maximum drawdown: -5.81%
- Six-block PF: 2.62, 1.68, 2.45, 2.27, 1.48, 1.82

## Status
Passes profit-factor and six-block criteria; fails the >350-trade criterion. Not yet cross-market validated.
