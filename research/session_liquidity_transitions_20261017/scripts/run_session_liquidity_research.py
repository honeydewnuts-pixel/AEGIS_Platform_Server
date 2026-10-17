#!/usr/bin/env python3
"""Session liquidity transitions measurement. Prereg commit 966214a261d2a15e0c9fa6b4335b3c5c3babde23."""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
PREREG = ROOT / "docs/AEGIS_SESSION_LIQUIDITY_PREREGISTRATION.md"
HASH_FILE = OUT / "preregistration_hash.txt"

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]
# boundary hour UTC -> label
TRANSITIONS = {"T1": 7, "T2": 12, "T3": 13}
CONTROLS = [3, 15]
HORIZONS = [6, 12, 24]
H_STAR = 12
SEED = 17
N_BOOT = 1000
MIN_EVENTS = 100


def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df["bh"] = df["bid_high"].astype(float)
    df["bl"] = df["bid_low"].astype(float)
    df["bc"] = df["bid_close"].astype(float)
    df["spread"] = (df["ask_close"] - df["bid_close"]).astype(float)
    df["hour"] = df["datetime"].dt.hour
    df["minute"] = df["datetime"].dt.minute
    df["dow"] = df["datetime"].dt.dayofweek  # 0=Mon
    df["date"] = df["datetime"].dt.date
    return df, h


def starts_at_hour(df, hour, n_dev, H):
    """Indices i in development where hour==hour, minute==0, weekday, room for H."""
    idx = []
    hours = df["hour"].to_numpy()
    mins = df["minute"].to_numpy()
    dow = df["dow"].to_numpy()
    for i in range(0, n_dev - H - 1):
        if hours[i] == hour and mins[i] == 0 and dow[i] < 5:
            idx.append(i)
    return np.array(idx, dtype=int)


def abs_disp(df, starts, H):
    bc = df["bc"].to_numpy(float)
    out = []
    dates = []
    for i in starts:
        out.append(abs(float(bc[i + H]) - float(bc[i])))
        dates.append(str(df.loc[i, "date"]))
    return np.array(out, float), dates


def realised_range(df, starts, H):
    bh = df["bh"].to_numpy(float)
    bl = df["bl"].to_numpy(float)
    out = []
    for i in starts:
        out.append(float(np.max(bh[i:i + H + 1]) - np.min(bl[i:i + H + 1])))
    return np.array(out, float)


def bootstrap_diff(event_vals, control_vals, n_boot=N_BOOT, seed=SEED):
    """Unpaired day-agnostic bootstrap of difference of means (simple); primary uses this."""
    if len(event_vals) < 10 or len(control_vals) < 10:
        return None, (None, None)
    rng = np.random.default_rng(seed)
    diffs = []
    ne, nc = len(event_vals), len(control_vals)
    for _ in range(n_boot):
        e = event_vals[rng.integers(0, ne, ne)]
        c = control_vals[rng.integers(0, nc, nc)]
        diffs.append(float(np.mean(e) - np.mean(c)))
    diffs = np.array(diffs)
    return float(np.mean(event_vals) - np.mean(control_vals)), (
        float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
    )


def analyze(sym):
    df, file_hash = load(sym)
    n = len(df)
    n_dev = int(0.80 * n)
    med_spread = float(np.nanmedian(df["spread"].to_numpy(float)[:n_dev]))
    rows = []
    primary = None
    for tid, hour in TRANSITIONS.items():
        for H in HORIZONS:
            ev = starts_at_hour(df, hour, n_dev, H)
            # controls: pool 03:00 and 15:00
            c_idx = np.concatenate([starts_at_hour(df, h, n_dev, H) for h in CONTROLS])
            e_disp, e_dates = abs_disp(df, ev, H)
            c_disp, _ = abs_disp(df, c_idx, H)
            e_rng = realised_range(df, ev, H)
            c_rng = realised_range(df, c_idx, H)
            diff, ci = bootstrap_diff(e_disp, c_disp)
            row = dict(
                symbol=sym, transition=tid, hour=hour, H=H,
                n_event=len(e_disp), n_control=len(c_disp),
                mean_abs_disp_event=float(np.mean(e_disp)) if len(e_disp) else None,
                mean_abs_disp_control=float(np.mean(c_disp)) if len(c_disp) else None,
                mean_range_event=float(np.mean(e_rng)) if len(e_rng) else None,
                mean_range_control=float(np.mean(c_rng)) if len(c_rng) else None,
                ratio_disp=(float(np.mean(e_disp)) / float(np.mean(c_disp))) if len(e_disp) and len(c_disp) and np.mean(c_disp) > 0 else None,
                diff_mean=diff, ci_lo=ci[0], ci_hi=ci[1],
                materiality=(float(np.mean(e_disp)) / med_spread) if len(e_disp) and med_spread > 0 else None,
                med_spread=med_spread,
                sufficient=len(e_disp) >= MIN_EVENTS,
                file_hash=file_hash,
            )
            rows.append(row)
            if tid == "T1" and H == H_STAR:
                primary = row
    # stability halves T1 H*
    half = n_dev // 2
    ev_all = starts_at_hour(df, 7, n_dev, H_STAR)
    ev1 = ev_all[ev_all < half]
    ev2 = ev_all[ev_all >= half]
    c_all = np.concatenate([starts_at_hour(df, h, n_dev, H_STAR) for h in CONTROLS])
    d1, _ = abs_disp(df, ev1, H_STAR)
    d2, _ = abs_disp(df, ev2, H_STAR)
    c1 = abs_disp(df, c_all[c_all < half], H_STAR)[0]
    c2 = abs_disp(df, c_all[c_all >= half], H_STAR)[0]
    r1 = (float(np.mean(d1)) / float(np.mean(c1))) if len(d1) and len(c1) and np.mean(c1) > 0 else None
    r2 = (float(np.mean(d2)) / float(np.mean(c2))) if len(d2) and len(c2) and np.mean(c2) > 0 else None
    return rows, primary, dict(ratio_half1=r1, ratio_half2=r2, n1=len(d1), n2=len(d2)), file_hash, med_spread


def main():
    t0 = time.time()
    actual = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    recorded = HASH_FILE.read_text().split()[0]
    assert actual == recorded, f"hash mismatch {actual} {recorded}"
    print(f"Prereg OK {actual[:16]}...", flush=True)

    all_rows = []
    primaries = []
    hashes = []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        rows, primary, stab, fh, ms = analyze(sym)
        all_rows.extend(rows)
        primaries.append({**primary, **stab})
        hashes.append(dict(symbol=sym, sha256=fh, med_spread=ms))
        p = primary
        print(
            f"  T1 H12 n_ev={p['n_event']} mean_ev={p['mean_abs_disp_event']:.6f} "
            f"mean_ctl={p['mean_abs_disp_control']:.6f} ratio={p['ratio_disp']} "
            f"diff={p['diff_mean']} CI=[{p['ci_lo']},{p['ci_hi']}] mat={p['materiality']}",
            flush=True,
        )

    pd.DataFrame(all_rows).to_csv(OUT / "session_event_measurements.csv", index=False)
    pd.DataFrame(primaries).to_csv(OUT / "session_instrument_summary.csv", index=False)
    pd.DataFrame(hashes).to_csv(OUT / "dataset_manifest.csv", index=False)

    # Decision
    suff = [p for p in primaries if p.get("sufficient")]
    ci_pos = [p for p in suff if p.get("ci_lo") is not None and p["ci_lo"] > 0]
    mat_ok = [p for p in suff if p.get("materiality") is not None and p["materiality"] >= 2]
    both = [p for p in ci_pos if p in mat_ok or (p.get("materiality") or 0) >= 2]
    # stability: both halves ratio > 1
    stable = [p for p in suff if (p.get("ratio_half1") or 0) > 1 and (p.get("ratio_half2") or 0) > 1]

    if len(suff) < 5:
        decision = "G_INSUFFICIENT_DATA"
    elif len(ci_pos) >= 5 and len(mat_ok) >= 5 and len(stable) >= 5:
        decision = "F_PROMISING"
    elif len(ci_pos) >= 5 and len(mat_ok) < 5:
        decision = "C_STATISTICAL_BUT_IMMATERIAL"
    elif len(ci_pos) == 0:
        decision = "A_NO_DETECTABLE_EFFECT"
    elif len(ci_pos) < 5:
        decision = "D_INSTRUMENT_SPECIFIC"
    else:
        decision = "C_STATISTICAL_BUT_IMMATERIAL"

    # Check if T1 similar to T2/T3 (seasonality)
    t2_ratios = []
    for sym in PAIRS:
        sub = [r for r in all_rows if r["symbol"] == sym and r["transition"] == "T2" and r["H"] == H_STAR]
        if sub and sub[0]["ratio_disp"]:
            t2_ratios.append(sub[0]["ratio_disp"])
    t1_ratios = [p["ratio_disp"] for p in primaries if p.get("ratio_disp")]

    summary = dict(
        prereg_hash=actual,
        prereg_commit="966214a261d2a15e0c9fa6b4335b3c5c3babde23",
        primary_transition="T1_London_open_07UTC",
        H_star=H_STAR,
        n_pairs=len(PAIRS),
        n_sufficient=len(suff),
        n_ci_diff_gt0=len(ci_pos),
        n_materiality_ge2=len(mat_ok),
        n_stable_both_halves=len(stable),
        median_ratio_t1=float(np.median(t1_ratios)) if t1_ratios else None,
        median_ratio_t2=float(np.median(t2_ratios)) if t2_ratios else None,
        median_materiality=float(np.median([p["materiality"] for p in suff if p.get("materiality")])) if suff else None,
        decision=decision,
        note="Price behaviour only; not liquidity; not executable P&L",
        elapsed_sec=round(time.time() - t0, 1),
        instruments=[{
            "symbol": p["symbol"],
            "n_event": p["n_event"],
            "ratio_disp": p["ratio_disp"],
            "diff_mean": p["diff_mean"],
            "ci": [p["ci_lo"], p["ci_hi"]],
            "materiality": p["materiality"],
            "ratio_half1": p.get("ratio_half1"),
            "ratio_half2": p.get("ratio_half2"),
        } for p in primaries],
    )
    (OUT / "session_liquidity_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== DECISION ====", flush=True)
    print(f"sufficient={len(suff)} ci_pos={len(ci_pos)} mat>=2={len(mat_ok)} stable={len(stable)}", flush=True)
    print(f"median T1 ratio={summary['median_ratio_t1']} T2 ratio={summary['median_ratio_t2']} mat={summary['median_materiality']}", flush=True)
    print(f"DECISION: {decision}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
