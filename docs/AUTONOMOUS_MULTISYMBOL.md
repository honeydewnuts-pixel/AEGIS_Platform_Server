# Autonomous MultiSymbol (no mobile dropdown)

## Path
MT5 OHLC Feed (MultiSymbol) → POST /api/mt5/ohlc/stream (CLOSED bar)
  → AutonomousOhlcSignalService → UniversalAnalysis → confidence gate
  → ExecutorSignalService.publish → AEGIS_Executor pending-batch → OrderSend

Mobile symbol dropdown is only for optional screenshot context / monitoring.

## Confidence policy (EXEC_MIN_CONFIDENCE=0.75)
- BUY/SELL published only if confidence >= threshold
- Same direction while open → rejected
- Opposite below threshold → rejected (position held; no fixed TP)
- Opposite at/above threshold → flip (Executor closes then opens)

## EA setup
Feed: MultiSymbol, SymbolsList=GBPUSD,AUDUSD,... ForceTF=M5
Executor v2.16: MultiPair, same SymbolsList, UseServerSignals=true
