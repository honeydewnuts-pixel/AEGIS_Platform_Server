# Autonomous MultiSymbol (no mobile dropdown)

## Path
MT5 OHLC Feed (MultiSymbol) → POST `/api/mt5/ohlc/stream` (CLOSED bar)  
  → AutonomousOhlcSignalService → UniversalAnalysis (V31 SHORT / V53.6 baseline)  
  → ExecutorSignalService.publish → **AEGIS_Executor v2.19** pending-batch → OrderSend  
  → Position manager (BE / trail / 72 M5 bars) on open shorts

Mobile symbol dropdown is only for optional screenshot context / monitoring.

## Baseline signal policy (cash-test restoration)
- Research path: **V31 SHORT only** (SELL); BUY rejected on baseline
- No `demo_ohlc_structure` slope substitute
- No confidence-flip exits on baseline (exits via SL / BE / trail / TIME in Executor v2.19)
- Production authorization remains disabled unless separately enabled

## EA setup
- **Feed v2.03:** MultiSymbol, SymbolsList=…, ForceTF=M5  
- **Executor v2.19:** MultiPair, same SymbolsList, `UseServerSignals=true`, `EnablePositionManager=true`, `BaselineShortOnly=true`
