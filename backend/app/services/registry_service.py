"""
Rulebook registry + tradeable pairs registry.

Replaces the old indicator-template system. MT5 charts are plain price charts;
no indicator stack is required or installed by the client.

Sources (in order) after rehabilitation:
  1. registry/operational/*.csv (authoritative; empty until explicit approval)
  2. No founding_registry fallback of research rulebooks
  3. Instruments are NEVER derived from rulebook records

production_authorized = false
execution_authorized = false
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import configure_logging

# repo root: backend/app/services -> parents[3] = repo root when layout is monorepo
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_APP = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BACKEND_APP / "templates"
OPERATIONAL_REGISTRY_DIR = REPO_ROOT / "registry" / "operational"
REGISTRY_DIR = OPERATIONAL_REGISTRY_DIR
LEGACY_V40_REGISTRY_DIR = REPO_ROOT / "registry" / "v40"
ARTIFACTS_V40_REGISTRY_DIR = REPO_ROOT / "artifacts" / "v40" / "registry"


class RegistryService:
    def __init__(self) -> None:
        self.logger = configure_logging(__name__)
        self._rulebooks: list[dict[str, Any]] = []
        self._instruments: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        self._rulebooks = self._load_rulebooks()
        self._instruments = self._load_instruments()
        rb_csv = REGISTRY_DIR / "AEGIS_OPERATIONAL_RULEBOOK_REGISTRY.csv"
        inst_csv = REGISTRY_DIR / "AEGIS_OPERATIONAL_INSTRUMENT_REGISTRY.csv"
        self.logger.info(
            "Registry loaded: %s rulebooks, %s instruments (dir=%s rb_csv=%s inst_csv=%s)",
            len(self._rulebooks),
            len(self._instruments),
            REGISTRY_DIR,
            rb_csv.exists(),
            inst_csv.exists(),
        )
        if not rb_csv.exists() or not inst_csv.exists():
            self.logger.warning(
                "V40 registry CSV missing under %s — founding_registry fallback only. "
                "Ensure Docker image COPYs registry/ (see docker/Dockerfile).",
                REGISTRY_DIR,
            )

    def _load_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _load_rulebooks(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        # CSV registry
        for row in self._load_csv(REGISTRY_DIR / "AEGIS_OPERATIONAL_RULEBOOK_REGISTRY.csv"):
            out.append(
                {
                    "rulebook_id": row.get("rulebook_id") or row.get("id") or "",
                    "family": row.get("family") or row.get("source_family") or "",
                    "asset_class": row.get("asset_class") or "FOREX",
                    "instrument": (row.get("instrument") or "").upper(),
                    "timeframe": (row.get("timeframe") or "M5").upper(),
                    "description": row.get("description") or row.get("thesis") or "",
                    "status": row.get("status") or row.get("qualification_status") or "",
                    "validation_trades": row.get("validation_trades"),
                    "validation_pf": row.get("validation_pf"),
                    "final_test_trades": row.get("final_test_trades"),
                    "final_test_pf": row.get("final_test_pf"),
                    "source": "csv_registry",
                }
            )
        # founding_registry intentionally NOT merged (research archived)
        # Dedup by rulebook_id
        seen: set[str] = set()
        deduped = []
        for r in out:
            rid = str(r.get("rulebook_id") or r.get("id") or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            deduped.append(r)
        return deduped

    def _load_instruments(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self._load_csv(REGISTRY_DIR / "AEGIS_OPERATIONAL_INSTRUMENT_REGISTRY.csv"):
            inst = (row.get("instrument") or "").upper()
            if not inst:
                continue
            router_status = (row.get("router_status") or "").upper()
            tradeable = router_status in {"TRADING_ENABLED", "LIVE"}  # RESEARCH_ELIGIBLE is not operational
            reg_status = (row.get("registry_status") or "").upper()
            # "Good" = research/live path allowed; V2-OPT-only pairs are not Good
            good = tradeable and "V2OPT_INSUFFICIENT" not in reg_status
            eligible = [
                x.strip()
                for x in (row.get("eligible_rulebooks") or "").split(";")
                if x.strip() and x.strip().lower() != "nan" and "V2OPT" not in x.upper()
            ]
            out.append(
                {
                    "instrument": inst,
                    "asset_class": row.get("asset_class") or "FOREX",
                    "timeframe": (row.get("timeframe") or "M5").upper(),
                    "registry_status": row.get("registry_status") or "",
                    "router_status": router_status,
                    "tradeable": tradeable,
                    "good": good,
                    "eligible_rulebooks": eligible,
                    "reason": row.get("reason") or "",
                }
            )
        # FAIL-CLOSED: never derive instruments from rulebook rows
        return out

    def list_rulebooks(self, instrument: str | None = None, timeframe: str | None = None) -> list[dict[str, Any]]:
        rows = self._rulebooks
        if instrument:
            rows = [r for r in rows if (r.get("instrument") or "").upper() == instrument.upper()]
        if timeframe:
            rows = [r for r in rows if (r.get("timeframe") or "").upper() == timeframe.upper()]
        return rows

    def list_instruments(self, tradeable_only: bool = False) -> list[dict[str, Any]]:
        rows = self._instruments
        if tradeable_only:
            rows = [r for r in rows if r.get("tradeable")]
        return rows

    def get_rulebook(self, rulebook_id: str) -> dict[str, Any] | None:
        for r in self._rulebooks:
            if str(r.get("rulebook_id") or r.get("id")) == rulebook_id:
                return r
        return None

    def get_active_bundle(self) -> dict[str, Any]:
        """What mobile/portal used to call 'active templates' — now registry snapshot."""
        ptr = self.get_active_pointer()
        all_inst = self.list_instruments(tradeable_only=False)
        tradeable = [r for r in all_inst if r.get("tradeable")]
        blocked = [r for r in all_inst if not r.get("tradeable")]
        return {
            "mode": "rulebook_and_pairs_registry",
            "indicators_required": False,
            "indicator_stack": None,
            "message": (
                "No MT5 indicators required. Charts are plain price. "
                "Full instrument registry is listed; only tradeable pairs may execute research/live paths."
            ),
            "active": ptr,
            "tradeable_pairs": [t["instrument"] for t in tradeable],
            "blocked_pairs": [t["instrument"] for t in blocked],
            "instruments": all_inst,
            "instrument_count": len(all_inst),
            "tradeable_count": len(tradeable),
            "rulebook_count": len(self._rulebooks),
        }

    def get_active_pointer(self) -> dict[str, Any]:
        """Stale active_profile.json cannot authorize trading when registries are empty."""
        base = {
            "rulebook_version": None,
            "registry_version": "operational",
            "indicators_required": False,
            "production_authorized": False,
            "execution_authorized": False,
            "active": False,
            "rulebook_count": len(self._rulebooks),
            "tradeable_instrument_count": len([x for x in self._instruments if x.get("tradeable")]),
            "notes": (
                "No approved operational strategy is active. "
                "Research strategies are archived. Trading is disabled."
            ),
        }
        path = TEMPLATES_DIR / "active_profile.json"
        if path.exists() and self._rulebooks:
            try:
                data = json.loads(path.read_text())
                rid = data.get("rulebook_version") or data.get("active_rulebook")
                if rid and self.get_rulebook(str(rid)):
                    base.update({
                        "rulebook_version": rid,
                        "registry_version": data.get("registry_version") or "operational",
                        "activated_at": data.get("activated_at"),
                        "active": True,
                        "notes": data.get("notes") or base["notes"],
                    })
            except Exception:
                pass
        return base

    def activate(self, rulebook_version: str, registry_version: str = "operational") -> dict[str, Any]:
        """Refuse activation unless the rulebook is present in the operational registry."""
        if not rulebook_version or not self.get_rulebook(rulebook_version):
            raise ValueError(
                "ACTIVATION_REJECTED: rulebook is not in the operational registry "
                f"(id={rulebook_version!r}). Research/archived rulebooks cannot be activated. "
                "production_authorized=false execution_authorized=false"
            )
        if not any(x.get("tradeable") for x in self._instruments):
            raise ValueError(
                "ACTIVATION_REJECTED: no tradeable instruments in the operational registry. "
                "production_authorized=false execution_authorized=false"
            )
        ptr = {
            "rulebook_version": rulebook_version,
            "registry_version": registry_version,
            "indicators_required": False,
            "production_authorized": False,
            "execution_authorized": False,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Activation recorded against operational registry only.",
        }
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        (TEMPLATES_DIR / "active_profile.json").write_text(json.dumps(ptr, indent=2))
        return ptr


# Back-compat alias so old imports of TemplateProfileService still construct something useful
class TemplateProfileService(RegistryService):
    """Deprecated name — use RegistryService. Keeps indicator APIs returning empty/disabled."""

    def list_indicator_stacks(self) -> list[dict[str, Any]]:
        return []

    def get_indicator_stack(self, version: str) -> dict[str, Any]:
        return {
            "version": version,
            "status": "retired",
            "install_order": [],
            "message": "Indicator stacks retired. No MT5 indicators required.",
        }

    def activate(self, indicator_stack_version: str, rulebook_version: str) -> dict[str, Any]:  # type: ignore[override]
        # Ignore indicator_stack_version
        return RegistryService.activate(self, rulebook_version=rulebook_version)
