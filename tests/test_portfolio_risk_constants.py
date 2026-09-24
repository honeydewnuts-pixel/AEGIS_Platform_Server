from app.services.portfolio_risk_service import ALLOWED_TOLERANCE_PCT, MAX_MULTISYMBOL_PAIRS

def test_tolerance_ladder():
    assert ALLOWED_TOLERANCE_PCT == (5, 10, 15, 20, 25, 30, 35, 40, 45)

def test_max_pairs_cap():
    assert MAX_MULTISYMBOL_PAIRS == 24
