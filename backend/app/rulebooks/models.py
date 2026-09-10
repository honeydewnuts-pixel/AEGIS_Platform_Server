from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class RulebookDefinition:
    rulebook_id: str
    rulebook_family: str
    instrument: str
    timeframe: str
    version: str
    status: str
    mechanism_description: str
    feature_schema: tuple[str, ...]
    execution_schema: tuple[str, ...]
    risk_schema: tuple[str, ...]
    cost_model: str
    qualification_status: str
    qualification_metrics: dict[str, Any]
    data_lineage: dict[str, Any]
    code_version: str
    created_at: str
    frozen_at: str | None = None
    supersedes: str | None = None
    audit_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
