#!/usr/bin/env python3
"""Market-state transitions. Prereg bed45657c9953ad3210360f76d5a02eb3a49b834."""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
PREREG = ROOT / "docs/AEGIS_MARKET_STATE_TRANSITIONS_PREREGISTRATION.md"
HASH_FILE = OUT / "preregistration_hash.txt"

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]
LOOKBACK = 20
H_STAR = 12
THIN = 12
SEED = 20261018
N_BOOT = 1000
MIN_N = 80
WARM = 500


def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df["bc"] = df["bid_close"].astype(float)
    df["spread"] = (df["ask_close"] - df["bid_close"]).astype(float)
    df["dow"] = df["datetime"].dt.dayofweek
    return df, h


def rolling_rv(bc):
    n = len(bc)
    disp = np.zeros(n)
    disp[1:] = np.abs(bc[1:] - bc[:-1])
    cs = np.cumsum(disp)
    rv = np.full(n, np.nan)
    idx = np.arange(LOOKBACK + 1, n)
    rv[idx] = (cs[idx - 1] - cs[idx - LOOKBACK - 1]) / LOOKBACK
    return rv, disp


def past_percentiles(rv, dow, n_end):
    """Expanding weekday-only percentiles; refresh every 50 bars after warm-up (past-only)."""
    p20 = np.full(n_end, np.nan)
    p33 = np.full(n_end, np.nan)
    p67 = np.full(n_end, np.nan)
    p80 = np.full(n_end, np.nan)
    hist = []
    last_p = None
    for i in range(LOOKBACK + 1, n_end):
        if not np.isnan(rv[i - 1]) and dow[i - 1] < 5:
            hist.append(rv[i - 1])
        if len(hist) < WARM:
            continue
        if last_p is None or (i % 50 == 0):
            arr = np.array(hist[::10] if len(hist) > 5000 else hist)
            last_p = np.percentile(arr, [20, 33, 67, 80])
        p20[i], p33[i], p67[i], p80[i] = last_p
    return p20, p33, p67, p80


def classify(rv, p20, p33, p67, p80, n_end):
    quiet = np.zeros(n_end, dtype=bool)
    ordinary = np.zeros(n_end, dtype=bool)
    elevated = np.zeros(n_end, dtype=bool)
    b_low = np.zeros(n_end, dtype=bool)
    b_mid = np.zeros(n_end, dtype=bool)
    b_high = np.zeros(n_end, dtype=bool)
    for i in range(n_end):
        if np.isnan(rv[i]) or np.isnan(p20[i]):
            continue
        if rv[i] <= p20[i]:
            quiet[i] = True
        elif rv[i] <= p80[i]:
            ordinary[i] = True
        else:
            elevated[i] = True
        if rv[i] <= p33[i]:
            b_low[i] = True
        elif rv[i] <= p67[i]:
            b_mid[i] = True
        else:
            b_high[i] = True
    # persist elevated: elevated at i, i-1, i-2
    persist = np.zeros(n_end, dtype=bool)
    for i in range(2, n_end):
        if elevated[i] and elevated[i - 1] and elevated[i - 2]:
            persist[i] = True
    # transitions
    q2a = np.zeros(n_end, dtype=bool)
    a2q = np.zeros(n_end, dtype=bool)
    for i in range(1, n_end):
        if quiet[i - 1] and elevated[i]:
            q2a[i] = True
        if elevated[i - 1] and quiet[i]:
            a2q[i] = True
    return dict(
        QUIET=quiet, ORDINARY=ordinary, ELEVATED=elevated,
        PERSIST_ELEV=persist, Q2A=q2a, A2Q=a2q,
        B_LOW=b_low, B_MID=b_mid, B_HIGH=b_high,
    )


def thin_idx(mask, step=THIN):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return idx
    out = [idx[0]]
    for j in idx[1:]:
        if j >= out[-1] + step:
            out.append(j)
    return np.array(out, dtype=int)


def abs_disp(bc, idx, H):
    out = np.full(len(idx), np.nan)
    for k, i in enumerate(idx):
        if i + H < len(bc):
            out[k] = abs(bc[i + H] - bc[i])
    return out


def bootstrap_mean_diff(a, b, n_boot=N_BOOT, seed=SEED):
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 10 or len(b) < 10:
        return None, (None, None), len(a), len(b)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    na, nb = len(a), len(b)
    for i in range(n_boot):
        diffs[i] = a[rng.integers(0, na, na)].mean() - b[rng.integers(0, nb, nb)].mean()
    return float(a.mean() - b.mean()), (
        float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
    ), na, nb


def analyze(sym):
    df, fh = load(sym)
    n = len(df)
    n_dev = int(0.60 * n)
    n_stab = int(0.80 * n)
    bc = df["bc"].to_numpy(float)
    dow = df["dow"].to_numpy()
    med_spread = float(np.nanmedian(df["spread"].to_numpy(float)[:n_dev]))
    rv, _ = rolling_rv(bc)

    # percentiles on development for primary; recompute for stability window end
    p20, p33, p67, p80 = past_percentiles(rv, dow, n_stab)
    states = classify(rv, p20, p33, p67, p80, n_stab)

    rows = []
    primary = None
    # Primary: ELEVATED vs B_HIGH on development
    for label, mask_s, mask_b in [
        ("ELEVATED_vs_B_HIGH", states["ELEVATED"], states["B_HIGH"]),
        ("QUIET_vs_B_LOW", states["QUIET"], states["B_LOW"]),
        ("ORDINARY_vs_B_MID", states["ORDINARY"], states["B_MID"]),
        ("PERSIST_vs_ELEVATED", states["PERSIST_ELEV"], states["ELEVATED"]),
        ("Q2A_vs_ELEVATED", states["Q2A"], states["ELEVATED"]),
    ]:
        # development only
        ms = mask_s.copy(); ms[n_dev:] = False
        mb = mask_b.copy(); mb[n_dev:] = False
        is_ = thin_idx(ms)
        ib = thin_idx(mb)
        as_ = abs_disp(bc, is_, H_STAR)
        ab = abs_disp(bc, ib, H_STAR)
        diff, ci, na, nb = bootstrap_mean_diff(as_, ab)
        mat = abs(diff) / med_spread if diff is not None and med_spread > 0 else None
        # stability window
        ms2 = mask_s.copy(); ms2[:n_dev] = False; ms2[n_stab:] = False
        mb2 = mask_b.copy(); mb2[:n_dev] = False; mb2[n_stab:] = False
        is2 = thin_idx(ms2); ib2 = thin_idx(mb2)
        as2 = abs_disp(bc, is2, H_STAR); ab2 = abs_disp(bc, ib2, H_STAR)
        stab_diff = None
        if len(as2[~np.isnan(as2)]) >= 20 and len(ab2[~np.isnan(ab2)]) >= 20:
            stab_diff = float(np.nanmean(as2) - np.nanmean(ab2))
        row = dict(
            symbol=sym, contrast=label,
            n_state=na, n_base=nb,
            mean_state=float(np.nanmean(as_)) if na else None,
            mean_base=float(np.nanmean(ab)) if nb else None,
            diff=diff, ci_lo=ci[0], ci_hi=ci[1],
            materiality=mat, med_spread=med_spread,
            sufficient=(na >= MIN_N and nb >= MIN_N),
            stab_diff=stab_diff,
            same_sign=(diff is not None and stab_diff is not None and diff * stab_diff > 0),
            file_hash=fh,
        )
        rows.append(row)
        if label == "ELEVATED_vs_B_HIGH":
            primary = row

    return rows, primary


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
        rows, primary = analyze(sym)
        all_rows.extend(rows)
        primaries.append(primary)
        hashes.append(dict(symbol=sym, sha256=primary["file_hash"], med_spread=primary["med_spread"]))
        p = primary
        print(
            f"  ELEV vs B_HIGH n_s={p['n_state']} n_b={p['n_base']} "
            f"mean_s={p['mean_state']} mean_b={p['mean_base']} diff={p['diff']} "
            f"CI=[{p['ci_lo']},{p['ci_hi']}] mat={p['materiality']} "
            f"suff={p['sufficient']} stab_same={p['same_sign']}",
            flush=True,
        )

    pd.DataFrame(all_rows).to_csv(OUT / "baseline_vs_state_comparison.csv", index=False)
    pd.DataFrame(primaries).to_csv(OUT / "instrument_state_summary.csv", index=False)
    pd.DataFrame(hashes).to_csv(OUT / "dataset_manifest.csv", index=False)

    suff = [p for p in primaries if p["sufficient"]]
    ci_excl = [p for p in suff if p["ci_lo"] is not None and (p["ci_lo"] > 0 or p["ci_hi"] < 0)]
    mat_ok = [p for p in suff if p["materiality"] is not None and p["materiality"] >= 1]
    same_stab = [p for p in suff if p["same_sign"]]

    if len(suff) < 5:
        decision = "INCONCLUSIVE"
    elif len(ci_excl) == 0 or (len(mat_ok) == 0 and len(ci_excl) < 5):
        decision = "CLOSE_AS_NO_USEFUL_INCREMENTAL_INFORMATION"
    elif len(ci_excl) >= 5 and len(mat_ok) == 0:
        decision = "RETAIN_AS_DESCRIPTIVE_ONLY"
    elif len(ci_excl) >= 5 and len(mat_ok) >= 5 and len(same_stab) >= 5:
        decision = "DESCRIPTIVE_STRONG_BUT_NOT_RULEBOOK"  # still not Rulebook
        decision = "RETAIN_AS_DESCRIPTIVE_ONLY"
    else:
        decision = "CLOSE_AS_NO_USEFUL_INCREMENTAL_INFORMATION"

    summary = dict(
        prereg_hash=actual,
        prereg_commit="bed45657c9953ad3210360f76d5a02eb3a49b834",
        primary_contrast="ELEVATED_vs_B_HIGH",
        H_star=H_STAR, n_boot=N_BOOT,
        n_pairs=len(PAIRS), n_sufficient=len(suff),
        n_ci_excludes_0=len(ci_excl), n_mat_ge1=len(mat_ok),
        n_same_sign_stability=len(same_stab),
        decision=decision,
        note="Richer state vs simple vol baseline; Bid-path only; not executable P&L",
        elapsed_sec=round(time.time() - t0, 1),
        instruments=[{
            "symbol": p["symbol"], "n_state": p["n_state"], "n_base": p["n_base"],
            "diff": p["diff"], "ci": [p["ci_lo"], p["ci_hi"]],
            "materiality": p["materiality"], "same_sign": p["same_sign"],
        } for p in primaries],
    )
    (OUT / "market_state_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== DECISION ====", flush=True)
    print(f"suff={len(suff)} ci_excl={len(ci_excl)} mat>=1={len(mat_ok)} stab={len(same_stab)}", flush=True)
    print(f"DECISION: {decision}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
