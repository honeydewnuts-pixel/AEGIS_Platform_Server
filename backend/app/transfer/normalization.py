from __future__ import annotations
import numpy as np
import pandas as pd

REQUIRED_OHLC = ('BidOpen','BidHigh','BidLow','BidClose')

def validate_ohlc(df: pd.DataFrame) -> list[str]:
    missing = [c for c in REQUIRED_OHLC if c not in df.columns]
    if missing:
        return [f'MISSING_COLUMNS:{",".join(missing)}']
    errors: list[str] = []
    x = df[list(REQUIRED_OHLC)].apply(pd.to_numeric, errors='coerce')
    if x.isna().any().any(): errors.append('NON_NUMERIC_OR_NAN_OHLC')
    if (x <= 0).any().any(): errors.append('NON_POSITIVE_PRICE')
    if (x.BidHigh < x[['BidOpen','BidClose']].max(axis=1)).any(): errors.append('HIGH_BELOW_BODY')
    if (x.BidLow > x[['BidOpen','BidClose']].min(axis=1)).any(): errors.append('LOW_ABOVE_BODY')
    if (x.BidHigh < x.BidLow).any(): errors.append('HIGH_BELOW_LOW')
    return errors

def atr_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df.BidHigh.astype(float), df.BidLow.astype(float), df.BidClose.astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h-l), (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    atr = pd.Series(np.nan, index=df.index, dtype=float)
    if len(df) <= 1: return atr
    atr.iloc[1] = tr.iloc[1]
    for i in range(2, len(df)):
        atr.iloc[i] = ((period-1)*atr.iloc[i-1] + tr.iloc[i]) / period
    atr.iloc[:period] = np.nan
    return atr

def causal_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out['ATR14'] = atr_wilder(out, 14)
    out['range_atr'] = (out.BidHigh-out.BidLow) / out.ATR14
    out['price_atr'] = out.BidClose / out.ATR14
    out['atr_pct_price'] = out.ATR14 / out.BidClose
    out['structural_range_12_atr'] = (out.BidHigh.shift(1).rolling(12).max() - out.BidLow.shift(1).rolling(12).min()) / out.ATR14
    out['compression_12'] = out['range_atr'].shift(1).rolling(12).mean()
    out['expansion_ratio'] = out['range_atr']
    out['disp_24_atr'] = (out.BidClose - out.BidClose.shift(24)) / out.ATR14
    out['disp_48_atr'] = (out.BidClose - out.BidClose.shift(48)) / out.ATR14
    if 'AskClose' in out.columns:
        out['spread'] = out.AskClose - out.BidClose
        out['spread_atr'] = out['spread'] / out.ATR14
        out['expected_cost_atr'] = out['spread_atr']
    else:
        out['spread'] = np.nan
        out['spread_atr'] = np.nan
        out['expected_cost_atr'] = np.nan
    return out

def normalized_1r(df: pd.DataFrame, source_risk_price: float = 0.001) -> float:
    """Source 1R is represented only to derive the dimensionless source ratio.
    Target 1R is never set to source_risk_price. This function returns the
    source ratio only; target mapping must use target causal ATR statistics.
    """
    valid = atr_wilder(df, 14).dropna()
    if valid.empty: raise ValueError('INSUFFICIENT_HISTORY')
    return float(source_risk_price / valid.median())
