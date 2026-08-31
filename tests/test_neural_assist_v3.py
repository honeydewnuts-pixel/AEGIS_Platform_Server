from app.services.neural_features_v3 import extract_feature_vector, FEATURE_DIM
from app.services.neural_service_v3 import NeuralAssistServiceV3


def _frame(i=0):
    return {
        "price_band7": {"U": 50 + i, "M": 100 + i, "L": 150 + i},
        "price_band8": {"U": 55 + i, "M": 105 + i, "L": 155 + i},
        "rsi6": 90 - i,
        "ma4": 95 - i,
        "band1": {"U": 40 + i, "M": 80 + i, "L": 120 + i},
    }


def test_feature_vector_length_v3():
    feats = extract_feature_vector([_frame(i) for i in range(20)])
    assert len(feats["vector"]) == FEATURE_DIM == 52
    assert len(feats["names"]) == 52


def test_feature_vector_pads_short_history():
    feats = extract_feature_vector([_frame(0)])
    assert len(feats["vector"]) == FEATURE_DIM
    assert feats["completeness"] < 1.0


def test_neural_v3_inference():
    svc = NeuralAssistServiceV3()
    history = [_frame(i) for i in range(20)]
    out = svc.apply(history, {
        "signal": "BUY",
        "confidence": 0.85,
        "rule_name": "v3_test",
        "details": "test",
    })
    assert out["neural_model_version"] == "AEGIS_NEURAL_V3"
    assert 0.0 <= out["neural_score"] <= 1.0
    assert set(out["neural_probabilities"]) == {"HOLD", "SELL", "BUY"}
