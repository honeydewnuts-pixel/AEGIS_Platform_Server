"""
Variant B - M15 Pullback-Failure Reversal with Main-Window Trend Filter
GBPUSD cash-test source code.

Rules:
- Lower window: RSI(9), SMA7 of RSI, BB34(1.618) on SMA7, WPR(60).
- Trend break: MA7 and RSI9 cross BB34 middle band.
- Pullback: RSI9 or WPR60 crosses back through middle band.
- Entry: after pullback failure - RSI9 recrosses MA7 or middle band.
- Main-window filter: block longs in confirmed BB17/BB34 downtrend,
  block shorts in confirmed BB17/BB34 uptrend.
- Exits: 1.5 ATR stop, 2.5 ATR chandelier trail after 1 ATR favorable move,
  48h time stop, opposite-signal exit, 30-bar cooldown.
"""
import pandas as pd
import numpy as np

def load_csv(path):
    df = pd.read_csv(path)
    cols = {k.lower(): k for k in df.columns}
    def col(*names):
        for n in names:
            if n.lower() in cols:
                return cols[n.lower()]
    t = col('time', 'timestamp', 'date')
    o = col('open'); h = col('high'); l = col('low'); c = col('close')
    df = df.rename(columns={t: 'time', o: 'open', h: 'high', l: 'low', c: 'close'})
    df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
    return df.dropna(subset=['time']).sort_values('time').drop_duplicates('time').reset_index(drop=True)

def resample(df, rule):
    return (df.set_index('time')
              .resample(rule)
              .agg({'open': 'first', 'high': 'max', 'low': 'min',
                    'close': 'last', 'volume': 'sum'})
              .dropna().reset_index())

def bollinger(s, n, k):
    mid = s.rolling(n).mean()
    sd = s.rolling(n).std(ddof=0)
    return mid + k * sd, mid, mid - k * sd

def rsi(close, n=9):
    diff = close.diff()
    gain = diff.clip(lower=0)
    loss = (-diff).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/n, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    out = out.where(avg_loss != 0, 100.0)
    out = out.where((avg_gain != 0) | (avg_loss != 0), 50.0)
    return out

def williams_r(high, low, close, n=60):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    return -100 * (hh - close) / (hh - ll)

def atr(high, low, close, n=14):
    tr = pd.concat([high - low,
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def profit_factor(pnl):
    pnl = pnl[pnl != 0]
    gross_profit = pnl[pnl > 0].sum()
    gross_loss = -pnl[pnl < 0].sum()
    return round(gross_profit / gross_loss, 2) if gross_loss > 0 else np.inf

def run_variant_b(d, cost=0.00019, risk=0.01):
    c, h, l = d.close, d.high, d.low
    rsi9 = rsi(c, 9)
    ma7 = rsi9.rolling(7).mean()
    bb_u, bb_m, bb_l = bollinger(ma7, 34, 1.618)
    wpr = williams_r(h, l, c, 60)
    atr14 = atr(h, l, c, 14)

    ema17 = c.rolling(17).mean(); sd17 = c.rolling(17).std(ddof=0)
    ema34 = c.rolling(34).mean(); sd34 = c.rolling(34).std(ddof=0)
    b17u, b17l = ema17 + sd17, ema17 - sd17
    b34u, b34l = ema34 + sd34, ema34 - sd34
    uptrend = (b17u > b34u) & (b17l > b34l)
    downtrend = (b17u < b34l) & (b17u < b34l)

    n = len(d)
    cash = 10000.0
    trades, equity = [], []
    up_break_i = dn_break_i = -10**9
    cooldown = -10**9
    pull_short = pull_long = False
    pos = 0

    for t in range(200, n):
        if pos != 0:
            if t - entry_i > 576:
                xp = d.open.iloc[t]
                pnl = (xp - entry) * direction * units - cost * units
                cash += pnl
                trades.append({'dir': 'long' if direction == 1 else 'short',
                               'entry_time': d.time.iloc[entry_i],
                               'exit_time': d.time.iloc[t],
                               'entry': entry, 'exit': xp,
                               'pnl': pnl, 'reason': 'time'})
                pos = 0; cooldown = t
            elif pos == 1:
                highest = max(highest, h.iloc[t-1])
                if highest - entry >= atr14.iloc[t-1]:
                    sl = max(sl, highest - 2.5 * atr14.iloc[t-1])
                if l.iloc[t] <= sl:
                    pnl = (sl - entry) * units - cost * units
                    cash += pnl
                    trades.append({'dir': 'long', 'entry_time': d.time.iloc[entry_i],
                                   'exit_time': d.time.iloc[t], 'entry': entry,
                                   'exit': sl, 'pnl': pnl, 'reason': 'trail'})
                    pos = 0; cooldown = t
            else:
                lowest = min(lowest, l.iloc[t-1])
                if entry - lowest >= atr14.iloc[t-1]:
                    sl = min(sl, lowest + 2.5 * atr14.iloc[t-1])
                if h.iloc[t] >= sl:
                    pnl = (entry - sl) * units - cost * units
                    cash += pnl
                    trades.append({'dir': 'short', 'entry_time': d.time.iloc[entry_i],
                                   'exit_time': d.time.iloc[t], 'entry': entry,
                                   'exit': sl, 'pnl': pnl, 'reason': 'trail'})
                    pos = 0; cooldown = t

        r = rsi9.iloc[t]; m = ma7.iloc[t]
        U, M, L = bb_u.iloc[t], bb_m.iloc[t], bb_l.iloc[t]
        w = wpr.iloc[t]
        r_prev = rsi9.iloc[t-1]; m_prev = ma7.iloc[t-1]; w_prev = wpr.iloc[t-1]

        if any(pd.isna(x) for x in [r, m, U, M, L, w, atr14.iloc[t-1]]):
            equity.append((d.time.iloc[t], cash)); continue

        if m_prev > M and m < M and r_prev > M and r < M:
            dn_break_i = t; pull_short = False
        if m_prev < M and m > M and r_prev < M and r > M:
            up_break_i = t; pull_long = False
        if t - dn_break_i > 30: pull_short = False
        if t - up_break_i > 30: pull_long = False

        if (L <= m <= M) and ((r_prev <= M and r > M) or (w_prev <= M and w > M)) and t - dn_break_i <= 30:
            pull_short = True
        if (M <= m <= U) and ((r_prev >= M and r < M) or (w_prev >= M and w < M)) and t - up_break_i <= 30:
            pull_long = True

        sig_short = pull_short and ((r_prev > M and r < M) or (r_prev > m and r < m)) and (L <= m <= M)
        sig_long = pull_long and ((r_prev < M and r > M) or (r_prev < m and r > m)) and (M <= m <= U)
        sig_short = sig_short and not uptrend.iloc[t]
        sig_long = sig_long and not downtrend.iloc[t]

        if pos == 1 and sig_short:
            xp = d.open.iloc[t]
            pnl = (xp - entry) * units - cost * units
            cash += pnl
            trades.append({'dir': 'long', 'entry_time': d.time.iloc[entry_i],
                           'exit_time': d.time.iloc[t], 'entry': entry, 'exit': xp,
                           'pnl': pnl, 'reason': 'reverse'})
            pos = 0; cooldown = t; pull_short = False
        elif pos == -1 and sig_long:
            xp = d.open.iloc[t]
            pnl = (entry - xp) * units - cost * units
            cash += pnl
            trades.append({'dir': 'short', 'entry_time': d.time.iloc[entry_i],
                           'exit_time': d.time.iloc[t], 'entry': entry, 'exit': xp,
                           'pnl': pnl, 'reason': 'reverse'})
            pos = 0; cooldown = t; pull_long = False

        if pos == 0 and t - cooldown >= 30:
            if sig_short:
                pos = -1; direction = -1; entry_i = t
                entry = d.open.iloc[t]; lowest = l.iloc[t]
                sl = max(entry + 1.5 * atr14.iloc[t], entry)
                units = (cash * risk) / max(sl - entry, 1e-9)
                pull_short = False
            elif sig_long:
                pos = 1; direction = 1; entry_i = t
                entry = d.open.iloc[t]; highest = h.iloc[t]
                sl = min(entry - 1.5 * atr14.iloc[t], entry)
                units = (cash * risk) / max(entry - sl, 1e-9)
                pull_long = False

        equity.append((d.time.iloc[t], cash))

    return pd.DataFrame(trades), pd.DataFrame(equity, columns=['time', 'equity'])

if __name__ == '__main__':
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else 'GBPUSD_M5_5Y.csv'
    df = load_csv(src)
    m15 = resample(df, '15min')
    trades, equity = run_variant_b(m15)
    trades.to_csv('variant_b_trades.csv', index=False)
    equity.to_csv('variant_b_equity.csv', index=False)
    print('trades:', len(trades), 'final equity:', equity.equity.iloc[-1],
          'profit factor:', profit_factor(trades.pnl))
