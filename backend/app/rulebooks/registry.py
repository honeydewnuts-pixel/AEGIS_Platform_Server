from __future__ import annotations
from dataclasses import replace
from typing import Iterable
from .models import RulebookDefinition

class RulebookRegistry:
    """Immutable-in-process registry. Registration rejects duplicate IDs."""
    def __init__(self, definitions: Iterable[RulebookDefinition] = ()) -> None:
        self._items: dict[str, RulebookDefinition] = {}
        for item in definitions:
            self.register(item)

    def register(self, definition: RulebookDefinition) -> RulebookDefinition:
        if definition.rulebook_id in self._items:
            raise ValueError(f"Rulebook ID already registered: {definition.rulebook_id}")
        self._items[definition.rulebook_id] = definition
        return definition

    def get(self, rulebook_id: str) -> RulebookDefinition | None:
        return self._items.get(rulebook_id)

    def lookup(self, instrument: str, timeframe: str, *, qualified_only: bool = False) -> list[RulebookDefinition]:
        out = [x for x in self._items.values() if x.instrument.upper() == instrument.upper() and x.timeframe.upper() == timeframe.upper()]
        if qualified_only:
            out = [x for x in out if x.qualification_status == "QUALIFIED_RESEARCH_CANDIDATE_FROZEN"]
        return sorted(out, key=lambda x: x.rulebook_id)

    def all(self) -> tuple[RulebookDefinition, ...]:
        return tuple(self._items.values())


def founding_registry() -> RulebookRegistry:
    lineage = {
        "dataset": "AEGIS_V37_STANDARDIZED_GBPUSD_5M.csv",
        "sha256": "6e962ec23023f9c747514bed17077a9bc7dadc4b42591feb1e29140c1e580ed5",
        "split": "70/15/15 chronological",
        "final_test_locked": True,
    }
    common_exec = ("completed-bar signal", "next-bar AskOpen", "one-position", "1.5 ATR14 initial SL", "+1R break-even", "0.75 ATR trailing", "72-bar max")
    common_risk = ("1R=0.00100", "cost=0.085R/trade", "short stop BidHigh")
    return RulebookRegistry([
        RulebookDefinition(
            "AEGIS-RB-V31-GBPUSD-5M", "STRUCTURAL_BREAK", "GBPUSD", "M5", "1.0",
            "QUALIFIED_RESEARCH_CANDIDATE_FROZEN",
            "12-bar compression + low exhaustion + down-break short continuation",
            ("ATR14", "12-bar structural high/low", "LOW_EXHAUSTION", "12-bar compression", "12-bar event throttle"),
            common_exec, common_risk, "0.085R/trade; target transfer must normalize target spread/ATR",
            "QUALIFIED_RESEARCH_CANDIDATE_FROZEN",
            {"signals": 2825, "trades": 2600, "validation_pf": 1.5226492929, "final_test_pf": 1.9278993553},
            lineage, "V37-FROZEN-REFERENCE", "2026-09-08T12:00:00Z", "2026-09-08T12:00:00Z", None, "AEGIS_V37_V31_REPRODUCTION.csv"),
        RulebookDefinition(
            "AEGIS-RB-V35-GBPUSD-5M", "MULTI_SCALE_EXPANSION", "GBPUSD", "M5", "1.0",
            "QUALIFIED_RESEARCH_CANDIDATE_FROZEN",
            "12-bar compression + expansion + 24/48-bar downside agreement + short continuation",
            ("ATR14", "12-bar compression", "current range/ATR", "24-bar displacement", "48-bar displacement", "12-bar event throttle"),
            common_exec, common_risk, "0.085R/trade; target transfer must normalize target spread/ATR",
            "QUALIFIED_RESEARCH_CANDIDATE_FROZEN",
            {"signals": 2238, "trades": 2060, "validation_pf": 2.0591182330, "final_test_pf": 1.8063749417},
            lineage, "V37-FROZEN-REFERENCE", "2026-09-08T12:00:00Z", "2026-09-08T12:00:00Z", None, "AEGIS_V37_V35_REPRODUCTION.csv"),
    ])
