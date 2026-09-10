from __future__ import annotations

def qualification_status(*, data_available: bool, valid: bool, spread_available: bool, enough_history: bool,
                          validation_trades: int = 0, validation_pf: float = 0.0,
                          final_trades: int = 0, final_pf: float = 0.0,
                          six_block_ok: bool = False, mechanism_ok: bool = False,
                          causality_ok: bool = False, execution_ok: bool = False,
                          reproduction_ok: bool = False) -> str:
    if not data_available: return 'DATA_NOT_AVAILABLE'
    if not valid: return 'DATA_INVALID'
    if not enough_history: return 'INSUFFICIENT_HISTORY'
    if not spread_available: return 'INSUFFICIENT_SPREAD_DATA'
    if validation_trades < 300 or validation_pf <= 1.60: return 'VALIDATION_FAILED'
    if final_trades < 300 or final_pf <= 1.60: return 'FINAL_TEST_FAILED'
    if not six_block_ok: return 'ROBUSTNESS_FAILED'
    if not mechanism_ok: return 'TRANSFER_FAILED'
    if not causality_ok: return 'LEAKAGE_FAILED'
    if not execution_ok: return 'TRANSFER_FAILED'
    if not reproduction_ok: return 'REPRODUCTION_FAILED'
    return 'QUALIFIED'
