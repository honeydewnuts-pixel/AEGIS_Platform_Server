from __future__ import annotations
from pathlib import Path
from .evaluators import EVALUATORS
from .evaluators.common import load_v37_dataset

class CausalRulebookEvaluator:
    """Server-side causal evaluator; reference ledgers are never used here."""
    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)
        self.df = load_v37_dataset(self.dataset_path)

    def evaluate(self, rulebook_id: str):
        fn = EVALUATORS.get(rulebook_id)
        if fn is None:
            raise ValueError("NO_QUALIFIED_RULEBOOK")
        return fn(self.df)
