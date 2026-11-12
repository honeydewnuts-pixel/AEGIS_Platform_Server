from __future__ import annotations
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

    def lookup(
        self, instrument: str, timeframe: str, *, qualified_only: bool = False
    ) -> list[RulebookDefinition]:
        out = [
            x
            for x in self._items.values()
            if x.instrument.upper() == instrument.upper()
            and x.timeframe.upper() == timeframe.upper()
        ]
        if qualified_only:
            out = [
                x
                for x in out
                if x.qualification_status == "QUALIFIED_RESEARCH_CANDIDATE_FROZEN"
            ]
        return sorted(out, key=lambda x: x.rulebook_id)

    def all(self) -> tuple[RulebookDefinition, ...]:
        return tuple(self._items.values())

    def count(self) -> int:
        return len(self._items)


def founding_registry() -> RulebookRegistry:
    """
    OPERATIONAL founding registry — intentionally EMPTY after rehabilitation.

    Historical V31/V35 research definitions are archived; not operationally loaded.
    production_authorized = false
    execution_authorized = false
    """
    return RulebookRegistry([])


def operational_registry() -> RulebookRegistry:
    return founding_registry()
