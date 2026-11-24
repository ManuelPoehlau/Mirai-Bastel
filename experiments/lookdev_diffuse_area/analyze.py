"""Per-region numbers from `run_compare.py`'s frames (2026-11-24; disposable).

    python experiments/lookdev_diffuse_area/analyze.py <out dir>

Regions are boxes in the cropped frames, as fractions (top, bottom, left, right) of the frame: `REGIONS[scene/view]`.
For every frame set (scene, view, material, size) and variant: the luminance error against REF (display values
0..255) per region - mean |error|, the share more than 8/255 brighter / darker, the 99th percentile of "brighter" -
and `new+`: the share of pixels that are > 8/255 brighter than REF in the variant but not in A (light the variant
*adds* where the truth has none: a leak or a bright rim).
"""

from __future__ import annotations

import re
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722])
THRESHOLD = 8.0
#: (top, bottom, left, right) fractions of the cropped frame. The shapes stand in a row: sphere, cylinder, panel.
REGIONS = {
    "shapes_front": {"sphere": (0.0, 1.0, 0.0, 0.31), "cylinder": (0.0, 1.0, 0.37, 0.62),
                     "bowl": (0.0, 0.52, 0.68, 1.0), "groove": (0.52, 1.0, 0.68, 1.0)},
    "gollum_face": {"nose": (0.40, 0.62, 0.30, 0.68), "mouth_l": (0.80, 1.0, 0.04, 0.36),
                    "mouth_r": (0.80, 1.0, 0.64, 0.96), "cheek_shadow": (0.45, 0.80, 0.0, 0.30),
                    "socket_l": (0.0, 0.38, 0.0, 0.45), "socket_r": (0.0, 0.38, 0.55, 1.0)},
    "gollum_framed": {"all": (0.0, 1.0, 0.0, 1.0)},
}


def load_png(path: Path) -> np.ndarray:
    """The RGB of a PNG written by `mirai.iris_import.encode_png` (8-bit RGBA, filters None / Up)."""
    data = path.read_bytes()
    i, idat, w, h = 8, b"", 0, 0
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        if kind == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif kind == b"IDAT":
            idat += body
        i += 12 + n
    raw = zlib.decompress(idat)
    stride = w * 4 + 1
    out = np.zeros((h, w * 4), np.int32)
    prev = np.zeros(w * 4, np.int32)
    for y in range(h):
        f = raw[y * stride]
        row = np.frombuffer(raw[y * stride + 1:(y + 1) * stride], np.uint8).astype(np.int32)
        if f == 2:
            row = (row + prev) & 255
        elif f != 0:
            raise ValueError(f"PNG filter {f}")
        out[y], prev = row, row
    return out.reshape(h, w, 4)[..., :3].astype(np.float64)


def region_stats(img, ref, a, box) -> dict:
    h, w = ref.shape[:2]
    t, b, l, r = (int(round(box[0] * h)), int(round(box[1] * h)), int(round(box[2] * w)), int(round(box[3] * w)))
    lum = lambda x: x[t:b, l:r] @ LUMA  # noqa: E731
    ref_l = lum(ref)
    mask = ref_l > 6.0  # the object (the background is ~5)
    d = (lum(img) - ref_l)[mask]
    da = (lum(a) - ref_l)[mask]
    if d.size == 0:
        return {}
    return {"mae": float(np.mean(np.abs(d))), "brighter": float(np.mean(d > THRESHOLD)),
            "darker": float(np.mean(d < -THRESHOLD)), "p99+": float(np.percentile(np.maximum(d, 0), 99)),
            "new+": float(np.mean((d > THRESHOLD) & (da <= THRESHOLD)))}


def boxes_overlay(img, regions) -> np.ndarray:
    out = img.copy()
    h, w = img.shape[:2]
    for t, b, l, r in regions.values():
        t, b, l, r = int(t * h), int(b * h) - 1, int(l * w), int(r * w) - 1
        for y in (t, b):
            out[y, l:r + 1] = (255, 60, 60)
        for x in (l, r):
            out[t:b + 1, x] = (255, 60, 60)
    return out


def main(argv=None) -> int:
    out = Path((argv or sys.argv[1:])[0])
    frames = out / "frames"
    sets: dict = {}
    for p in sorted(frames.glob("*.png")):
        m = re.match(r"(?P<scene>[a-z]+)_(?P<view>[a-z]+)_(?P<mat>[A-Za-z]+)_s(?P<size>\d{3})_(?P<var>.+)\.png", p.name)
        if m:
            sets.setdefault((m["scene"], m["view"], m["mat"], m["size"]), {})[m["var"]] = p
    lines = []
    for (scene, view, mat, size), files in sets.items():
        if "REF" not in files or "A" not in files:
            continue
        ref, a = load_png(files["REF"]), load_png(files["A"])
        regions = REGIONS.get(f"{scene}_{view}", {"all": (0.0, 1.0, 0.0, 1.0)})
        lines.append(f"{scene}/{view}/{mat}/size {int(size) / 100:g}")
        for var, path in files.items():
            if var in ("REF",) or "beauty" in var:
                continue
            img = load_png(path)
            cells = []
            for name, box in regions.items():
                s = region_stats(img, ref, a, box)
                cells.append(f"{name} {s['mae']:4.1f} +{100 * s['brighter']:4.1f}% -{100 * s['darker']:4.1f}% "
                             f"p99+ {s['p99+']:4.1f} new+ {100 * s['new+']:4.1f}%")
            lines.append(f"  {var:<11} " + " | ".join(cells))
    text = "\n".join(lines)
    print(text)
    (out / "regions.txt").write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def crops(out: Path, scene_view: str = "gollum_face", regions=("nose", "mouth_l"), sizes=("050", "100"),
          variants=("A", "B", "B-split", "REF"), scale: int = 2) -> list[Path]:
    """Zoomed crops (`scale` x) of `regions`: per material one sheet, rows = region x size, columns = `variants`, then
    the signed difference to REF (red brighter, blue darker, x4). Written as
    `crops_<scene_view>_<material>_<region>.png` (rows = sizes)."""
    from run_compare import diff_map, sheet, write_png

    frames = out / "frames"
    written = []
    boxes = REGIONS[scene_view]
    for material in ("Neutral", "CreatureSkin"):
        for region in regions:
            rows = []
            for size in sizes:
                imgs = {v: load_png(frames / f"{scene_view}_{material}_s{size}_{v}.png") for v in variants}
                h, w = imgs["REF"].shape[:2]
                t, b, l, r = boxes[region]
                box = (int(t * h), int(b * h), int(l * w), int(r * w))
                cut = {v: im[box[0]:box[1], box[2]:box[3]].astype(np.uint8) for v, im in imgs.items()}
                mask = (cut["REF"].astype(np.float64) @ LUMA) > 6.0
                row = [cut[v] for v in variants] + [diff_map(cut[v], cut["REF"], mask) for v in variants if v != "REF"]
                rows.append([np.repeat(np.repeat(c, scale, 0), scale, 1) for c in row])
            path = out / f"crops_{scene_view}_{material}_{region}.png"
            write_png(path, sheet(rows))
            written.append(path)
    return written
