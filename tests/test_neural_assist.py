from app.services.neural_features import extract_feature_vector, FEATURE_DIM
from app.services.neural_service import NeuralAssistService


def test_feature_vector_length():
    history = [
        {
            "band1": {"U": 10, "M": 20, "L": 30},
            "band2": {"U": 12, "M": 22, "L": 32},
            "ma4": 18,
            "cci5": 25,
            "rsi6": 15,
            "williams3": 28,
        },
        {
            "band1": {"U": 11, "M": 21, "L": 31},
            "band2": {"U": 10, "M": 19, "L": 29},
            "ma4": 17,
            "cci5": 24,
            "rsi6": 14,
            "williams3": 27,
        },
    ]
    feats = extract_feature_vector(history)
    assert len(feats["vector"]) == FEATURE_DIM
    assert feats["bands_ok"] is True
    assert feats["completeness"] > 0.5


def test_neural_apply_confidence():
    svc = NeuralAssistService()
    history = [
        {
            "band1": {"U": 10, "M": 20, "L": 30},
            "band2": {"U": 12, "M": 22, "L": 32},
            "ma4": 18,
            "cci5": 25,
            "rsi6": 15,
            "williams3": 28,
        },
        {
            "band1": {"U": 11, "M": 21, "L": 31},
            "band2": {"U": 10, "M": 19, "L": 29},
            "ma4": 17,
            "cci5": 24,
            "rsi6": 14,
            "williams3": 27,
        },
    ]
    base = {
        "signal": "BUY",
        "confidence": 0.85,
        "rule_name": "base_buy",
        "details": "test",
        "frames_in_history": 2,
    }
    out = svc.apply(history, base)
    assert "neural_score" in out
    assert 0.0 <= out["neural_score"] <= 1.0
    assert out.get("neural_mode")
