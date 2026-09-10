from __future__ import annotations
from dataclasses import dataclass
from .models import TransferEligibility, TransferParameter
from .parameter_mapping import map_execution_parameters

SOURCE_RULEBOOKS = ('AEGIS-RB-V31-GBPUSD-5M','AEGIS-RB-V35-GBPUSD-5M')

@dataclass(frozen=True)
class ForexTransferEngine:
    version: str = 'V39.1'

    def eligibility(self, source_rulebook_id: str, target_instrument: str, *, data_available: bool,
                    data_valid: bool, spread_available: bool, enough_history: bool,
                    data_hash: str | None = None) -> TransferEligibility:
        if source_rulebook_id not in SOURCE_RULEBOOKS:
            return TransferEligibility(source_rulebook_id, target_instrument, 'M5', 'TRANSFER_NOT_ELIGIBLE', ('UNKNOWN_SOURCE_RULEBOOK',), data_hash)
        if not data_available: status, reason = 'DATA_NOT_AVAILABLE', 'TARGET_DATASET_NOT_PRESENT'
        elif not data_valid: status, reason = 'DATA_INVALID', 'TARGET_DATASET_FAILED_INTEGRITY'
        elif not enough_history: status, reason = 'INSUFFICIENT_HISTORY', 'TARGET_HISTORY_BELOW_RESEARCH_REQUIREMENT'
        elif not spread_available: status, reason = 'INSUFFICIENT_SPREAD_DATA', 'NO_HISTORICAL_BID_ASK_OR_SPREAD'
        else: status, reason = 'TRANSFER_ELIGIBLE', 'PRECONDITIONS_MET'
        return TransferEligibility(source_rulebook_id, target_instrument, 'M5', status, (reason,), data_hash)

    def execution_parameters(self, target_df, source_1r_ratio: float):
        return map_execution_parameters(target_df, source_1r_ratio)
