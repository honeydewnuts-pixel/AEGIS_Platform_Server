from pathlib import Path
import numpy as np
import pandas as pd
from app.rulebooks.causal import CausalRulebookEvaluator

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'backend/app/data/research/AEGIS_V37_STANDARDIZED_GBPUSD_5M.csv'
REF = ROOT / 'backend/app/data/research'
V31='AEGIS-RB-V31-GBPUSD-5M'; V35='AEGIS-RB-V35-GBPUSD-5M'


def _assert_ledger_close(actual, expected):
    fields=['event_i','exit_i','reason','signal_datetime','entry_datetime','exit_datetime','duration_bars']
    for f in fields:
        assert actual[f].astype(str).tolist() == expected[f].astype(str).tolist(), f
    for f in ['entry','exit','R']:
        np.testing.assert_allclose(actual[f].to_numpy(float), expected[f].to_numpy(float), rtol=0, atol=5e-13, err_msg=f)


def test_v31_causal_reproduction():
    e=CausalRulebookEvaluator(DATA).evaluate(V31)
    ref=pd.read_csv(REF/'AEGIS_V37_V31_REFERENCE_REPLAY.csv')
    assert len(e.signals)==2825
    assert len(e.trades)==2600
    _assert_ledger_close(e.trades, ref)
    assert abs(e.metrics['PF']-1.4803553737250497)<5e-13


def test_v35_causal_reproduction():
    e=CausalRulebookEvaluator(DATA).evaluate(V35)
    ref=pd.read_csv(REF/'AEGIS_V37_V35_REFERENCE_REPLAY.csv')
    assert len(e.signals)==2238
    assert len(e.trades)==2060
    _assert_ledger_close(e.trades, ref)
    assert abs(e.metrics['PF']-1.7018831432004435)<5e-13


def test_unknown_rulebook_fails_closed():
    evaluator=CausalRulebookEvaluator(DATA)
    try:
        evaluator.evaluate('AEGIS-RB-UNKNOWN')
    except ValueError as exc:
        assert str(exc)=='NO_QUALIFIED_RULEBOOK'
    else:
        raise AssertionError('unknown rulebook did not fail closed')
