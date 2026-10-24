"""ARRS Stage 2 — offline execution-aware evaluation (research-only)."""
from .data import validate_bid_ask, dataset_hash, load_bid_ask_csv
from .simulator import simulate_trades, TradeManagementTemplate
from .walkforward import chronological_partitions, walk_forward_evaluate
from .gates import evaluate_gates, GatePolicy
from .runner import run_evaluation

__all__ = [
    "validate_bid_ask", "dataset_hash", "load_bid_ask_csv",
    "simulate_trades", "TradeManagementTemplate",
    "chronological_partitions", "walk_forward_evaluate",
    "evaluate_gates", "GatePolicy", "run_evaluation",
]
