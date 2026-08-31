"""
Improved v3 extraction pass, round 2.

Key change from the first pipeline: price-panel BB34/BB17 U/M/L values
are now derived with the SAME algorithm as production's
BrainCVService._band_ulm() (sort rightmost-column pixel rows, split
into thirds) instead of gap-based clustering. This:

  1. Always produces exactly 3 values (never fails/drops a frame for
     "couldn't find 3 clusters"), which was the single biggest cause
     of data loss in the first pass (107/313 frames, concentrated
     exactly in CONTRACTION moments when bands converge).
  2. Matches what the live system will actually compute at inference
     time, which matters more than raw yield: training on a different
     extraction method than production uses would silently bias the
     model.

RSI-panel values (f7-f11) are still taken from the OCR'd text overlay,
unchanged from the first pass (that path was reliable).
"""
import re, os, glob, json
import numpy as np
from PIL import Image
import pytesseract

SRC = "/home/claude/rulebook_data/Rulebook_v3_Test_Screenshorts"
OUT = "/home/claude/pipeline"


def ocr_rsi_line(im):
    crop = im.convert("L").crop((0, 495, 900, 517))
    arr = np.array(crop).astype(np.float32)
    arr = np.clip(arr, 0, 5) / 5 * 255
    out = Image.fromarray(arr.astype(np.uint8))
    out = out.resize((out.width * 3, out.height * 3), Image.LANCZOS)
    inv = Image.fromarray(255 - np.array(out))
    txt = pytesseract.image_to_string(
        inv, config="--psm 7 -c tessedit_char_whitelist=0123456789.RSI()MAnds"
    )
    return txt.strip()


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
    """Same approach as production _band_ulm(): sort, split into
    thirds. gap_merge first collapses near-duplicate antialiasing rows
    so a single thick line doesn't get incorrectly treated as spread
    across all 3 output slots."""
    if not rows:
        return None
    rows = sorted(rows)
    # collapse consecutive near-duplicates (antialiasing) before splitting
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
    white_rows = white_rows[white_rows > 4].tolist()
    cyan_rows = cyan_rows[cyan_rows > 4].tolist()
    return white_rows, cyan_rows


def parse_ts(fn):
    m = re.search(r"(\d{8})-(\d{6})", fn)
    return m.group(1) + m.group(2) if m else fn


def main():
    raw_cache_path = os.path.join(OUT, "raw_extraction.json")
    files = sorted(glob.glob(os.path.join(SRC, "*.png")))

    recs = []
    n_ocr_fail = 0
    n_no_pixels = 0
    for i, fp in enumerate(files):
        fn = os.path.basename(fp)
        im = Image.open(fp)
        raw = ocr_rsi_line(im)
        parsed = parse_rsi_block(raw)
        white_rows, cyan_rows = extract_price_bands_raw(im)

        if parsed is None:
            n_ocr_fail += 1
            continue
        if not white_rows or not cyan_rows:
            n_no_pixels += 1
            continue

        f7, f8, f9, f10, f11 = parsed
        w = band_ulm(white_rows)   # raw pixel-Y, U/M/L - this IS price_band7
        c = band_ulm(cyan_rows)    # raw pixel-Y, U/M/L - this IS price_band8

        recs.append(dict(
            file=fn, ts=parse_ts(fn),
            # raw pixel-Y band dicts, matching production's frame_state convention
            # (smaller Y = higher on chart = higher value) directly, no sign flip needed
            p7_U=w["U"], p7_M=w["M"], p7_L=w["L"],
            p8_U=c["U"], p8_M=c["M"], p8_L=c["L"],
            # OCR'd REAL values (bigger = higher RSI/MA/Band value) - negate before
            # feeding into the pixel-Y-convention engine/feature-extractor
            rsi6_val=f7, ma4_val=f8, b1_U_val=f9, b1_M_val=f10, b1_L_val=f11,
        ))
        if i % 50 == 0:
            print(i, fn, "ok")

    print(f"Total files: {len(files)}  OCR fail: {n_ocr_fail}  no pixels: {n_no_pixels}  parsed: {len(recs)}")

    import pandas as pd
    df = pd.DataFrame(recs).sort_values("ts").reset_index(drop=True)

    # Sanity filters (catch OCR digit-drop errors on the RSI overlay -
    # the pixel-based price features can't have this failure mode since
    # they're not OCR'd, so no equivalent filter needed there).
    val_cols = ["rsi6_val", "ma4_val", "b1_U_val", "b1_M_val", "b1_L_val"]
    mask = df[val_cols].apply(lambda c: c.between(-10, 110)).all(axis=1)
    df = df[mask].reset_index(drop=True)
    mask2 = (df["b1_U_val"] > df["b1_M_val"]) & (df["b1_M_val"] > df["b1_L_val"])
    df = df[mask2].reset_index(drop=True)

    all_cols = ["p7_U", "p7_M", "p7_L", "p8_U", "p8_M", "p8_L"] + val_cols
    dup = (df[all_cols].diff().abs().sum(axis=1) == 0)
    df = df[~dup].reset_index(drop=True)

    print(f"After sanity filters: {len(df)} rows (was {len(recs)} before filtering, {len(files)} screenshots total)")
    df.to_csv(os.path.join(OUT, "features_v2.csv"), index=False)
    return df


if __name__ == "__main__":
    df = main()
    print(df.describe())
