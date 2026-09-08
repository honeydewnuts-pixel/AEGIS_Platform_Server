"""AEGIS Neural v3 teacher-confidence layer (v2.3.6.6).

Documented modes (config.NEURAL_MODE):
  confidence / v3_teacher_confidence — blend NN score into rule confidence
  filter — veto weak rule fires → HOLD when NN direction score < veto threshold
  hybrid — both veto and blend
Rules remain the source of the signal except when filter/hybrid vetoes to HOLD.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.logging import configure_logging
from app.services.neural_features_v3 import FEATURE_DIM, extract_feature_vector

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "aegis_neural_v3_2.3.6.6.json"


def _softmax(values):
    m = max(values)
    ex = [math.exp(v - m) for v in values]
    s = sum(ex) or 1.0
    return [v / s for v in ex]


class NeuralAssistService:
    def __init__(self):
        self.logger = configure_logging(__name__)
        self.model = self._load_model()
        if self.model.get("feature_dim") != FEATURE_DIM:
            raise ValueError("v3 neural feature dimension mismatch")
        self.logger.info("AEGIS Neural v3 loaded from %s", MODEL_PATH)

    def _load_model(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(MODEL_PATH)
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))

    def _predict(self, vector):
        if len(vector) != FEATURE_DIM:
            raise ValueError(f"Expected {FEATURE_DIM} features, got {len(vector)}")
        norm = self.model["normalization"]
        mean = norm["mean"]
        std = norm["std"]
        x = []
        for v, m, s in zip(vector, mean, std):
            if v is None or not math.isfinite(float(v)):
                v = float(m)
            x.append((float(v) - float(m)) / max(float(s), 1e-6))
        for layer in self.model["layers"]:
            x = [
                sum(wi * xi for wi, xi in zip(row, x)) + bi
                for row, bi in zip(layer["weight"], layer["bias"])
            ]
            if layer.get("activation") == "tanh":
                x = [math.tanh(v) for v in x]
        return dict(zip(self.model["classes"], _softmax(x)))

    def apply(self, history, rule_result):
        flags = rule_result.get("rule_flags", {})
        feats = extract_feature_vector(history, flags)
        probs = self._predict(feats["vector"])
        rule_signal = (rule_result.get("signal") or "HOLD").upper()
        mode = (getattr(settings, "NEURAL_MODE", None) or "v3_teacher_confidence").lower()
        veto_thr = float(getattr(settings, "NEURAL_VETO_THRESHOLD", 0.35) or 0.35)
        min_blend = float(getattr(settings, "NEURAL_MIN_BLEND", 0.15) or 0.15)

        out = dict(rule_result)
        out.update(
            {
                "neural_model_version": self.model.get("version", "AEGIS_NEURAL_V3_2.3.6.6"),
                "neural_architecture": self.model.get("architecture"),
                "neural_feature_dim": FEATURE_DIM,
                "neural_probabilities": {k: round(v, 4) for k, v in probs.items()},
                "neural_signal": max(probs, key=probs.get),
                "neural_score": round(max(probs.get("BUY", 0), probs.get("SELL", 0)), 4),
                "neural_applied": True,
                "neural_mode": mode,
                "feature_completeness": round(feats["completeness"], 4),
                "neural_vetoed": False,
            }
        )

        fired = rule_signal in ("BUY", "SELL")
        direction_score = float(probs.get(rule_signal, 0.0)) if fired else 0.0
        nn_score = float(max(probs.get("BUY", 0.0), probs.get("SELL", 0.0)))

        # filter / hybrid: veto weak rule fires → HOLD
        if mode in ("filter", "hybrid") and fired and direction_score < veto_thr:
            out["signal"] = "HOLD"
            out["rule_name"] = f"{out.get('rule_name', out.get('rule', 'rule'))}+neural_veto"
            out["details"] = (
                f"{out.get('details', '')} | neural {rule_signal.lower()} "
                f"probability={direction_score:.2f} < {veto_thr:.2f}"
            ).strip(" |")
            out["neural_vetoed"] = True
            fired = False

        # confidence / hybrid / v3_teacher_confidence: blend NN into confidence
        if mode in ("confidence", "hybrid", "v3_teacher_confidence") and not out["neural_vetoed"]:
            if fired:
                rule_conf = float(out.get("confidence") or 0.0)
                # Documented blend: weighted mix of rule confidence and NN direction score
                blended = max(min_blend, min(0.99, 0.55 * rule_conf + 0.45 * direction_score))
                out["confidence"] = round(max(rule_conf, blended), 4)
            else:
                out["confidence"] = round(
                    max(float(out.get("confidence") or 0.0), min_blend * nn_score), 4
                )

        return out
