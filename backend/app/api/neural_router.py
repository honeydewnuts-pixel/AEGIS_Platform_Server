"""Neural diagnostics: feature-vector prediction for ops verification."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.neural_features import FEATURE_DIM
from app.services.neural_service import NeuralAssistService, MODEL_PATH

router = APIRouter(prefix="/api/neural", tags=["Neural"])

_service: NeuralAssistService | None = None


def _svc() -> NeuralAssistService:
    global _service
    if _service is None:
        _service = NeuralAssistService()
    return _service


class PredictRequest(BaseModel):
    features: list[float] = Field(..., description=f"Length-{FEATURE_DIM} feature vector")


@router.post("/predict")
async def predict(body: PredictRequest) -> dict[str, Any]:
    if len(body.features) != FEATURE_DIM:
        raise HTTPException(
            status_code=400,
            detail=f"Expected {FEATURE_DIM} features, got {len(body.features)}",
        )
    svc = _svc()
    probs = svc._predict(body.features)
    nn_signal = max(probs, key=probs.get)
    score = float(max(probs["SELL"], probs["BUY"])) * 100.0
    return {
        "score": round(score, 2),
        "signal": nn_signal,
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "model_version": svc.model.get("version"),
        "architecture": svc.model.get("architecture"),
        "feature_dim": FEATURE_DIM,
        "model_path": str(MODEL_PATH.name),
    }


@router.get("/info")
async def info() -> dict[str, Any]:
    svc = _svc()
    return {
        "model_version": svc.model.get("version"),
        "architecture": svc.model.get("architecture"),
        "feature_dim": FEATURE_DIM,
        "classes": svc.model.get("classes"),
        "training_samples": svc.model.get("training_samples"),
        "holdout_direction_agreement": svc.model.get("holdout_direction_agreement"),
        "model_file": MODEL_PATH.name,
        "exists": MODEL_PATH.exists(),
    }
