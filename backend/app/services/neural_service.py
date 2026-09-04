"""AEGIS Neural v3 teacher-confidence layer (v2.3.6.6)."""
from __future__ import annotations
import json, math
from pathlib import Path
from typing import Any
from app.config import settings
from app.core.logging import configure_logging
from app.services.neural_features_v3 import FEATURE_DIM, extract_feature_vector

MODEL_PATH=Path(__file__).resolve().parent.parent/"models"/"aegis_neural_v3_2.3.6.6.json"

def _softmax(values):
    m=max(values); ex=[math.exp(v-m) for v in values]; s=sum(ex) or 1.0; return [v/s for v in ex]

class NeuralAssistService:
    def __init__(self):
        self.logger=configure_logging(__name__); self.model=self._load_model()
        if self.model.get("feature_dim")!=FEATURE_DIM: raise ValueError("v3 neural feature dimension mismatch")
        self.logger.info("AEGIS Neural v3 loaded from %s",MODEL_PATH)
    def _load_model(self):
        if not MODEL_PATH.exists(): raise FileNotFoundError(MODEL_PATH)
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    def _predict(self, vector):
        if len(vector)!=FEATURE_DIM: raise ValueError(f"Expected {FEATURE_DIM} features, got {len(vector)}")
        norm=self.model["normalization"]; mean=norm["mean"]; std=norm["std"]
        x=[]
        for v,m,s in zip(vector,mean,std):
            if v is None or not math.isfinite(float(v)): v=float(m)
            x.append((float(v)-float(m))/max(float(s),1e-6))
        for layer in self.model["layers"]:
            x=[sum(wi*xi for wi,xi in zip(row,x))+bi for row,bi in zip(layer["weight"],layer["bias"])]
            if layer.get("activation")=="tanh": x=[math.tanh(v) for v in x]
        return dict(zip(self.model["classes"],_softmax(x)))
    def apply(self,history,rule_result):
        flags=rule_result.get("rule_flags",{})
        feats=extract_feature_vector(history,flags); probs=self._predict(feats["vector"])
        rule_signal=(rule_result.get("signal") or "HOLD").upper()
        out=dict(rule_result); out.update({
            "neural_model_version":self.model.get("version","AEGIS_NEURAL_V3_2.3.6.6"),
            "neural_architecture":self.model.get("architecture"),
            "neural_feature_dim":FEATURE_DIM,
            "neural_probabilities":{k:round(v,4) for k,v in probs.items()},
            "neural_signal":max(probs,key=probs.get),
            "neural_score":round(max(probs.get("BUY",0),probs.get("SELL",0)),4),
            "neural_applied":True,
            "neural_mode":"v3_teacher_confidence",
            "feature_completeness":round(feats["completeness"],4),
        })
        # v3 deterministic rule engine remains authoritative. Neural never vetoes
        # or changes a v3 BUY/SELL/HOLD decision.
        if rule_signal in ("BUY","SELL"):
            out["confidence"]=round(max(float(out.get("confidence") or 0.0), float(probs.get(rule_signal,0.0))),4)
        return out
