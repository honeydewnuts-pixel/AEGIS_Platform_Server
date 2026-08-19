"""
Phase B — Neural assist layer (confidence / filter).

Uses a compact logistic-style scorer over Phase A features.
Weights are fixed (hand-initialized, L2-normalized intent) so Render needs
no PyTorch/TF. Replace `score()` with ONNX later without changing the API.

Modes (Settings.NEURAL_MODE):
  off        — no change to rule output
  confidence — blend neural score into confidence
  filter     — veto weak rule fires → HOLD
  hybrid     — filter + confidence (default)
"""

from __future__ import annotations

import math
from typing import Any

from app.config import settings
from app.core.logging import configure_logging
from app.services.neural_features import FEATURE_DIM, extract_feature_vector


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


class NeuralAssistService:
    """
    Lightweight 'network': y = σ(w·x + b).
    Positive weights favour clean band geometry + completeness.
    """

    def __init__(self) -> None:
        self.logger = configure_logging(__name__)
        # Dim must match FEATURE_DIM
        self.weights = [
            0.35,   # n_frames
            1.20,   # bands_ok
            0.25,   # b1_width
            0.25,   # b2_width
            0.05,   # b1_mid
            0.05,   # b2_mid
            0.40,   # band_mid_delta magnitude later via abs in features? keep linear
            0.15,   # ma4
            0.15,   # cci5
            0.15,   # rsi6
            0.10,   # williams3
            0.30,   # ma4_vs_b1m
            0.25,   # rsi_vs_b1u
            0.20,   # cci_vs_b1m
            0.35,   # b2m_vs_b1u
            0.10,   # price_close
            0.15,   # price_band7_mid
            0.15,   # price_band8_mid
            0.20,   # d_b1_mid
            0.20,   # d_b2_mid
            0.15,   # d_ma4
            0.15,   # d_rsi6
            0.15,   # d_cci5
            1.10,   # completeness
        ]
        assert len(self.weights) == FEATURE_DIM
        self.bias = -0.85
        self.logger.info(
            "NeuralAssistService ready mode=%s veto=%.2f",
            getattr(settings, "NEURAL_MODE", "hybrid"),
            getattr(settings, "NEURAL_VETO_THRESHOLD", 0.35),
        )

    def score(self, vector: list[float]) -> float:
        if len(vector) != FEATURE_DIM:
            return 0.0
        # Emphasize absolute mid-delta (feature index 6)
        x = list(vector)
        x[6] = abs(x[6])
        s = self.bias + sum(w * v for w, v in zip(self.weights, x))
        return float(_sigmoid(s))

    def apply(
        self,
        history: list[dict[str, Any]],
        rule_result: dict[str, Any],
    ) -> dict[str, Any]:
        mode = (getattr(settings, "NEURAL_MODE", "hybrid") or "off").strip().lower()
        feats = extract_feature_vector(history)
        nn = self.score(feats["vector"])
        veto_thr = float(getattr(settings, "NEURAL_VETO_THRESHOLD", 0.35))
        min_blend = float(getattr(settings, "NEURAL_MIN_BLEND", 0.15))

        out = dict(rule_result)
        out["neural_score"] = round(nn, 4)
        out["neural_mode"] = mode
        out["feature_completeness"] = round(feats["completeness"], 4)
        out["bands_detected"] = feats["bands_ok"]

        if mode in ("off", "", "none"):
            out["neural_applied"] = False
            return out

        signal = (out.get("signal") or "HOLD").upper()
        rule_conf = float(out.get("confidence") or 0.0)
        fired = signal in ("BUY", "SELL") and rule_conf > 0

        vetoed = False
        if mode in ("filter", "hybrid") and fired and nn < veto_thr:
            out["signal"] = "HOLD"
            out["confidence"] = round(max(min_blend, nn * 0.5), 4)
            out["rule_name"] = f"{out.get('rule_name', 'rule')}+neural_veto"
            out["details"] = (
                f"{out.get('details', '')} | neural veto score={nn:.2f} < {veto_thr:.2f}"
            )
            vetoed = True

        if mode in ("confidence", "hybrid") and not vetoed:
            if fired:
                # Blend rule confidence with neural score
                blended = 0.55 * rule_conf + 0.45 * nn
                out["confidence"] = round(max(min_blend, min(0.99, blended)), 4)
            else:
                # Soft confidence for HOLD / warming
                out["confidence"] = round(
                    max(float(out.get("confidence") or 0.0), min_blend * nn),
                    4,
                )

        out["neural_applied"] = True
        out["neural_vetoed"] = vetoed
        return out
