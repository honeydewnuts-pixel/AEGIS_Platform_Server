from app.services.neural_features import extract_feature_vector, FEATURE_DIM
from app.services.neural_service import NeuralAssistService


def _frame(i=0):
    return {
        "band1": {"U": 40+i, "M": 80+i, "L": 120+i},
        "band2": {"U": 45+i, "M": 85+i, "L": 125+i},
        "ma4": 95+i,
        "cci5": 100+i,
        "rsi6": 90+i,
        "williams3": 110+i,
        "price_close": 100-i,
        "price_band7": {"U": 50+i, "M": 100+i, "L": 150+i},
        "price_band8": {"U": 45+i, "M": 95+i, "L": 145+i},
    }


def test_feature_vector_length_v2():
    feats = extract_feature_vector([_frame(i) for i in range(12)])
    assert len(feats["vector"]) == FEATURE_DIM == 68
    assert len(feats["names"]) == 68


def test_neural_v2_inference():
    svc = NeuralAssistService()
    history = [_frame(i) for i in range(12)]
    out = svc.apply(history, {
        "signal": "BUY",
        "confidence": 0.85,
        "rule_name": "v2_test",
        "details": "test",
    })
    assert out["neural_model_version"] == "AEGIS_NEURAL_V2"
    assert 0.0 <= out["neural_score"] <= 1.0
    assert set(out["neural_probabilities"]) == {"HOLD", "SELL", "BUY"}
