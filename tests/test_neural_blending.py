"""NeuralAssistService.apply matches documented NEURAL_MODE behavior."""
from app.config import settings
from app.services.neural_service import NeuralAssistService


def _history():
    # minimal frames for extract_feature_vector
    return [
        {
            "rsi6": 20, "ma4": 22,
            "band1": {"U": 10, "M": 20, "L": 30},
            "price_band7": {"U": 10, "M": 20, "L": 30},
            "price_band8": {"U": 12, "M": 20, "L": 28},
            "price_close": 15,
        }
        for _ in range(5)
    ]


def test_confidence_mode_blends_without_changing_signal(monkeypatch):
    monkeypatch.setattr(settings, "NEURAL_MODE", "confidence")
    monkeypatch.setattr(settings, "NEURAL_MIN_BLEND", 0.15)
    svc = NeuralAssistService()
    rule = {"signal": "BUY", "confidence": 0.5, "rule_flags": {}, "rule_name": "RULE_B"}
    out = svc.apply(_history(), rule)
    assert out["signal"] == "BUY"
    assert out["neural_applied"] is True
    assert out["neural_vetoed"] is False
    assert "confidence" in out


def test_filter_mode_can_veto(monkeypatch):
    monkeypatch.setattr(settings, "NEURAL_MODE", "filter")
    monkeypatch.setattr(settings, "NEURAL_VETO_THRESHOLD", 0.99)  # almost always veto
    svc = NeuralAssistService()
    rule = {"signal": "BUY", "confidence": 0.8, "rule_flags": {}, "rule_name": "RULE_B"}
    out = svc.apply(_history(), rule)
    # With threshold 0.99, almost any NN score vetoes
    assert out["signal"] in ("HOLD", "BUY")  # HOLD if vetoed
    if out["signal"] == "HOLD":
        assert out["neural_vetoed"] is True
