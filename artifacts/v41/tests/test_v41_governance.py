from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'governance' / 'AEGIS_V41_STATUS.md'
DATA = ROOT / 'forward' / 'AEGIS_V41_FORWARD_DATA_STATUS.csv'


def test_forward_boundary_and_status():
    text = STATUS.read_text()
    assert 'NO_NEW_DATA' in text
    assert '2026-08-28 16:55:00' in text


def test_six_candidates_are_locked_and_data_limited():
    rows = list(csv.DictReader(DATA.open()))
    assert len(rows) == 6
    assert {r['status'] for r in rows} == {'NO_NEW_DATA'}
    assert {r['instrument'] for r in rows} == {'AUDUSD','USDCHF','NZDUSD'}
    assert {r['rulebook'] for r in rows} == {'V31','V35'}
