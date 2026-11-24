"""Per-region numbers from `compare.py`'s frames (2026-11-24; disposable).

    python experiments/lookdev_pcss/analyze.py <out dir> [--sizes 025,045,100] [--variants P,K16,...]

As `experiments/lookdev_diffuse_area/analyze.py` (its regions for "face", "framed" and the shapes; the luminance error
against REF in display values 0..255: mean |error|, the share > 8/255 brighter / darker, p99 of "brighter"), with the
regions of Manu's view "manu" added and the baseline P (production today) for `new+` (the share of pixels > 8/255
brighter than REF in the variant but not in P: light a variant *adds* - a leak, a bright rim) and `new-` (darker, not
in P: a new dark blotch). Writes `regions.txt` and prints a compact table (mae per region).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "lookdev_diffuse_area"))

import numpy as np  # noqa: E402

import analyze as base  # noqa: E402

REGIONS = dict(base.REGIONS)
#: Manu's view (the camera on the shadow side, AD-039 §23.6): (top, bottom, left, right) fractions of the frame
REGIONS["gollum_manu"] = {"nose_cheek": (0.30, 0.75, 0.15, 0.70), "nostril": (0.42, 0.60, 0.68, 0.88),
                          "mouth": (0.80, 0.97, 0.50, 0.80), "cheek_shadow": (0.30, 0.90, 0.0, 0.25)}


def stats(img, ref, p, box) -> dict:
    h, w = ref.shape[:2]
    t, b, l, r = (int(round(box[0] * h)), int(round(box[1] * h)), int(round(box[2] * w)), int(round(box[3] * w)))
    lum = lambda x: x[t:b, l:r] @ base.LUMA  # noqa: E731
    ref_l = lum(ref)
    mask = ref_l > 6.0
    d = (lum(img) - ref_l)[mask]
    dp = (lum(p) - ref_l)[mask]
    if d.size == 0:
        return {}
    return {"mae": float(np.mean(np.abs(d))), "brighter": float(np.mean(d > base.THRESHOLD)),
            "darker": float(np.mean(d < -base.THRESHOLD)), "p99+": float(np.percentile(np.maximum(d, 0), 99)),
            "new+": float(np.mean((d > base.THRESHOLD) & (dp <= base.THRESHOLD))),
            "new-": float(np.mean((d < -base.THRESHOLD) & (dp >= -base.THRESHOLD)))}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0])
    sizes = variants = None
    if "--sizes" in argv:
        sizes = set(argv[argv.index("--sizes") + 1].split(","))
    if "--variants" in argv:
        variants = argv[argv.index("--variants") + 1].split(",")
    sets: dict = {}
    for f in sorted((out / "frames").glob("*.png")):
        m = re.match(r"(?P<scene>[a-z]+)_(?P<view>[a-z]+)_(?P<mat>[A-Za-z]+)_s(?P<size>\d{3})_(?P<var>.+)\.png", f.name)
        if m and (sizes is None or m["size"] in sizes):
            sets.setdefault((m["scene"], m["view"], m["mat"], m["size"]), {})[m["var"]] = f
    lines, table = [], []
    for (scene, view, mat, size), files in sets.items():
        if "REF" not in files or "P" not in files:
            continue
        ref, p = base.load_png(files["REF"]), base.load_png(files["P"])
        regions = REGIONS.get(f"{scene}_{view}", {"all": (0.0, 1.0, 0.0, 1.0)})
        head = f"{scene}/{view}/{mat}/size {int(size) / 100:g}"
        lines.append(head)
        table.append(f"{head:<40} " + " ".join(f"{name[:12]:>12}" for name in regions))
        names = [v for v in (variants or files) if v in files and v != "REF" and "beauty" not in v]
        for var in names:
            img = base.load_png(files[var])
            cells, maes = [], []
            for name, box in regions.items():
                s = stats(img, ref, p, box)
                cells.append(f"{name} {s['mae']:4.1f} +{100 * s['brighter']:4.1f}% -{100 * s['darker']:4.1f}% "
                             f"p99+ {s['p99+']:4.1f} new+ {100 * s['new+']:4.1f}% new- {100 * s['new-']:4.1f}%")
                maes.append(f"{s['mae']:12.2f}")
            lines.append(f"  {var:<12} " + " | ".join(cells))
            table.append(f"  {var:<38} " + " ".join(maes))
    (out / "regions.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "regions_mae.txt").write_text("\n".join(table) + "\n", encoding="utf-8")
    print("\n".join(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
