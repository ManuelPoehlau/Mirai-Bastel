"""Zoomed crops of `compare.py` frames side by side (2026-11-24; disposable).

    python experiments/lookdev_pcss/zoom.py <out dir> <frame tag> <variants,...> [top bottom left right] [--diff]

The box is in fractions of the frame (default: the nose -> cheek of the "manu" view); rows of at most 4 images.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE.parents[1] / "src", HERE.parents[0] / "lookdev_diffuse_area"):
    sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from analyze import LUMA, load_png  # noqa: E402
from run_compare import diff_map, sheet, write_png  # noqa: E402


def main(argv):
    diff = "--diff" in argv
    argv = [a for a in argv if a != "--diff"]
    out, tag, variants = Path(argv[0]), argv[1], argv[2].split(",")
    box = tuple(float(v) for v in argv[3:7]) if len(argv) >= 7 else (0.2, 0.9, 0.0, 0.6)
    imgs = []
    for v in variants:
        im = load_png(out / "frames" / f"{tag}_{v}.png")
        h, w = im.shape[:2]
        t, b, l, r = int(box[0] * h), int(box[1] * h), int(box[2] * w), int(box[3] * w)
        imgs.append(im[t:b, l:r].astype(np.uint8))
    if diff:
        ref = imgs[-1]
        mask = (ref.astype(np.float64) @ LUMA) > 6.0
        imgs = imgs + [diff_map(i, ref, mask) for i in imgs[:-1]]
    rows = [imgs[i:i + 4] for i in range(0, len(imgs), 4)]
    while len(rows[-1]) < 4 and len(rows) > 1:
        rows[-1].append(np.zeros_like(imgs[0]))
    name = out / f"zoom_{tag}_{'-'.join(variants)[:60]}{'_diff' if diff else ''}.png"
    write_png(name, sheet(rows))
    print(name)


if __name__ == "__main__":
    main(sys.argv[1:])
