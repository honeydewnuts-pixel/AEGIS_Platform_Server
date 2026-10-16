#!/usr/bin/env python3
"""
Asian Range → New York Expansion hypothesis scan.

Audit-compliant:
- Broker-correct Bid/Ask execution only (not V53.6).
- Full-cost R: spread embedded + 0.3 entry slip + 0.3 exit slip + 0.7 commission.
- PF_spread_only and PF_full_cost both reported; PF_full_cost is primary.
- Six equal-duration calendar blocks on validation.
- Conservative gap: fill at next available open on exit side (sensitivity documented).
- Stop-first intrabar convention.
- No lookahead. Chronological 60/20/20. No production authorization.

Git commit at time of script creation: 8385fc60ea16a195ba00a64697ddc07d4f526b9c
"""
from __future__ import annotations
import json, time, hashlib, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path("/home/workdir/artifacts/aegis_disc2")
import sys
sys.path.insert(0, str(ROOT / "backend"))
from app.rulebooks.evaluators.common import wilder_atr14

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = Path("/home/workdir/artifacts/discovery_hypotheses")
OUT.mkdir(parents=True, exist_ok=True)

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]

GIT_SHA = "8385fc60ea16a195ba00a64697ddc07d4f526b9c"
SLIP_ENTRY_PIPS = 0.3
SLIP_EXIT_PIPS = 0.3
COMM_PIPS = 0.7  # assumption, not broker-spec

VAL_MIN_TRADES_STRICT = 350
VAL_MIN_TRADES_LF = 150
VAL_MIN_PF = 1.6
BLOCK_MIN_PF = 1.0
N_BLOCKS = 6
BLOCK_MIN_TRADES = 10


def pip_size(sym: str) -> float:
    return 0.01 if "JPY" in sym else 0.0001


def load_pair(sym: str) -> pd.DataFrame | None:
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    if not p.is_file():
        return None
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    for std, src in [
        ("BidOpen", "bid_open"), ("BidHigh", "bid_high"),
        ("BidLow", "bid_low"), ("BidClose", "bid_close"),
        ("AskOpen", "ask_open"), ("AskHigh", "ask_high"),
        ("AskLow", "ask_low"), ("AskClose", "ask_close"),
    ]:
        df[std] = df[src].astype(float)
    df["hour"] = df["datetime"].dt.hour
    df["date"] = df["datetime"].dt.date
    return df


def true_range(bh, bl, bc):
    n = len(bc)
    tr = np.full(n, np.nan)
    tr[0] = bh[0] - bl[0]
    tr[1:] = np.maximum.reduce([
        bh[1:] - bl[1:],
        np.abs(bh[1:] - bc[:-1]),
        np.abs(bl[1:] - bc[:-1]),
    ])
    return tr


def daily_atr_median(df: pd.DataFrame, window_days: int = 20) -> np.ndarray:
    """20-day median of daily true range, aligned to each M5 bar (causal)."""
    d = df.set_index("datetime")
    daily = d.resample("1D").agg({"BidHigh": "max", "BidLow": "min", "BidClose": "last"}).dropna()
    dtr = (daily["BidHigh"] - daily["BidLow"]).values
    med = pd.Series(dtr, index=daily.index).rolling(window_days, min_periods=10).median()
    # shift 1 day so today's bars only see prior completed days
    med = med.shift(1)
    aligned = med.reindex(df["datetime"], method="ffill")
    return aligned.to_numpy(float)


def build_sessions(df: pd.DataFrame):
    """Build per-date Asian / London / NY session index lists."""
    hours = df["hour"].to_numpy(int)
    dates = df["date"].to_numpy()
    date_to_idxs: dict = {}
    for i, d in enumerate(dates):
        date_to_idxs.setdefault(d, []).append(i)

    sessions = []
    for d, idxs in date_to_idxs.items():
        asian = [i for i in idxs if 0 <= hours[i] < 7]
        london = [i for i in idxs if 7 <= hours[i] < 12]
        ny = [i for i in idxs if 12 <= hours[i] < 16]
        if len(asian) < 12 or len(london) < 6 or len(ny) < 6:
            continue
        sessions.append(dict(date=d, asian=asian, london=london, ny=ny))
    return sessions


def generate_events(df: pd.DataFrame, atr_m5: np.ndarray, daily_atr_med: np.ndarray, sym: str):
    """
    Asian range → London compression/failure → NY expansion events.
    Returns long_events, short_events, n_cost_rejected.
    """
    bh = df["BidHigh"].to_numpy(float)
    bl = df["BidLow"].to_numpy(float)
    bc = df["BidClose"].to_numpy(float)
    tr = true_range(bh, bl, bc)
    tr_med100 = pd.Series(tr).rolling(100, min_periods=50).median().to_numpy()
    spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
    pip = pip_size(sym)

    sessions = build_sessions(df)
    long_ev, short_ev = [], []
    n_cost_rejected = 0

    for s in sessions:
        a_idxs = s["asian"]
        l_idxs = s["london"]
        n_idxs = s["ny"]
        a_hi = float(np.max(bh[a_idxs]))
        a_lo = float(np.min(bl[a_idxs]))
        a_range = a_hi - a_lo
        last_asian = a_idxs[-1]
        datr = daily_atr_med[last_asian]
        if not np.isfinite(datr) or datr <= 0:
            continue
        # Asian range filter: 0.5–1.5 × 20-day median daily ATR
        if a_range < 0.5 * datr or a_range > 1.5 * datr:
            continue
        if a_range < 3 * pip:  # degenerate
            continue

        # London behavior: failed expansion or remains inside
        l_closes = bc[l_idxs]
        l_beyond = np.sum((l_closes > a_hi + 0.25 * a_range) | (l_closes < a_lo - 0.25 * a_range))
        l_inside = np.sum((l_closes >= a_lo) & (l_closes <= a_hi))
        failed_expansion = l_beyond == 0  # never closed beyond by 0.25×range
        mostly_inside = (l_inside / max(len(l_idxs), 1)) >= 0.60
        if not (failed_expansion or mostly_inside):
            continue

        # NY expansion: first M5 close beyond Asian high/low by ≥0.25×range
        # with TR > median M5 TR
        broken_long = broken_short = False
        for j in n_idxs:
            if broken_long and broken_short:
                break
            if not np.isfinite(tr[j]) or not np.isfinite(tr_med100[j]):
                continue
            if tr[j] <= tr_med100[j]:
                continue
            # cost estimate at this bar
            spr_pips = spread[j] / pip
            full_cost_pips = spr_pips + SLIP_ENTRY_PIPS + SLIP_EXIT_PIPS + COMM_PIPS
            full_cost_price = full_cost_pips * pip
            A = atr_m5[j]
            if not np.isfinite(A) or A < 2.0 * full_cost_price:
                n_cost_rejected += 1
                continue

            if not broken_long and bc[j] > a_hi + 0.25 * a_range:
                # room to invalidation (Asian midpoint or low)
                room = bc[j] - a_lo
                if room < 5.0 * full_cost_price:
                    n_cost_rejected += 1
                else:
                    long_ev.append(j)
                    broken_long = True
            if not broken_short and bc[j] < a_lo - 0.25 * a_range:
                room = a_hi - bc[j]
                if room < 5.0 * full_cost_price:
                    n_cost_rejected += 1
                else:
                    short_ev.append(j)
                    broken_short = True

    return np.array(long_ev, dtype=int), np.array(short_ev, dtype=int), n_cost_rejected


def simulate_full(
    df: pd.DataFrame,
    atr: np.ndarray,
    events: np.ndarray,
    side: str,
    *,
    stop_atr: float,
    target_atr: float | None,
    trail_atr: float | None,
    use_be: bool,
    max_hold: int,
    pip: float,
    gap_mode: str = "conservative",  # "conservative" = fill at open; "optimistic" = fill at stop
) -> pd.DataFrame:
    """
    Broker-correct simulation with full-cost R.
    gap_mode:
      conservative — gap through stop fills at next available open on exit side
      optimistic   — fills at historical stop price (frozen-sim style)
    """
    n = len(df)
    bo = df["BidOpen"].to_numpy(float)
    bh = df["BidHigh"].to_numpy(float)
    bl = df["BidLow"].to_numpy(float)
    bc = df["BidClose"].to_numpy(float)
    ao = df["AskOpen"].to_numpy(float)
    ah = df["AskHigh"].to_numpy(float)
    al = df["AskLow"].to_numpy(float)
    ac = df["AskClose"].to_numpy(float)

    slip_entry = SLIP_ENTRY_PIPS * pip
    slip_exit = SLIP_EXIT_PIPS * pip
    comm = COMM_PIPS * pip

    trades = []
    next_allowed = 0
    n_gap = 0

    for i in events:
        i = int(i)
        if i <= next_allowed or i + 1 >= n:
            continue
        A = atr[i]
        if not np.isfinite(A) or A <= 0:
            continue
        risk = stop_atr * float(A)
        if risk <= 0:
            continue

        if side == "LONG":
            raw_entry = float(ao[i + 1])
            entry = raw_entry + slip_entry  # adverse
            stop = entry - risk
            target = (entry + target_atr * float(A)) if target_atr is not None else None
            be = False
            best = entry
            end = min(n - 1, i + int(max_hold))
            exit_i = exit_px = reason = None
            for j in range(i + 1, end + 1):
                # stop check first (intrabar convention)
                if bl[j] <= stop:
                    # gap?
                    if float(bo[j]) < stop and gap_mode == "conservative":
                        fill = float(bo[j])  # adverse open
                        n_gap += 1
                    else:
                        fill = stop
                    exit_i, exit_px, reason = j, fill - slip_exit, "STOP"
                    break
                # target
                if target is not None and bh[j] >= target:
                    exit_i, exit_px, reason = j, target - slip_exit, "TARGET"
                    break
                # BE
                if use_be and (bh[j] - entry) / risk >= 1.0 and not be:
                    stop = entry
                    be = True
                # trail from best favorable (close-based update; cannot retroactively fill same bar)
                if trail_atr is not None:
                    if bc[j] > best:
                        best = bc[j]
                    candidate = best - trail_atr * float(atr[j] if np.isfinite(atr[j]) else A)
                    if candidate > stop:
                        stop = candidate
                if j == end:
                    exit_i, exit_px, reason = j, float(bc[j]) - slip_exit, "TIME"
            if exit_i is None:
                continue
            gross_price = float(exit_px) - entry  # already includes slips on both sides
            # commission in price
            net_price = gross_price - comm
            gross_R_spread = (float(exit_px) + slip_exit - (raw_entry)) / risk  # approx spread-only path
            # cleaner: spread-only uses raw quotes without slip/comm
            exit_raw = float(exit_px) + slip_exit  # undo exit slip for spread-only
            entry_raw = raw_entry
            gross_spread_only = (exit_raw - entry_raw) / risk
            full_R = net_price / risk
        else:  # SHORT
            raw_entry = float(bo[i + 1])
            entry = raw_entry - slip_entry  # adverse for short
            stop = entry + risk
            target = (entry - target_atr * float(A)) if target_atr is not None else None
            be = False
            best = entry
            end = min(n - 1, i + int(max_hold))
            exit_i = exit_px = reason = None
            for j in range(i + 1, end + 1):
                if ah[j] >= stop:
                    if float(ao[j]) > stop and gap_mode == "conservative":
                        fill = float(ao[j])
                        n_gap += 1
                    else:
                        fill = stop
                    exit_i, exit_px, reason = j, fill + slip_exit, "STOP"
                    break
                if target is not None and al[j] <= target:
                    exit_i, exit_px, reason = j, target + slip_exit, "TARGET"
                    break
                if use_be and (entry - al[j]) / risk >= 1.0 and not be:
                    stop = entry
                    be = True
                if trail_atr is not None:
                    if ac[j] < best:
                        best = ac[j]
                    candidate = best + trail_atr * float(atr[j] if np.isfinite(atr[j]) else A)
                    if candidate < stop:
                        stop = candidate
                if j == end:
                    exit_i, exit_px, reason = j, float(ac[j]) + slip_exit, "TIME"
            if exit_i is None:
                continue
            net_price = entry - float(exit_px) - comm
            exit_raw = float(exit_px) - slip_exit
            entry_raw = raw_entry
            gross_spread_only = (entry_raw - exit_raw) / risk
            full_R = net_price / risk

        trades.append(dict(
            entry_i=i, exit_i=exit_i, entry=entry, exit=float(exit_px),
            R=full_R, R_spread_only=gross_spread_only, reason=reason, side=side,
        ))
        next_allowed = exit_i

    out = pd.DataFrame(trades)
    out.attrs["n_gap"] = n_gap
    return out


def pf_from_r(r: np.ndarray) -> float:
    if len(r) == 0:
        return float("nan")
    gp = float(r[r > 0].sum())
    gl = float(-r[r < 0].sum())
    return gp / gl if gl > 0 else float("nan")


def metrics(tr: pd.DataFrame, r_col: str = "R") -> dict:
    if tr is None or len(tr) == 0:
        return dict(trades=0, PF=float("nan"), avg_R=float("nan"), win_rate=float("nan"),
                    max_DD=float("nan"), max_win=float("nan"), max_loss=float("nan"))
    r = tr[r_col].to_numpy(float)
    eq = np.cumsum(r)
    dd = float((np.maximum.accumulate(eq) - eq).max()) if len(r) else float("nan")
    return dict(
        trades=int(len(r)),
        PF=pf_from_r(r),
        avg_R=float(np.mean(r)),
        win_rate=float(np.mean(r > 0)),
        max_DD=dd,
        max_win=float(np.max(r)) if len(r) else float("nan"),
        max_loss=float(np.min(r)) if len(r) else float("nan"),
    )


def six_calendar_blocks(tr: pd.DataFrame, df: pd.DataFrame, t1: int, t2: int, r_col: str = "R"):
    """Six equal-duration calendar intervals over validation [t1, t2)."""
    if tr is None or len(tr) == 0:
        return [float("nan")] * N_BLOCKS, [0] * N_BLOCKS
    val_start = df.loc[t1, "datetime"]
    val_end = df.loc[t2 - 1, "datetime"]
    total_sec = (val_end - val_start).total_seconds()
    if total_sec <= 0:
        return [float("nan")] * N_BLOCKS, [0] * N_BLOCKS
    edges = [val_start + pd.Timedelta(seconds=total_sec * k / N_BLOCKS) for k in range(N_BLOCKS + 1)]
    # map entry_i to datetime
    entry_dt = pd.to_datetime(df.loc[tr["entry_i"].to_numpy(), "datetime"].to_numpy(), utc=True)
    pfs, counts = [], []
    for b in range(N_BLOCKS):
        e0 = pd.Timestamp(edges[b])
        e1 = pd.Timestamp(edges[b + 1])
        mask = (entry_dt >= e0) & (entry_dt < e1)
        seg = tr.loc[mask.to_numpy() if hasattr(mask, "to_numpy") else mask, r_col].to_numpy(float)
        counts.append(int(len(seg)))
        if len(seg) < BLOCK_MIN_TRADES:
            pfs.append(float("nan"))  # insufficient
        else:
            pfs.append(pf_from_r(seg))
    return pfs, counts


def rnd(x, nd=4):
    try:
        return round(float(x), nd) if np.isfinite(float(x)) else None
    except Exception:
        return None


def eval_side(df, atr, events, side, cfg, t1, t2, pip, n_cost_rej):
    tag, stop_a, target_a, trail_a, use_be, hold = cfg
    tr = simulate_full(
        df, atr, events, side,
        stop_atr=stop_a, target_atr=target_a, trail_atr=trail_a,
        use_be=use_be, max_hold=hold, pip=pip, gap_mode="conservative",
    )
    n_gap = tr.attrs.get("n_gap", 0) if hasattr(tr, "attrs") else 0

    def split(lo, hi):
        if len(tr) == 0:
            return pd.DataFrame()
        return tr[(tr["entry_i"] >= lo) & (tr["entry_i"] < hi)]

    tr_tr, tr_v, tr_te = split(0, t1), split(t1, t2), split(t2, len(df))
    m_tr_s = metrics(tr_tr, "R_spread_only")
    m_tr_f = metrics(tr_tr, "R")
    m_v_s = metrics(tr_v, "R_spread_only")
    m_v_f = metrics(tr_v, "R")
    m_te_s = metrics(tr_te, "R_spread_only")
    m_te_f = metrics(tr_te, "R")
    blk_pfs, blk_counts = six_calendar_blocks(tr_v, df, t1, t2, "R")
    # min over defined blocks only; if any insufficient, min is nan → fail gate
    defined = [p for p in blk_pfs if np.isfinite(p)]
    blk_min = float(np.min(defined)) if defined and len(defined) == N_BLOCKS else float("nan")

    vt = m_v_f["trades"]
    vp = m_v_f["PF"]
    tt = m_te_f["trades"]
    tp = m_te_f["PF"]

    pass_strict = (
        vt > VAL_MIN_TRADES_STRICT and np.isfinite(vp) and vp > VAL_MIN_PF
        and np.isfinite(blk_min) and blk_min > BLOCK_MIN_PF
        and np.isfinite(tp) and tp > 1.4 and tt > 200
    )
    pass_lf = (
        vt > VAL_MIN_TRADES_LF and np.isfinite(vp) and vp > VAL_MIN_PF
        and np.isfinite(blk_min) and blk_min > BLOCK_MIN_PF
        and np.isfinite(tp) and tp > 1.4 and tt > 80
    )

    return dict(
        side=side, config=tag, stop_atr=stop_a, target_atr=target_a, trail_atr=trail_a,
        use_be=use_be, max_hold=hold,
        n_signals=int(len(events)), n_cost_rejected=int(n_cost_rej), n_gap_stops=int(n_gap),
        train_trades=m_tr_f["trades"], train_pf_spread=rnd(m_tr_s["PF"]), train_pf_full=rnd(m_tr_f["PF"]),
        train_avg_R=rnd(m_tr_f["avg_R"]), train_wr=rnd(m_tr_f["win_rate"]),
        val_trades=vt, val_pf_spread=rnd(m_v_s["PF"]), val_pf_full=rnd(vp),
        val_avg_R=rnd(m_v_f["avg_R"]), val_wr=rnd(m_v_f["win_rate"]),
        val_max_DD=rnd(m_v_f["max_DD"]), val_max_win=rnd(m_v_f["max_win"]), val_max_loss=rnd(m_v_f["max_loss"]),
        val_block_pfs=[rnd(p) for p in blk_pfs], val_block_counts=blk_counts,
        val_block_min_pf_full=rnd(blk_min),
        test_trades=tt, test_pf_spread=rnd(m_te_s["PF"]), test_pf_full=rnd(tp),
        test_avg_R=rnd(m_te_f["avg_R"]), test_wr=rnd(m_te_f["win_rate"]),
        pass_strict=bool(pass_strict), pass_lf=bool(pass_lf),
    )


def main():
    t0 = time.time()
    all_rows = []
    strict_passers, lf_candidates = [], []

    # Predeclared exits only
    # (tag, stop_atr, target_atr|None, trail_atr|None, use_be, max_hold)
    configs = [
        ("A", 1.5, 2.0, None, False, 96),
        ("B", 1.5, 3.0, None, False, 96),
        ("C", 2.0, 3.0, None, False, 120),
        ("D", 2.0, None, 1.5, False, 144),
        ("E", 2.0, 3.0, None, True, 120),
    ]

    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        df = load_pair(sym)
        if df is None:
            print("  MISSING", flush=True)
            continue
        atr = wilder_atr14(df["BidHigh"].to_numpy(float), df["BidLow"].to_numpy(float), df["BidClose"].to_numpy(float))
        datr = daily_atr_median(df)
        spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
        ms = float(np.nanmedian(spread))
        ma = float(np.nanmedian(atr[np.isfinite(atr)]))
        print(f"  rows={len(df)} med_spread={ms:.6f} med_atr={ma:.6f}", flush=True)

        long_ev, short_ev, n_rej = generate_events(df, atr, datr, sym)
        print(f"  signals LONG={len(long_ev)} SHORT={len(short_ev)} cost_rejected≈{n_rej}", flush=True)

        t1, t2 = int(0.60 * len(df)), int(0.80 * len(df))
        pip = pip_size(sym)
        best = None

        for cfg in configs:
            # LONG, SHORT, BOTH
            row_l = eval_side(df, atr, long_ev, "LONG", cfg, t1, t2, pip, n_rej)
            row_s = eval_side(df, atr, short_ev, "SHORT", cfg, t1, t2, pip, n_rej)
            # BOTH: concatenate trades
            tr_l = simulate_full(df, atr, long_ev, "LONG", stop_atr=cfg[1], target_atr=cfg[2],
                                 trail_atr=cfg[3], use_be=cfg[4], max_hold=cfg[5], pip=pip)
            tr_s = simulate_full(df, atr, short_ev, "SHORT", stop_atr=cfg[1], target_atr=cfg[2],
                                 trail_atr=cfg[3], use_be=cfg[4], max_hold=cfg[5], pip=pip)
            tr_b = pd.concat([tr_l, tr_s], ignore_index=True) if len(tr_l) or len(tr_s) else pd.DataFrame()
            if len(tr_b):
                tr_b = tr_b.sort_values("entry_i").reset_index(drop=True)
            # reuse eval logic via a synthetic events path — compute metrics directly
            def split_b(lo, hi):
                if len(tr_b) == 0:
                    return pd.DataFrame()
                return tr_b[(tr_b["entry_i"] >= lo) & (tr_b["entry_i"] < hi)]
            tr_tr, tr_v, tr_te = split_b(0, t1), split_b(t1, t2), split_b(t2, len(df))
            m_v_f = metrics(tr_v, "R")
            m_v_s = metrics(tr_v, "R_spread_only")
            m_te_f = metrics(tr_te, "R")
            m_te_s = metrics(tr_te, "R_spread_only")
            m_tr_f = metrics(tr_tr, "R")
            m_tr_s = metrics(tr_tr, "R_spread_only")
            blk_pfs, blk_counts = six_calendar_blocks(tr_v, df, t1, t2, "R")
            defined = [p for p in blk_pfs if np.isfinite(p)]
            blk_min = float(np.min(defined)) if defined and len(defined) == N_BLOCKS else float("nan")
            vt, vp, tt, tp = m_v_f["trades"], m_v_f["PF"], m_te_f["trades"], m_te_f["PF"]
            pass_strict = (vt > VAL_MIN_TRADES_STRICT and np.isfinite(vp) and vp > VAL_MIN_PF
                           and np.isfinite(blk_min) and blk_min > BLOCK_MIN_PF
                           and np.isfinite(tp) and tp > 1.4 and tt > 200)
            pass_lf = (vt > VAL_MIN_TRADES_LF and np.isfinite(vp) and vp > VAL_MIN_PF
                       and np.isfinite(blk_min) and blk_min > BLOCK_MIN_PF
                       and np.isfinite(tp) and tp > 1.4 and tt > 80)
            n_gap = (tr_l.attrs.get("n_gap", 0) if hasattr(tr_l, "attrs") else 0) + (
                tr_s.attrs.get("n_gap", 0) if hasattr(tr_s, "attrs") else 0)
            row_b = dict(
                side="BOTH", config=cfg[0], stop_atr=cfg[1], target_atr=cfg[2], trail_atr=cfg[3],
                use_be=cfg[4], max_hold=cfg[5],
                n_signals=int(len(long_ev) + len(short_ev)), n_cost_rejected=int(n_rej), n_gap_stops=int(n_gap),
                train_trades=m_tr_f["trades"], train_pf_spread=rnd(m_tr_s["PF"]), train_pf_full=rnd(m_tr_f["PF"]),
                train_avg_R=rnd(m_tr_f["avg_R"]), train_wr=rnd(m_tr_f["win_rate"]),
                val_trades=vt, val_pf_spread=rnd(m_v_s["PF"]), val_pf_full=rnd(vp),
                val_avg_R=rnd(m_v_f["avg_R"]), val_wr=rnd(m_v_f["win_rate"]),
                val_max_DD=rnd(m_v_f["max_DD"]), val_max_win=rnd(m_v_f["max_win"]), val_max_loss=rnd(m_v_f["max_loss"]),
                val_block_pfs=[rnd(p) for p in blk_pfs], val_block_counts=blk_counts,
                val_block_min_pf_full=rnd(blk_min),
                test_trades=tt, test_pf_spread=rnd(m_te_s["PF"]), test_pf_full=rnd(tp),
                test_avg_R=rnd(m_te_f["avg_R"]), test_wr=rnd(m_te_f["win_rate"]),
                pass_strict=bool(pass_strict), pass_lf=bool(pass_lf),
            )

            for row in (row_l, row_s, row_b):
                row["symbol"] = sym
                row["hypothesis_id"] = f"{sym}_{row['side']}_asianNY_{row['config']}"
                row["family"] = "asian_range_ny_expansion"
                row["git_sha"] = GIT_SHA
                row["cost_basis"] = "full_cost_primary; also report spread_only"
                row["gap_mode"] = "conservative_open_fill"
                row["intrabar"] = "stop_first"
                row["med_spread"] = round(ms, 8)
                row["med_atr"] = round(ma, 8)
                all_rows.append(row)
                if row["side"] == "BOTH":
                    if row["pass_strict"]:
                        strict_passers.append(row)
                        print(f"  PASS-STRICT {row['hypothesis_id']} val_n={row['val_trades']} pf_full={row['val_pf_full']} blk={row['val_block_min_pf_full']}", flush=True)
                    elif row["pass_lf"]:
                        lf_candidates.append(row)
                        print(f"  PASS-LF {row['hypothesis_id']} val_n={row['val_trades']} pf_full={row['val_pf_full']} blk={row['val_block_min_pf_full']}", flush=True)
                    if (row["val_trades"] or 0) >= 20 and (best is None or (row["val_pf_full"] or 0) > (best["val_pf_full"] or 0)):
                        best = row
        if best:
            print(f"  best BOTH {best['hypothesis_id']} n={best['val_trades']} pf_full={best['val_pf_full']} blk={best['val_block_min_pf_full']} test_pf={best['test_pf_full']}", flush=True)

    # serialize
    df_out = pd.DataFrame(all_rows)
    # convert list cols to string for CSV
    for col in ("val_block_pfs", "val_block_counts"):
        if col in df_out.columns:
            df_out[col] = df_out[col].apply(lambda x: json.dumps(x) if isinstance(x, list) else x)
    df_out.to_csv(OUT / "asian_range_ny_expansion_results.csv", index=False)

    both = [r for r in all_rows if r["side"] == "BOTH" and (r.get("val_trades") or 0) >= 30]
    ranked = sorted(both, key=lambda x: (x.get("val_pf_full") or 0), reverse=True)[:15]

    summary = dict(
        hypothesis="Asian range → London compression/failure → NY expansion",
        git_sha=GIT_SHA,
        cost_model=dict(
            entry_slippage_pips=SLIP_ENTRY_PIPS,
            exit_slippage_pips=SLIP_EXIT_PIPS,
            commission_pips=COMM_PIPS,
            commission_label="assumption_not_broker_spec",
            primary_metric="PF_full_cost",
            also_reported="PF_spread_only",
        ),
        gap_mode="conservative_open_fill",
        intrabar="stop_first",
        blocks="six equal-duration calendar intervals on validation",
        split="60/20/20 chronological; test previously inspected",
        gates_strict=dict(val_trades=VAL_MIN_TRADES_STRICT, val_pf_full=VAL_MIN_PF, block_min_pf_full=BLOCK_MIN_PF, test_pf_full=1.4, test_trades=200),
        gates_lf=dict(val_trades=VAL_MIN_TRADES_LF, val_pf_full=VAL_MIN_PF, block_min_pf_full=BLOCK_MIN_PF, test_pf_full=1.4, test_trades=80),
        n_pairs=len(PAIRS),
        n_evals=len(all_rows),
        n_pass_strict=len(strict_passers),
        n_pass_lf=len(lf_candidates),
        strict_passers=strict_passers,
        lf_candidates=lf_candidates,
        top_by_val_pf_full=ranked[:10],
        elapsed_sec=round(time.time() - t0, 1),
    )
    (OUT / "asian_range_ny_expansion_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n==== SUMMARY ====", flush=True)
    print(f"Evals={len(all_rows)} Pass-strict={len(strict_passers)} Pass-LF={len(lf_candidates)} elapsed={summary['elapsed_sec']}s", flush=True)
    print("Top near-misses (BOTH, val>=30) by val PF_full_cost:", flush=True)
    for r in ranked[:10]:
        print(f"  {r['symbol']} {r['config']} n={r['val_trades']} pf_full={r['val_pf_full']} pf_spread={r['val_pf_spread']} "
              f"blk={r['val_block_min_pf_full']} test_n={r['test_trades']} test_pf_full={r['test_pf_full']}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
