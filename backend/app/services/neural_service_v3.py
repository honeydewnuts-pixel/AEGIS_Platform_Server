"""AEGIS Neural v3 inference layer.

Same pure-Python JSON-weights approach as neural_service.py (no
PyTorch/TensorFlow runtime needed in production), pointed at the v3
feature extractor and v3-trained model file.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.logging import configure_logging
from app.services.neural_features_v3 import FEATURE_DIM, extract_feature_vector

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "aegis_neural_v3.json"


def _softmax(values: list[float]) -> list[float]:
    m = max(values)
    ex = [math.exp(v - m) for v in values]
    s = sum(ex) or 1.0
    return [v / s for v in ex]


class NeuralAssistServiceV3:
    """Pure-Python inference for the trained AEGIS Neural v3 MLP."""

    def __init__(self) -> None:
        self.logger = configure_logging(__name__)
        self.model = self._load_model()
        if self.model.get("feature_dim") != FEATURE_DIM:
            raise ValueError(f"Neural v3 model feature_dim mismatch: {self.model.get('feature_dim')} != {FEATURE_DIM}")
        self.logger.info("AEGIS Neural v3 loaded from %s", MODEL_PATH)

    def _load_model(self) -> dict[str, Any]:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Neural v3 model not found: {MODEL_PATH}")
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def _predict(self, vector: list[float]) -> dict[str, float]:
        if len(vector) != FEATURE_DIM:
            raise ValueError(f"Expected {FEATURE_DIM} features, got {len(vector)}")
        norm = self.model["normalization"]
        mean = norm["mean"]
        std = norm["std"]
        x = [(float(v) - float(m)) / max(float(s), 1e-6) for v, m, s in zip(vector, mean, std)]
        for layer in self.model["layers"]:
            w = layer["weight"]
            b = layer["bias"]
            x = [sum(wi * xi for wi, xi in zip(row, x)) + bi for row, bi in zip(w, b)]
            if layer.get("activation") == "tanh":
                x = [math.tanh(v) for v in x]
        probs = _softmax(x)
        return dict(zip(self.model["classes"], probs))

    def score(self, vector: list[float]) -> float:
        probs = self._predict(vector)
        return float(max(probs["SELL"], probs["BUY"]))

    def apply(self, history: list[dict[str, Any]], rule_result: dict[str, Any]) -> dict[str, Any]:
        mode = (getattr(settings, "NEURAL_MODE", "hybrid") or "off").strip().lower()
        feats = extract_feature_vector(history)
        probs = self._predict(feats["vector"])
        signal = (rule_result.get("signal") or "HOLD").upper()
        direction_score = probs.get(signal, probs["HOLD"]) if signal in ("BUY", "SELL") else max(probs["BUY"], probs["SELL"])
        nn_signal = max(("BUY", probs["BUY"]), ("SELL", probs["SELL"]), key=lambda x: x[1])[0]
        nn_score = max(probs["BUY"], probs["SELL"])
        veto_thr = float(getattr(settings, "NEURAL_VETO_THRESHOLD", 0.35))
        min_blend = float(getattr(settings, "NEURAL_MIN_BLEND", 0.15))

        out = dict(rule_result)
        out.update({
            "neural_score": round(nn_score, 4),
            "neural_signal": nn_signal,
            "neural_probabilities": {k: round(v, 4) for k, v in probs.items()},
            "neural_mode": mode,
            "feature_completeness": round(feats["completeness"], 4),
            "bands_detected": feats["bands_ok"],
            "neural_model_version": self.model.get("version", "AEGIS_NEURAL_V3"),
        })

        if mode in ("off", "", "none"):
            out["neural_applied"] = False
            return out

        fired = signal in ("BUY", "SELL") and float(out.get("confidence") or 0.0) > 0
        vetoed = False
        if mode in ("filter", "hybrid") and fired and direction_score < veto_thr:
            out["signal"] = "HOLD"
            out["confidence"] = round(max(min_blend, direction_score * 0.5), 4)
            out["rule_name"] = f"{out.get('rule_name', 'rule')}+neural_veto"
            out["details"] = f"{out.get('details', '')} | neural {signal.lower()} probability={direction_score:.2f} < {veto_thr:.2f}"
            vetoed = True

        if mode in ("confidence", "hybrid") and not vetoed and fired:
            rule_conf = float(out.get("confidence") or 0.0)
            out["confidence"] = round(max(min_blend, min(0.99, 0.55 * rule_conf + 0.45 * direction_score)), 4)
        elif not fired:
            out["confidence"] = round(max(float(out.get("confidence") or 0.0), min_blend * nn_score), 4)

        out["neural_applied"] = True
        out["neural_vetoed"] = vetoed
        return out


def get_neural_with_fallback():
    """Primary Neural v3; seamless fallback to Neural v2 on load/predict failure."""
    try:
        return NeuralAssistServiceV3(), "v3"
    except Exception:
        from app.services.neural_service import NeuralAssistService
        return NeuralAssistService(), "v2"
