"""Adversarial fail-closed tests for operational registry + active profile."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def isolated_registry(tmp_path, monkeypatch):
    """Point RegistryService at temporary operational CSVs and templates."""
    import sys
    sys.path.insert(0, str(ROOT / "backend"))

    op = tmp_path / "operational"
    op.mkdir()
    templates = tmp_path / "templates"
    templates.mkdir()

    rb_csv = op / "AEGIS_OPERATIONAL_RULEBOOK_REGISTRY.csv"
    inst_csv = op / "AEGIS_OPERATIONAL_INSTRUMENT_REGISTRY.csv"
    rb_csv.write_text(
        "rulebook_id,source_rulebook_id,asset_class,instrument,timeframe,"
        "mechanism_family,status,validation_trades,validation_pf,"
        "final_test_trades,final_test_pf,min_six_block_pf,"
        "independent_reproduction,production_authorized\n"
    )
    inst_csv.write_text(
        "instrument,asset_class,timeframe,registry_status,router_status,"
        "eligible_rulebooks,reason\n"
    )

    import app.services.registry_service as rs

    monkeypatch.setattr(rs, "REGISTRY_DIR", op)
    monkeypatch.setattr(rs, "OPERATIONAL_REGISTRY_DIR", op)
    monkeypatch.setattr(rs, "TEMPLATES_DIR", templates)
    # Also neutralize legacy dirs if referenced
    if hasattr(rs, "LEGACY_V40_REGISTRY_DIR"):
        monkeypatch.setattr(rs, "LEGACY_V40_REGISTRY_DIR", op)
    if hasattr(rs, "ARTIFACTS_V40_REGISTRY_DIR"):
        monkeypatch.setattr(rs, "ARTIFACTS_V40_REGISTRY_DIR", op)

    return rs, op, templates, rb_csv, inst_csv


def _write_rb(rb_csv: Path, rows: list[dict]):
    header = (
        "rulebook_id,source_rulebook_id,asset_class,instrument,timeframe,"
        "mechanism_family,status,validation_trades,validation_pf,"
        "final_test_trades,final_test_pf,min_six_block_pf,"
        "independent_reproduction,production_authorized\n"
    )
    lines = [header]
    for r in rows:
        lines.append(
            ",".join([
                r["rulebook_id"],
                r.get("source", ""),
                r.get("asset_class", "FOREX"),
                r["instrument"],
                r["timeframe"],
                r.get("family", ""),
                r.get("status", "OPERATIONAL_CANDIDATE"),
                "",
                "",
                "",
                "",
                "",
                "False",
                "False",
            ])
            + "\n"
        )
    rb_csv.write_text("".join(lines))


def _write_inst(inst_csv: Path, rows: list[dict]):
    header = (
        "instrument,asset_class,timeframe,registry_status,router_status,"
        "eligible_rulebooks,reason\n"
    )
    lines = [header]
    for r in rows:
        lines.append(
            f"{r['instrument']},{r.get('asset_class','FOREX')},{r['timeframe']},"
            f"{r.get('registry_status','')},{r['router_status']},"
            f"{r.get('eligible','')},{r.get('reason','')}\n"
        )
    inst_csv.write_text("".join(lines))


def test_both_csvs_empty(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    svc = rs.RegistryService()
    assert svc.list_rulebooks() == []
    assert svc.list_instruments() == []
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["production_authorized"] is False
    assert ptr["execution_authorized"] is False


def test_rulebook_exists_instrument_empty(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_rb(rb_csv, [{
        "rulebook_id": "RB-TEST-1", "instrument": "EURUSD", "timeframe": "M5",
    }])
    svc = rs.RegistryService()
    assert len(svc.list_rulebooks()) == 1
    assert svc.list_instruments() == []
    templates.joinpath("active_profile.json").write_text(json.dumps({
        "rulebook_version": "RB-TEST-1",
    }))
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["blocked_reason"] == "INSTRUMENT_NOT_IN_OPERATIONAL_REGISTRY"


def test_instrument_not_tradeable(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_rb(rb_csv, [{"rulebook_id": "RB-TEST-1", "instrument": "EURUSD", "timeframe": "M5"}])
    _write_inst(inst_csv, [{
        "instrument": "EURUSD", "timeframe": "M5",
        "router_status": "RESEARCH_ELIGIBLE",
        "eligible": "RB-TEST-1",
    }])
    svc = rs.RegistryService()
    assert svc.list_instruments(tradeable_only=True) == []
    templates.joinpath("active_profile.json").write_text(json.dumps({"rulebook_version": "RB-TEST-1"}))
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["blocked_reason"] == "INSTRUMENT_NOT_TRADEABLE"


def test_research_eligible_never_tradeable(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_inst(inst_csv, [{
        "instrument": "GBPUSD", "timeframe": "M5",
        "router_status": "RESEARCH_ELIGIBLE",
        "eligible": "ANY",
    }])
    svc = rs.RegistryService()
    assert svc.list_instruments(tradeable_only=True) == []
    all_inst = svc.list_instruments(tradeable_only=False)
    assert len(all_inst) == 1
    assert all_inst[0]["tradeable"] is False


def test_instrument_tradeable_but_rulebook_not_eligible(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_rb(rb_csv, [{"rulebook_id": "RB-TEST-1", "instrument": "EURUSD", "timeframe": "M5"}])
    _write_inst(inst_csv, [{
        "instrument": "EURUSD", "timeframe": "M5",
        "router_status": "TRADING_ENABLED",
        "eligible": "RB-OTHER",
    }])
    svc = rs.RegistryService()
    templates.joinpath("active_profile.json").write_text(json.dumps({"rulebook_version": "RB-TEST-1"}))
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["blocked_reason"] == "RULEBOOK_NOT_IN_INSTRUMENT_ELIGIBLE_LIST"


def test_timeframe_mismatch(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_rb(rb_csv, [{"rulebook_id": "RB-TEST-1", "instrument": "EURUSD", "timeframe": "M5"}])
    _write_inst(inst_csv, [{
        "instrument": "EURUSD", "timeframe": "M15",
        "router_status": "TRADING_ENABLED",
        "eligible": "RB-TEST-1",
    }])
    svc = rs.RegistryService()
    templates.joinpath("active_profile.json").write_text(json.dumps({"rulebook_version": "RB-TEST-1"}))
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["blocked_reason"] in {
        "TIMEFRAME_OR_ASSOCIATION_MISMATCH",
        "INSTRUMENT_NOT_IN_OPERATIONAL_REGISTRY",
        "RULEBOOK_NOT_IN_INSTRUMENT_ELIGIBLE_LIST",
    }


def test_stale_profile_archived_rulebook(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    templates.joinpath("active_profile.json").write_text(json.dumps({
        "rulebook_version": "AEGIS-RB-V31-GBPUSD-5M",
    }))
    svc = rs.RegistryService()
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["blocked_reason"] == "RULEBOOK_NOT_IN_OPERATIONAL_REGISTRY"


def test_stale_profile_valid_rb_no_tradeable_instrument(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_rb(rb_csv, [{"rulebook_id": "RB-TEST-1", "instrument": "EURUSD", "timeframe": "M5"}])
    templates.joinpath("active_profile.json").write_text(json.dumps({"rulebook_version": "RB-TEST-1"}))
    svc = rs.RegistryService()
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False
    assert ptr["production_authorized"] is False
    assert ptr["execution_authorized"] is False


def test_valid_association_active_but_auth_flags_false(isolated_registry):
    """Positive path: consistent association may be active; flags stay false."""
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    _write_rb(rb_csv, [{"rulebook_id": "RB-TEST-1", "instrument": "EURUSD", "timeframe": "M5"}])
    _write_inst(inst_csv, [{
        "instrument": "EURUSD", "timeframe": "M5",
        "router_status": "TRADING_ENABLED",
        "eligible": "RB-TEST-1",
    }])
    templates.joinpath("active_profile.json").write_text(json.dumps({
        "rulebook_version": "RB-TEST-1",
        "registry_version": "operational",
    }))
    svc = rs.RegistryService()
    assert len(svc.list_rulebooks()) == 1
    assert len(svc.list_instruments(tradeable_only=True)) == 1
    ptr = svc.get_active_pointer()
    assert ptr["active"] is True
    assert ptr["production_authorized"] is False
    assert ptr["execution_authorized"] is False
    assert ptr.get("blocked_reason") is None
    assert ptr["instrument"] == "EURUSD"


def test_missing_csv_no_legacy_fallback(isolated_registry, monkeypatch):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    rb_csv.unlink()
    inst_csv.unlink()
    svc = rs.RegistryService()
    assert svc.list_rulebooks() == []
    assert svc.list_instruments() == []
    ptr = svc.get_active_pointer()
    assert ptr["active"] is False


def test_activate_rejected_empty(isolated_registry):
    rs, op, templates, rb_csv, inst_csv = isolated_registry
    svc = rs.RegistryService()
    with pytest.raises(ValueError, match="ACTIVATION_REJECTED"):
        svc.activate("AEGIS-RB-V31-GBPUSD-5M")


def test_founding_registry_still_empty():
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.rulebooks.registry import founding_registry
    assert founding_registry().count() == 0
    assert founding_registry().get("AEGIS-RB-V31-GBPUSD-5M") is None
