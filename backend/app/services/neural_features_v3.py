"""Feature adapter for AEGIS Neural v3 teacher-confidence model."""
from __future__ import annotations
from typing import Any

FEATURE_NAMES = [
    "f7","f8","f9","f10","f11",
    "CONTRACTION","EXPANSION","RULE_A","RULE_B","RULE_C","RULE_F",
    "EXPANSION_BUY","EXPANSION_SELL",
]
FEATURE_DIM = 13


def _rsi_scale(y: float, panel_top: float, panel_bottom: float) -> float:
    span=max(panel_bottom-panel_top,1.0)
    return max(0.0,min(100.0,100.0*(panel_bottom-y)/span))


def extract_feature_vector(history: list[dict[str, Any]], rule_flags: dict[str,int]) -> dict[str,Any]:
    cur=history[-1] if history else {}
    top=float(cur.get("_indicator_top",0.0)); bottom=float(cur.get("_indicator_bottom",100.0))
    b=cur.get("band1") if isinstance(cur.get("band1"),dict) else {}
    vals=[
        _rsi_scale(float(cur["rsi6"]),top,bottom) if cur.get("rsi6") is not None else float("nan"),
        _rsi_scale(float(cur["ma4"]),top,bottom) if cur.get("ma4") is not None else float("nan"),
        _rsi_scale(float(b["U"]),top,bottom) if b.get("U") is not None else float("nan"),
        _rsi_scale(float(b["M"]),top,bottom) if b.get("M") is not None else float("nan"),
        _rsi_scale(float(b["L"]),top,bottom) if b.get("L") is not None else float("nan"),
    ]
    flags=[float(rule_flags.get(k,0)) for k in FEATURE_NAMES[5:]]
    vec=vals+flags
    complete=sum(1 for v in vec if v==v)/FEATURE_DIM
    return {"vector":vec,"names":FEATURE_NAMES,"completeness":complete,"bands_ok":len(b)==3}
