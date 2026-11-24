"""The assessment's figures from `compare.py`'s frames (2026-11-24; disposable).

    python experiments/lookdev_pcss/figures.py experiments/lookdev_pcss/out docs/research/lookdev_pcss_assets_2026-11-24

Each figure: rows = key sizes, columns = the named variants, then the signed difference of each to REF (red = brighter
than REF, blue = darker, x 4); halved in size (2 x 2 mean) once or twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE.parents[1] / "src", HERE.parents[0] / "lookdev_diffuse_area"):
    sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from analyze import LUMA, load_png  # noqa: E402
from run_compare import diff_map, sheet, write_png  # noqa: E402

#: name: (frame tag without size, sizes, variants (REF last), crop (top, bottom, left, right), halve)
FIGURES = {
    "manu_nose_cheek_creatureskin": ("gollum_manu_CreatureSkinM", ("025", "045", "100"), ("P", "K16c", "REF"),
                                     (0.25, 0.95, 0.05, 0.85), True),
    "manu_nose_cheek_neutral": ("gollum_manu_Neutral", ("045", "100"), ("P", "K16c", "REF"),
                                (0.25, 0.95, 0.05, 0.85), True),
    "face_creatureskin": ("gollum_face_CreatureSkinM", ("025", "100"), ("P", "F", "K16c", "REF"),
                          (0.0, 1.0, 0.0, 1.0), 2),
    "face_nose_mouth_creatureskin": ("gollum_face_CreatureSkinM", ("000", "045"), ("P", "K16c", "REF"),
                                     (0.38, 1.0, 0.25, 1.0), True),
    "shapes_neutral": ("shapes_front_Neutral", ("025", "045", "100"), ("P", "K16c", "REF"), (0.0, 1.0, 0.0, 1.0),
                       True),
}


def halve(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[0] // 2 * 2, img.shape[1] // 2 * 2
    x = img[:h, :w].astype(np.float64)
    return np.round((x[0::2, 0::2] + x[1::2, 0::2] + x[0::2, 1::2] + x[1::2, 1::2]) / 4.0).astype(np.uint8)


def figure(frames: Path, tag: str, sizes, variants, box, half: bool) -> np.ndarray:
    rows = []
    for size in sizes:
        imgs = [load_png(frames / f"{tag}_s{size}_{v}.png") for v in variants]
        h, w = imgs[0].shape[:2]
        t, b, l, r = int(box[0] * h), int(box[1] * h), int(box[2] * w), int(box[3] * w)
        imgs = [i[t:b, l:r].astype(np.uint8) for i in imgs]
        ref = imgs[-1]
        mask = (ref.astype(np.float64) @ LUMA) > 6.0
        row = imgs + [diff_map(i, ref, mask) for i in imgs[:-1]]
        for _ in range(int(half)):
            row = [halve(i) for i in row]
        rows.append(row)
    return sheet(rows)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out, dest = Path(argv[0]), Path(argv[1])
    dest.mkdir(parents=True, exist_ok=True)
    for name, (tag, sizes, variants, box, half) in FIGURES.items():
        path = dest / f"{name}.png"
        write_png(path, figure(out / "frames", tag, sizes, variants, box, half))
        print(path, path.stat().st_size // 1024, "KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
