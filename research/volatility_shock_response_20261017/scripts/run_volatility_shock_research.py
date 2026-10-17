#!/usr/bin/env python3
"""Volatility-shock response. Prereg c8647f3291412b64c45fddf96b0014df5bf0b5d1."""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
PREREG = ROOT / "docs/AEGIS_VOLATILITY_SHOCK_PREREGISTRATION.md"
HASH_FILE = OUT / "preregistration_hash.txt"

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]
LOOKBACK, THRESH, H_STAR, COOLDOWN = 20, 2.0, 12, 12
SEED, N_BOOT, MIN_MATCHED = 20261017, 500, 80


def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df["bc"] = df["bid_close"].astype(float)
    df["spread"] = (df["ask_close"] - df["bid_close"]).astype(float)
    df["hour"] = df["datetime"].dt.hour
    return df, h


def build_features(df):
    bc = df["bc"].to_numpy(float)
    n = len(bc)
    disp = np.zeros(n)
    disp[1:] = np.abs(bc[1:] - bc[:-1])
    cs = np.cumsum(disp)
    pre_vol = np.full(n, np.nan)
    idx = np.arange(LOOKBACK + 1, n)
    pre_vol[idx] = (cs[idx - 1] - cs[idx - LOOKBACK - 1]) / LOOKBACK
    direction = np.zeros(n)
    direction[1:] = np.sign(bc[1:] - bc[:-1])
    ratio = np.where(pre_vol > 0, disp / pre_vol, np.nan)
    return disp, pre_vol, direction, ratio, bc


def find_shocks(ratio, direction, n_end, cooldown=COOLDOWN):
    shocks = []
    last = -10**9
    for i in range(LOOKBACK + 1, n_end):
        if np.isnan(ratio[i]) or direction[i] == 0:
            continue
        if ratio[i] >= THRESH and i >= last + cooldown:
            shocks.append(i)
            last = i
    return np.array(shocks, dtype=int)


def signed_r_arr(bc, direction, indices, H):
    out = np.full(len(indices), np.nan)
    for k, i in enumerate(indices):
        if i + H < len(bc):
            out[k] = direction[i] * (bc[i + H] - bc[i])
    return out


def bootstrap_diff(shock_r, ctrl_r, n_boot=N_BOOT, seed=SEED):
    shock_r = np.asarray(shock_r, float)
    ctrl_r = np.asarray(ctrl_r, float)
    shock_r = shock_r[~np.isnan(shock_r)]
    ctrl_r = ctrl_r[~np.isnan(ctrl_r)]
    if len(shock_r) < 10 or len(ctrl_r) < 10:
        return None, (None, None)
    rng = np.random.default_rng(seed)
    ns, nc = len(shock_r), len(ctrl_r)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        diffs[b] = shock_r[rng.integers(0, ns, ns)].mean() - ctrl_r[rng.integers(0, nc, nc)].mean()
    return float(shock_r.mean() - ctrl_r.mean()), (
        float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
    )


def match_all(shocks, ratio, direction, disp, pre_vol, hour, n_end):
    pools = {h: [] for h in range(24)}
    for j in range(LOOKBACK + 1, n_end):
        if np.isnan(ratio[j]) or ratio[j] >= THRESH or direction[j] == 0:
            continue
        pools[int(hour[j])].append(j)
    pools = {h: np.array(v, dtype=int) for h, v in pools.items() if v}

    matched_i, ctrl_lists, n_unmatched = [], [], 0
    for i in shocks:
        h = int(hour[i])
        if h not in pools or pre_vol[i] <= 0 or disp[i] <= 0:
            n_unmatched += 1
            continue
        cand = pools[h]
        mask = (cand >= i - 1500) & (cand <= i + 1500) & (cand != i)
        cand = cand[mask]
        if len(cand) == 0:
            n_unmatched += 1
            continue
        pv, d0 = pre_vol[i], disp[i]
        ok = (
            (pre_vol[cand] >= pv * 0.75) & (pre_vol[cand] <= pv * 1.25)
            & (disp[cand] >= d0 * 0.5) & (disp[cand] <= d0 * 1.5)
        )
        cand = cand[ok]
        if len(cand) == 0:
            n_unmatched += 1
            continue
        order = np.argsort(np.abs(cand - i))[:3]
        matched_i.append(int(i))
        ctrl_lists.append(cand[order])
    return matched_i, ctrl_lists, n_unmatched


def analyze(sym):
    df, fh = load(sym)
    n = len(df)
    n_dev = int(0.60 * n)
    n_stab_end = int(0.80 * n)
    med_spread = float(np.nanmedian(df["spread"].to_numpy(float)[:n_dev]))
    disp, pre_vol, direction, ratio, bc = build_features(df)
    hour = df["hour"].to_numpy()

    shocks_dev = find_shocks(ratio, direction, n_dev)
    matched_i, ctrl_lists, n_unmatched = match_all(
        shocks_dev, ratio, direction, disp, pre_vol, hour, n_dev
    )
    n_matched = len(matched_i)
    shock_idx = np.array(matched_i, dtype=int)
    primary_s = signed_r_arr(bc, direction, shock_idx, H_STAR) if len(shock_idx) else np.array([])
    ctrl_idx = np.array([j for cl in ctrl_lists for j in cl], dtype=int) if ctrl_lists else np.array([], dtype=int)
    primary_c = signed_r_arr(bc, direction, ctrl_idx, H_STAR) if len(ctrl_idx) else np.array([])

    diff, ci = bootstrap_diff(primary_s, primary_c)
    cont_s = float(np.nanmean(primary_s > 0)) if len(primary_s) else None
    cont_c = float(np.nanmean(primary_c > 0)) if len(primary_c) else None
    mat = abs(diff) / med_spread if diff is not None and med_spread > 0 else None

    shocks_stab = find_shocks(ratio, direction, n_stab_end)
    shocks_stab = shocks_stab[shocks_stab >= n_dev]
    mi2, cl2, _ = match_all(shocks_stab, ratio, direction, disp, pre_vol, hour, n_stab_end)
    stab_s = signed_r_arr(bc, direction, np.array(mi2, int), H_STAR) if mi2 else np.array([])
    c2 = np.array([j for cl in cl2 for j in cl], dtype=int) if cl2 else np.array([], dtype=int)
    stab_c = signed_r_arr(bc, direction, c2, H_STAR) if len(c2) else np.array([])
    stab_diff = None
    if len(stab_s) >= 20 and len(stab_c) >= 20:
        stab_diff = float(np.nanmean(stab_s) - np.nanmean(stab_c))

    return dict(
        symbol=sym, file_hash=fh, rows=n, n_dev=n_dev, med_spread=med_spread,
        n_shocks_dedup=int(len(shocks_dev)), n_matched=n_matched, n_unmatched=n_unmatched,
        n_shock_obs=int(np.sum(~np.isnan(primary_s))) if len(primary_s) else 0,
        n_ctrl_obs=int(np.sum(~np.isnan(primary_c))) if len(primary_c) else 0,
        mean_r_shock=float(np.nanmean(primary_s)) if len(primary_s) else None,
        mean_r_ctrl=float(np.nanmean(primary_c)) if len(primary_c) else None,
        cont_rate_shock=cont_s, cont_rate_ctrl=cont_c,
        diff_mean=diff, ci_lo=ci[0], ci_hi=ci[1], materiality=mat,
        sufficient=n_matched >= MIN_MATCHED, stab_diff=stab_diff,
        same_sign_stab=(diff is not None and stab_diff is not None and (diff * stab_diff > 0)),
    )


def main():
    t0 = time.time()
    actual = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    recorded = HASH_FILE.read_text().split()[0]
    assert actual == recorded, f"hash mismatch {actual} {recorded}"
    print(f"Prereg OK {actual[:16]}...", flush=True)
    results, hashes = [], []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        r = analyze(sym)
        results.append(r)
        hashes.append(dict(symbol=sym, sha256=r["file_hash"], med_spread=r["med_spread"]))
        print(
            f"  matched={r['n_matched']} mean_s={r['mean_r_shock']} mean_c={r['mean_r_ctrl']} "
            f"diff={r['diff_mean']} CI=[{r['ci_lo']},{r['ci_hi']}] cont_s={r['cont_rate_shock']} "
            f"mat={r['materiality']} suff={r['sufficient']} stab_same={r['same_sign_stab']}",
            flush=True,
        )
    pd.DataFrame(results).to_csv(OUT / "instrument_summary.csv", index=False)
    pd.DataFrame(hashes).to_csv(OUT / "dataset_manifest.csv", index=False)
    pd.DataFrame(results).to_csv(OUT / "shock_control_comparison.csv", index=False)

    suff = [r for r in results if r["sufficient"]]
    ci_excl = [r for r in suff if r["ci_lo"] is not None and (r["ci_lo"] > 0 or r["ci_hi"] < 0)]
    mat_ok = [r for r in suff if r["materiality"] is not None and r["materiality"] >= 1]
    same_stab = [r for r in suff if r["same_sign_stab"]]
    pos = [r for r in ci_excl if (r["diff_mean"] or 0) > 0]
    neg = [r for r in ci_excl if (r["diff_mean"] or 0) < 0]

    if len(suff) < 5:
        decision = "F_INSUFFICIENT_DATA"
    elif len(ci_excl) == 0:
        decision = "A_NO_MATERIAL_CONDITIONAL_EFFECT"
    elif len(ci_excl) >= 5 and len(mat_ok) < 5:
        decision = "C_STATISTICAL_BUT_ECONOMICALLY_WEAK"
    elif len(ci_excl) >= 5 and len(mat_ok) >= 5 and len(same_stab) >= 5:
        decision = "E_PROMISING"
    elif len(ci_excl) < 5:
        decision = "D_INSTRUMENT_SPECIFIC_OR_UNSTABLE"
    else:
        decision = "C_STATISTICAL_BUT_ECONOMICALLY_WEAK"

    summary = dict(
        prereg_hash=actual, prereg_commit="c8647f3291412b64c45fddf96b0014df5bf0b5d1",
        thresh=THRESH, lookback=LOOKBACK, H_star=H_STAR, n_boot=N_BOOT,
        n_pairs=len(PAIRS), n_sufficient=len(suff), n_ci_excludes_0=len(ci_excl),
        n_mat_ge1=len(mat_ok), n_same_sign_stability=len(same_stab),
        n_continuation_effect=len(pos), n_reversal_effect=len(neg),
        decision=decision, elapsed_sec=round(time.time() - t0, 1),
        instruments=[{
            "symbol": r["symbol"], "n_matched": r["n_matched"],
            "mean_r_shock": r["mean_r_shock"], "mean_r_ctrl": r["mean_r_ctrl"],
            "diff": r["diff_mean"], "ci": [r["ci_lo"], r["ci_hi"]],
            "cont_shock": r["cont_rate_shock"], "cont_ctrl": r["cont_rate_ctrl"],
            "materiality": r["materiality"], "stab_diff": r["stab_diff"],
        } for r in results],
    )
    (OUT / "volatility_shock_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== DECISION ====", flush=True)
    print(f"suff={len(suff)} ci_excl={len(ci_excl)} mat>=1={len(mat_ok)} stab={len(same_stab)}", flush=True)
    print(f"continuation={len(pos)} reversal={len(neg)}", flush=True)
    print(f"DECISION: {decision}", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
