import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    with open(ROOT / 'registry' / name, newline='') as f:
        return list(csv.DictReader(f))


def test_six_qualified_candidates():
    rows = load('AEGIS_V40_RULEBOOK_REGISTRY.csv')
    assert len(rows) == 6
    assert all(r['status'] == 'QUALIFIED_RESEARCH_CANDIDATE' for r in rows)
    assert all(float(r['validation_trades']) >= 300 for r in rows)
    assert all(float(r['validation_pf']) > 1.60 for r in rows)
    assert all(float(r['final_test_trades']) >= 300 for r in rows)
    assert all(float(r['final_test_pf']) > 1.60 for r in rows)
    assert all(float(r['min_six_block_pf']) > 1.0 for r in rows)
    assert all(r['independent_reproduction'] == 'true' for r in rows)
    assert all(r['production_authorized'] == 'false' for r in rows)


def test_disabled_instruments_fail_closed():
    rows = load('AEGIS_V40_INSTRUMENT_REGISTRY.csv')
    disabled = {r['instrument'] for r in rows if r['router_status'] == 'TRADING_DISABLED'}
    assert {'EURUSD', 'USDJPY', 'EURJPY', 'GBPJPY'} <= disabled
