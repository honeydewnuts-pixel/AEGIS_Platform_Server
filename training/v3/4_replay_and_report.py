"""
Screenshot replay & QA harness for AEGIS v3.

WHY THIS EXISTS
----------------
Training metrics (holdout accuracy, CV F1, etc.) tell you how well the
model fits rule-derived labels. They do NOT tell you whether the signals
"look right" to someone who actually understands the chart. This script
closes that gap: point it at a folder of screenshots, and it replays them
through the REAL production code (SignalRuleEngineV3 +
NeuralAssistServiceV3, same classes brain_cv_service.py uses) in
chronological order, then produces:

  1. report.csv    - one row per screenshot: signal, which rule fired,
                      confidence, neural probabilities, contraction/
                      expansion state. Good for spotting patterns
                      (e.g. "BUY only ever fires during EXPANSION" -
                      is that expected?).
  2. review.html    - a scrollable page with the actual screenshot
                      thumbnail next to its signal, so you can eyeball
                      "did this look like a BUY on the chart?" without
                      opening 300 files one at a time.

This is a QA tool, not a backtester: it doesn't know what the price did
AFTER a signal, so it can't tell you if a BUY would have made money. It
only tells you whether the signal is internally consistent and matches
what you'd expect a human to see on the chart at that moment.

USAGE
-----
    python3 4_replay_and_report.py --screenshots_dir /path/to/pngs --out_dir /path/to/report

Requires: PIL, pytesseract, numpy, pandas, and the AEGIS backend package
on PYTHONPATH (same requirement as the training scripts).
"""
import argparse
import base64
import glob
import io
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
import pytesseract


def ocr_rsi_line(im):
    crop = im.convert("L").crop((0, 495, 900, 517))
    arr = np.array(crop).astype(np.float32)
    arr = np.clip(arr, 0, 5) / 5 * 255
    out = Image.fromarray(arr.astype(np.uint8))
    out = out.resize((out.width * 3, out.height * 3), Image.LANCZOS)
    inv = Image.fromarray(255 - np.array(out))
    return pytesseract.image_to_string(
        inv, config="--psm 7 -c tessedit_char_whitelist=0123456789.RSI()MAnds"
    ).strip()


def parse_rsi_block(raw):
    m = re.search(r"RSI\(9\)(\d+\.\d{2})MA\(7\)(\d+\.\d{3})\D*(\d.*)$", raw)
    if not m:
        return None
    rsi = float(m.group(1))
    ma = float(m.group(2))
    bands = re.findall(r"\d{1,3}\.\d{4}", m.group(3))
    if len(bands) != 3:
        return None
    m_, u_, l_ = float(bands[0]), float(bands[1]), float(bands[2])
    return rsi, ma, u_, m_, l_


def band_ulm(rows, gap_merge=2):
    if not rows:
        return None
    rows = sorted(rows)
    collapsed = [rows[0]]
    for r in rows[1:]:
        if r - collapsed[-1] > gap_merge:
            collapsed.append(r)
        else:
            collapsed[-1] = (collapsed[-1] + r) / 2
    if len(collapsed) == 1:
        y = collapsed[0]
        return {"U": y - 4.0, "M": y, "L": y + 4.0}
    if len(collapsed) == 2:
        return {"U": collapsed[0], "M": (collapsed[0] + collapsed[1]) / 2, "L": collapsed[1]}
    thirds = np.array_split(collapsed, 3)
    u, m, l = [float(np.mean(part)) for part in thirds]
    return {"U": u, "M": m, "L": l}


def extract_price_bands_raw(im, x0=1258, x1=1290, y0=0, y1=470):
    arr = np.array(im.convert("RGB"))[y0:y1, x0:x1, :]
    r = arr[..., 0].astype(int); g = arr[..., 1].astype(int); b = arr[..., 2].astype(int)
    white_mask = (r > 150) & (g > 150) & (b > 150)
    cyan_mask = (b > 150) & (g > 150) & (r < 100)
    white_rows = np.where(white_mask.any(axis=1))[0]
    cyan_rows = np.where(cyan_mask.any(axis=1))[0]
    return white_rows[white_rows > 4].tolist(), cyan_rows[cyan_rows > 4].tolist()


def parse_ts(fn):
    m = re.search(r"(\d{8})-(\d{6})", fn)
    return m.group(1) + m.group(2) if m else fn


def extract_all(screenshots_dir):
    files = sorted(glob.glob(os.path.join(screenshots_dir, "*.png")))
    rows = []
    for fp in files:
        fn = os.path.basename(fp)
        im = Image.open(fp)
        raw = ocr_rsi_line(im)
        parsed = parse_rsi_block(raw)
        white_rows, cyan_rows = extract_price_bands_raw(im)
        status = "ok"
        if parsed is None:
            status = "ocr_fail"
        elif not white_rows or not cyan_rows:
            status = "no_band_pixels"
        rows.append(dict(file=fn, path=fp, ts=parse_ts(fn), status=status,
                          parsed=parsed, white_rows=white_rows, cyan_rows=cyan_rows))
    rows.sort(key=lambda r: r["ts"])
    return rows


def build_frame(row):
    if row["status"] != "ok":
        return None
    rsi, ma, b1u, b1m, b1l = row["parsed"]
    w = band_ulm(row["white_rows"])
    c = band_ulm(row["cyan_rows"])
    if w is None or c is None:
        return None
    if not (b1u > b1m > b1l):
        return None  # OCR digit-drop guard, same as training pipeline
    return {
        "price_band7": w,
        "price_band8": c,
        "rsi6": -rsi,
        "ma4": -ma,
        "band1": {"U": -b1u, "M": -b1m, "L": -b1l},
    }


def thumbnail_data_uri(path, max_w=360):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    scale = max_w / w
    im = im.resize((max_w, int(h * scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screenshots_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--backend_path", default=None,
                     help="Path to the AEGIS backend/ directory (defaults to ../backend relative to this script)")
    ap.add_argument("--no_thumbnails", action="store_true",
                     help="Skip embedding screenshot thumbnails in review.html (much smaller/faster output)")
    args = ap.parse_args()

    backend_path = args.backend_path or str(Path(__file__).resolve().parent.parent / "backend")
    sys.path.insert(0, backend_path)
    from app.services.signal_rule_engine_v3 import SignalRuleEngineV3
    from app.services.neural_features_v3 import extract_feature_vector
    import math

    def load_neural_model():
        model_path = Path(backend_path) / "app" / "models" / "aegis_neural_v3.json"
        return json.loads(model_path.read_text())

    def predict(model, vector):
        norm = model["normalization"]
        mean, std = norm["mean"], norm["std"]
        x = [(float(v) - float(m)) / max(float(s), 1e-6) for v, m, s in zip(vector, mean, std)]
        for layer in model["layers"]:
            w, b = layer["weight"], layer["bias"]
            x = [sum(wi * xi for wi, xi in zip(row, x)) + bi for row, bi in zip(w, b)]
            if layer.get("activation") == "tanh":
                x = [math.tanh(v) for v in x]
        m_ = max(x)
        ex = [math.exp(v - m_) for v in x]
        s = sum(ex) or 1.0
        probs = [v / s for v in ex]
        return dict(zip(model["classes"], probs))

    engine = SignalRuleEngineV3()
    neural_model = load_neural_model()

    raw_rows = extract_all(args.screenshots_dir)
    print(f"Found {len(raw_rows)} screenshots. Extracting...")

    frames = []
    report_rows = []
    for row in raw_rows:
        frame = build_frame(row)
        entry = {"file": row["file"], "ts": row["ts"], "status": row["status"]}
        if frame is None:
            entry.update({"signal": None, "rule_name": "extraction_failed", "reason": row["status"],
                          "contraction": None, "expansion": None,
                          "neural_probs": None, "neural_signal": None})
            report_rows.append(entry)
            continue

        frames.append(frame)
        result = engine.evaluate(frames)
        feats = extract_feature_vector(frames)
        probs = predict(neural_model, feats["vector"])
        nn_signal = max(("BUY", probs["BUY"]), ("SELL", probs["SELL"]), key=lambda x: x[1])[0]

        entry.update({
            "signal": result.signal or "HOLD",
            "rule_name": result.rule_name,
            "reason": result.reason,
            "contraction": engine._contraction(frame),
            "expansion": engine._expansion(frame),
            "neural_probs": {k: round(v, 3) for k, v in probs.items()},
            "neural_signal": nn_signal,
            "neural_score": round(max(probs["BUY"], probs["SELL"]), 3),
        })
        report_rows.append(entry)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(report_rows)
    df.to_csv(out_dir / "report.csv", index=False)

    ok = df[df["status"] == "ok"]
    print(f"\nExtraction: {len(ok)}/{len(df)} usable frames "
          f"({(df['status']=='ocr_fail').sum()} OCR fail, {(df['status']=='no_band_pixels').sum()} no band pixels)")
    print("Rule-engine signal counts:\n", ok["signal"].value_counts())
    fired = ok[ok["signal"] != "HOLD"]
    print(f"\n{len(fired)} non-HOLD signals fired - see review.html to eyeball each one against its screenshot.")

    # ---- HTML review page ----
    rows_html = []
    for _, r in df.iterrows():
        if r["status"] != "ok":
            badge = f'<span class="badge fail">{r["status"]}</span>'
            probs_html = ""
        else:
            sig = r["signal"]
            cls = {"BUY": "buy", "SELL": "sell", "HOLD": "hold"}.get(sig, "hold")
            regime = "CONTRACTION" if r["contraction"] else ("EXPANSION" if r["expansion"] else "neutral")
            badge = f'<span class="badge {cls}">{sig}</span> <span class="rule">{r["rule_name"]}</span> <span class="regime">{regime}</span>'
            np_ = r["neural_probs"] if isinstance(r["neural_probs"], dict) else {}
            probs_html = (f'<div class="probs">NN: {r["neural_signal"]} '
                          f'(H={np_.get("HOLD","?")} S={np_.get("SELL","?")} B={np_.get("BUY","?")})</div>')
        thumb = ""
        if not args.no_thumbnails:
            path = next((row["path"] for row in raw_rows if row["file"] == r["file"]), None)
            if path:
                try:
                    thumb = f'<img src="{thumbnail_data_uri(path)}"/>'
                except Exception:
                    thumb = ""
        rows_html.append(f'''
        <div class="row">
          <div class="thumb">{thumb}</div>
          <div class="meta">
            <div class="fn">{r["file"]}</div>
            {badge}
            {probs_html}
            <div class="reason">{r.get("reason","")}</div>
          </div>
        </div>''')

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AEGIS v3 Screenshot Replay Review</title>
<style>
body {{ font-family: -apple-system, sans-serif; background:#111; color:#eee; margin:0; padding:16px; }}
h1 {{ font-size:18px; }}
.summary {{ margin-bottom:16px; color:#aaa; }}
.row {{ display:flex; gap:12px; border-bottom:1px solid #333; padding:10px 0; align-items:center; }}
.thumb img {{ max-width:360px; border-radius:4px; display:block; }}
.meta {{ flex:1; }}
.fn {{ font-size:11px; color:#888; margin-bottom:4px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:13px; }}
.badge.buy {{ background:#1b5e20; color:#a5d6a7; }}
.badge.sell {{ background:#5d1a1a; color:#ef9a9a; }}
.badge.hold {{ background:#333; color:#999; }}
.badge.fail {{ background:#4a3800; color:#ffcc80; }}
.rule {{ color:#888; font-size:12px; margin-left:6px; }}
.regime {{ color:#5c9aff; font-size:12px; margin-left:6px; }}
.probs {{ font-size:12px; color:#bbb; margin-top:4px; }}
.reason {{ font-size:11px; color:#666; margin-top:4px; max-width:700px; }}
</style></head>
<body>
<h1>AEGIS v3 Screenshot Replay Review</h1>
<div class="summary">{len(ok)}/{len(df)} usable frames &middot; {len(fired)} non-HOLD signals &middot;
generated from {args.screenshots_dir}</div>
{"".join(rows_html)}
</body></html>'''

    (out_dir / "review.html").write_text(html, encoding="utf-8")
    print(f"\nWrote {out_dir/'report.csv'} and {out_dir/'review.html'}")


if __name__ == "__main__":
    main()
