"""Compatibility shim — v2 path archived; re-export v3 feature API for older imports."""
from app.services.neural_features_v3 import FEATURE_DIM, extract_feature_vector

__all__ = ["FEATURE_DIM", "extract_feature_vector"]
