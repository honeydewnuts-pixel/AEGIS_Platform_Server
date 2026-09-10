"""Fail-closed Universal Router for the AEGIS V46 production repository baseline.

This layer resolves only registry-qualified research candidates. It does not
place orders and it cannot promote a research candidate to production.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import csv


class RouteState(str, Enum):
    ROUTABLE_RESEARCH = "ROUTABLE_RESEARCH"
    UNKNOWN_INSTRUMENT = "UNKNOWN_INSTRUMENT"
    UNKNOWN_TIMEFRAME = "UNKNOWN_TIMEFRAME"
    NO_QUALIFIED_RULEBOOK = "NO_QUALIFIED_RULEBOOK"
    INSUFFICIENT_SPREAD_DATA = "INSUFFICIENT_SPREAD_DATA"
    RULEBOOK_INTEGRITY_FAILURE = "RULEBOOK_INTEGRITY_FAILURE"
    MODEL_LINEAGE_FAILURE = "MODEL_LINEAGE_FAILURE"
    PRODUCTION_AUTHORIZATION_REQUIRED = "PRODUCTION_AUTHORIZATION_REQUIRED"


@dataclass(frozen=True)
class RouteDecision:
    state: RouteState
    instrument: str
    timeframe: str
    rulebook_ids: tuple[str, ...] = ()
    production_authorized: bool = False
    reason: str = ""


class UniversalRouter:
    """Resolve instrument/timeframe against an immutable CSV registry.

    Production authorization is intentionally not inferred from registry
    membership. A caller must explicitly provide production_authorized=True,
    and the registry row must itself contain production_authorized=true.
    """

    def __init__(self, registry_csv: str | Path):
        self.registry_csv = Path(registry_csv)
        self._rows = self._load()

    def _load(self) -> list[dict[str, str]]:
        with self.registry_csv.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def resolve(
        self,
        instrument: str,
        timeframe: str,
        *,
        spread_available: bool = True,
        rulebook_integrity_ok: bool = True,
        model_lineage_ok: bool = True,
        production_requested: bool = False,
    ) -> RouteDecision:
        instrument = instrument.upper()
        timeframe = timeframe.upper()
        matching_instrument = [r for r in self._rows if r.get("instrument", "").upper() == instrument]
        if not matching_instrument:
            return RouteDecision(RouteState.UNKNOWN_INSTRUMENT, instrument, timeframe, reason="Instrument absent from registry")
        matching = [r for r in matching_instrument if r.get("timeframe", "").upper() == timeframe]
        if not matching:
            return RouteDecision(RouteState.UNKNOWN_TIMEFRAME, instrument, timeframe, reason="Timeframe not registered for instrument")
        if not spread_available:
            return RouteDecision(RouteState.INSUFFICIENT_SPREAD_DATA, instrument, timeframe, reason="Bid/Ask spread data unavailable")
        if not rulebook_integrity_ok:
            return RouteDecision(RouteState.RULEBOOK_INTEGRITY_FAILURE, instrument, timeframe, reason="Rulebook integrity gate failed")
        if not model_lineage_ok:
            return RouteDecision(RouteState.MODEL_LINEAGE_FAILURE, instrument, timeframe, reason="Model lineage gate failed")

        eligible = []
        for row in matching:
            status = row.get("status", "")
            authorized = row.get("production_authorized", "false").lower() == "true"
            if status in {"QUALIFIED_RESEARCH_CANDIDATE", "SOURCE_RULEBOOK_FROZEN"}:
                eligible.append(row)
            if production_requested and not authorized:
                # Explicitly fail closed if a caller asks for live/production
                # while every matching entry is research-only.
                continue

        if not eligible:
            return RouteDecision(RouteState.NO_QUALIFIED_RULEBOOK, instrument, timeframe, reason="No eligible rulebook")

        if production_requested:
            production_rows = [r for r in eligible if r.get("production_authorized", "false").lower() == "true"]
            if not production_rows:
                return RouteDecision(RouteState.PRODUCTION_AUTHORIZATION_REQUIRED, instrument, timeframe, tuple(r["rulebook_id"] for r in eligible), reason="Research qualification is not production authorization")
            eligible = production_rows

        return RouteDecision(RouteState.ROUTABLE_RESEARCH, instrument, timeframe, tuple(r["rulebook_id"] for r in eligible), reason="Registry-qualified research route")
