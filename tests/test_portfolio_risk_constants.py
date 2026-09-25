from app.services.portfolio_risk_service import ALLOWED_TOLERANCE_PCT, MAX_MULTISYMBOL_PAIRS

def test_tolerance_ladder():
    assert ALLOWED_TOLERANCE_PCT[0] == 0.5
    assert 1.0 in ALLOWED_TOLERANCE_PCT
    assert 2.5 in ALLOWED_TOLERANCE_PCT
    assert 50.0 in ALLOWED_TOLERANCE_PCT
    assert 5.0 in ALLOWED_TOLERANCE_PCT

def test_max_pairs_cap():
    assert MAX_MULTISYMBOL_PAIRS == 24
