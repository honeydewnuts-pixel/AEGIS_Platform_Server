from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

TRANSFER_FAILURE_STATES = {
    'DATA_NOT_AVAILABLE','DATA_INVALID','INSUFFICIENT_HISTORY','INSUFFICIENT_SPREAD_DATA',
    'TRANSFER_NOT_ELIGIBLE','TRANSFER_FAILED','VALIDATION_FAILED','FINAL_TEST_FAILED',
    'ROBUSTNESS_FAILED','LEAKAGE_FAILED','REPRODUCTION_FAILED','QUALIFIED'
}

@dataclass(frozen=True)
class TransferParameter:
    source_rulebook_id: str
    target_instrument: str
    timeframe: str
    parameter_name: str
    source_value: Any
    normalization_method: str
    target_value: Any
    causal_window: str
    adaptation_version: str
    adaptation_reason: str
    data_version: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class TransferEligibility:
    source_rulebook_id: str
    target_instrument: str
    timeframe: str
    status: str
    reasons: tuple[str, ...]
    data_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
