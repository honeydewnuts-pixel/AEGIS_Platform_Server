from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from .normalization import causal_features

@dataclass(frozen=True)
class MappingPolicy:
    version: str = 'V39.1-PREDECLARED-ATR-MEDIAN'
    source_1r_ratio_method: str = 'source_1R / median(source ATR14)'
    target_1r_method: str = 'target causal median ATR14 * source 1R/ATR ratio'
    stop_method: str = '1.5 * target ATR14'
    trail_method: str = '0.75 * target ATR14'
    max_bars: int = 72

def map_execution_parameters(target_df: pd.DataFrame, source_1r_ratio: float) -> dict[str, float | int | str]:
    f = causal_features(target_df)
    atr = f.ATR14.dropna()
    if atr.empty: raise ValueError('INSUFFICIENT_HISTORY')
    target_atr = float(atr.median())
    return {
        '1R': target_atr * source_1r_ratio,
        'initial_sl_atr': 1.5,
        'trailing_atr': 0.75,
        'max_holding_bars': 72,
        'mapping_version': MappingPolicy().version,
    }
