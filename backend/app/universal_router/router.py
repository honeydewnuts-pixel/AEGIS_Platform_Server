"""Fail-closed Universal Router for the AEGIS V46 production repository baseline.

Resolves instrument/timeframe against the V40 instrument + rulebook CSVs.
Does not place orders. Research eligibility is never production authorization.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import csv
from typing import Any


class RouteState(str, Enum):
    ROUTABLE_RESEARCH = "ROUTABLE_RESEARCH"
    UNKNOWN_INSTRUMENT = "UNKNOWN_INSTRUMENT"
    UNKNOWN_TIMEFRAME = "UNKNOWN_TIMEFRAME"
    NO_QUALIFIED_RULEBOOK = "NO_QUALIFIED_RULEBOOK"
    TRADING_DISABLED = "TRADING_DISABLED"
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
    registry_status: str = ""
    router_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["rulebook_ids"] = list(self.rulebook_ids)
        return d


def default_registry_dir() -> Path:
    """Resolve /app/registry/v40 in Docker or <repo>/registry/v40 in dev."""
    here = Path(__file__).resolve()
    # backend/app/universal_router/router.py -> parents[3] = backend, [4]=repo root
    candidates = [
        here.parents[3] / "registry" / "v40",  # /app/backend -> wrong
        here.parents[4] / "registry" / "v40" if len(here.parents) > 4 else None,
        Path("/app/registry/v40"),
        Path.cwd() / "registry" / "v40",
        Path.cwd().parent / "registry" / "v40",
    ]
    for c in candidates:
        if c is None:
            continue
        if (c / "AEGIS_V40_INSTRUMENT_REGISTRY.csv").exists():
            return c
    return Path("/app/registry/v40")


class UniversalRouter:
    """Resolve instrument/timeframe against V40 instrument + rulebook registries.

    Production authorization requires:
      production_requested=True AND a matching rulebook with production_authorized=true.
    Research membership alone never authorizes live execution.
    """

    def __init__(
        self,
        registry_csv: str | Path | None = None,
        *,
        instrument_csv: str | Path | None = None,
        rulebook_csv: str | Path | None = None,
    ):
        reg_dir = default_registry_dir()
        # Back-compat: single registry_csv arg historically pointed at rulebook CSV
        if registry_csv is not None and rulebook_csv is None:
            p = Path(registry_csv)
            if p.name.startswith("AEGIS_V40_INSTRUMENT"):
                instrument_csv = p
            else:
                rulebook_csv = p

        self.instrument_csv = Path(instrument_csv) if instrument_csv else reg_dir / "AEGIS_V40_INSTRUMENT_REGISTRY.csv"
        self.rulebook_csv = Path(rulebook_csv) if rulebook_csv else reg_dir / "AEGIS_V40_RULEBOOK_REGISTRY.csv"
        self._instruments = self._load(self.instrument_csv)
        self._rulebooks = self._load(self.rulebook_csv)

    @staticmethod
    def _load(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
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
        instrument = instrument.upper().strip()
        timeframe = timeframe.upper().strip()

        inst_rows = [
            r
            for r in self._instruments
            if (r.get("instrument") or "").upper() == instrument
        ]
        if not inst_rows:
            # Fall back: instrument only known via rulebook CSV
            rb_only = [
                r
                for r in self._rulebooks
                if (r.get("instrument") or "").upper() == instrument
            ]
            if not rb_only:
                return RouteDecision(
                    RouteState.UNKNOWN_INSTRUMENT,
                    instrument,
                    timeframe,
                    reason="Instrument absent from V40 registry",
                )
            # Synthetic instrument presence from rulebooks
            inst_rows = [
                {
                    "instrument": instrument,
                    "timeframe": timeframe,
                    "router_status": "RESEARCH_ELIGIBLE",
                    "registry_status": "FROM_RULEBOOKS",
                    "eligible_rulebooks": "",
                    "reason": "Derived from rulebook registry",
                }
            ]

        tf_rows = [
            r
            for r in inst_rows
            if (r.get("timeframe") or "M5").upper() == timeframe
        ]
        if not tf_rows:
            return RouteDecision(
                RouteState.UNKNOWN_TIMEFRAME,
                instrument,
                timeframe,
                reason="Timeframe not listed for instrument",
                registry_status=inst_rows[0].get("registry_status") or "",
                router_status=inst_rows[0].get("router_status") or "",
            )

        row = tf_rows[0]
        registry_status = (row.get("registry_status") or "").upper()
        router_status = (row.get("router_status") or "").upper()
        reason_reg = row.get("reason") or ""

        if router_status in {"TRADING_DISABLED", "DISABLED", "REJECTED"}:
            return RouteDecision(
                RouteState.TRADING_DISABLED,
                instrument,
                timeframe,
                reason=reason_reg or "Instrument is trading-disabled in V40 registry",
                registry_status=registry_status,
                router_status=router_status,
            )

        if not spread_available:
            return RouteDecision(
                RouteState.INSUFFICIENT_SPREAD_DATA,
                instrument,
                timeframe,
                reason="Bid/Ask spread data unavailable",
                registry_status=registry_status,
                router_status=router_status,
            )
        if not rulebook_integrity_ok:
            return RouteDecision(
                RouteState.RULEBOOK_INTEGRITY_FAILURE,
                instrument,
                timeframe,
                reason="Rulebook integrity gate failed",
                registry_status=registry_status,
                router_status=router_status,
            )
        if not model_lineage_ok:
            return RouteDecision(
                RouteState.MODEL_LINEAGE_FAILURE,
                instrument,
                timeframe,
                reason="Model lineage gate failed",
                registry_status=registry_status,
                router_status=router_status,
            )

        # Eligible rulebook IDs from instrument row and/or rulebook CSV
        eligible_ids: list[str] = [
            x.strip()
            for x in (row.get("eligible_rulebooks") or "").split(";")
            if x.strip()
        ]
        for rb in self._rulebooks:
            if (rb.get("instrument") or "").upper() != instrument:
                continue
            if (rb.get("timeframe") or "M5").upper() != timeframe:
                continue
            status = (rb.get("status") or "").upper()
            if status in {
                "QUALIFIED_RESEARCH_CANDIDATE",
                "SOURCE_RULEBOOK_FROZEN",
                "FOUNDING",
            }:
                rid = rb.get("rulebook_id") or ""
                if rid and rid not in eligible_ids:
                    eligible_ids.append(rid)

        if not eligible_ids and router_status not in {
            "RESEARCH_ELIGIBLE",
            "TRADING_ENABLED",
            "LIVE",
        }:
            return RouteDecision(
                RouteState.NO_QUALIFIED_RULEBOOK,
                instrument,
                timeframe,
                reason=reason_reg or "No eligible rulebook",
                registry_status=registry_status,
                router_status=router_status,
            )

        if not eligible_ids:
            return RouteDecision(
                RouteState.NO_QUALIFIED_RULEBOOK,
                instrument,
                timeframe,
                reason="RESEARCH_ELIGIBLE but no rulebook IDs listed",
                registry_status=registry_status,
                router_status=router_status,
            )

        # Production gate: never infer from research membership
        if production_requested:
            prod_ids = []
            for rb in self._rulebooks:
                rid = rb.get("rulebook_id") or ""
                if rid not in eligible_ids:
                    continue
                if (rb.get("production_authorized") or "false").lower() == "true":
                    prod_ids.append(rid)
            if not prod_ids:
                return RouteDecision(
                    RouteState.PRODUCTION_AUTHORIZATION_REQUIRED,
                    instrument,
                    timeframe,
                    rulebook_ids=tuple(eligible_ids),
                    production_authorized=False,
                    reason="Research qualification is not production authorization",
                    registry_status=registry_status,
                    router_status=router_status,
                )
            return RouteDecision(
                RouteState.ROUTABLE_RESEARCH,
                instrument,
                timeframe,
                rulebook_ids=tuple(prod_ids),
                production_authorized=True,
                reason="Production-authorized route",
                registry_status=registry_status,
                router_status=router_status,
            )

        return RouteDecision(
            RouteState.ROUTABLE_RESEARCH,
            instrument,
            timeframe,
            rulebook_ids=tuple(eligible_ids),
            production_authorized=False,
            reason=reason_reg or "Registry-qualified research route",
            registry_status=registry_status,
            router_status=router_status,
        )
