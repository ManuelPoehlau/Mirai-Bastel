"""UV-transfer probe (AD-037 §11.3 "Speed"): where the ZBrush return's paint transfer spends its time.

Usage (from the repo root; no window, CPU only):
    python experiments/drag_cost/probe_uv_transfer.py
    python experiments/drag_cost/probe_uv_transfer.py --size 1024

Why: the reference PC took 7.3 s, then 6.0 s ("map 2.6, layers 3.3") and 5.6 s ("map 2.2, layers 3.5") for two 2048²
layers on `Gollum_Head_05`'s painted object, the container 0.6-0.9 s - 6-11x, not the usual 3x. Two guesses (cache-sized
pieces, no compression on the way in) changed little, so this probe splits every part and times three variants of the
bilinear read side by side; one run names the part to work on.

The fixture: `scenes/Gollum_Head_05.mirai.json`, the object "Gollum_backup_noscale1 ZBrush" (2,492 faces) with its two
layers when their PNGs are in `Gollum_Head_05_textures/` (else: the flattened image as layer 1 and a band as layer 2).
The new UVs: two layouts - "transposed" (u, v) -> (0.1 + 0.8 v, 0.1 + 0.8 u), islands turned like a re-unwrap (the
worst case for memory locality), and "scaled" (0.05 + 0.9 u, 0.05 + 0.9 v), islands kept in place (the best case).

Rows (best of `--repeat`, seconds):
- map: the texel map of the new layout (split / raster / ownership, `TexelMap.build_seconds`) and the rest of the plan
  (the changed faces, the old corner UVs, the old UV points);
- per layer: the copy of unchanged texels, the read (variant A, the app's), the paint mask, the seam padding;
- read variants on layer 1: A = the app's bilinear (`uv_transfer._bilinear` in pieces of `CHUNK`), B = the same with the
  texels taken in the order of their source texel (memory order of the old image), C = nearest (one read per texel) for
  scale.

Plain ASCII output; prints the commit and working-tree state (`_paths.source_state`).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parents[1]
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths, source_state  # noqa: E402

ensure_paths()

import numpy as np  # noqa: E402

SCENE = REPO_ROOT / "scenes" / "Gollum_Head_05.mirai.json"
OBJECT_SUFFIX = "ZBrush"
FLAT = REPO_ROOT / "scenes" / "Gollum_Head_05_textures" / "Gollum_backup_noscale1_ZBrush_paint_flat_c4ca21727c.png"


def best(fn, repeat: int) -> tuple[float, object]:
    times, result = [], None
    for _ in range(repeat):
        started = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - started)
    return min(times), result


def layouts(mesh) -> dict:
    faces = [f for f in mesh.all_face_ids() if mesh.face_uvs(f) is not None]
    return {
        "transposed": {f: tuple((0.1 + 0.8 * v, 0.1 + 0.8 * u) for u, v in mesh.face_uvs(f)) for f in faces},
        "scaled": {f: tuple((0.05 + 0.9 * u, 0.05 + 0.9 * v) for u, v in mesh.face_uvs(f)) for f in faces},
    }


def read_sorted(rgba, uv, grown, opaque, chunk):
    """Variant B: the texels in the order of their source texel, read in pieces, written back in place."""
    from mirai.paint import uv_transfer

    height, width = rgba.shape[:2]
    x = np.clip(np.floor(uv[:, 0] * width - 0.5), 0, width - 1)
    y = np.clip(np.floor(uv[:, 1] * height - 0.5), 0, height - 1)
    key = np.where(np.isfinite(x) & np.isfinite(y), y * width + x, -1).astype(np.int64)
    order = np.argsort(key, kind="stable")
    out = np.empty((uv.shape[0], 4), np.uint8)
    for a in range(0, order.size, chunk):
        idx = order[a:a + chunk]
        out[idx] = uv_transfer._bilinear(rgba, uv[idx], grown, opaque)
    return out


def read_nearest(rgba, uv):
    height, width = rgba.shape[:2]
    x = np.clip(np.floor(uv[:, 0] * width), 0, width - 1).astype(np.int64)
    y = np.clip(np.floor(uv[:, 1] * height), 0, height - 1).astype(np.int64)
    return rgba.reshape(-1, 4)[y * width + x]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=2048)
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()

    from mirai.application import Application
    from mirai.paint import uv_transfer
    from mirai.paint.files import read_image
    from mirai.paint.store import occupied, tile_box, tiles_in
    from mirai.paint.surface import pad_width, seam_pad
    from mirai.paint.texel_map import TexelMap

    print(f"UV-transfer probe (AD-037 §11.3) - {source_state()}")
    print(f"numpy {np.__version__}, python {sys.version.split()[0]}, size {args.size}^2, best of {args.repeat}")
    app = Application()
    app.init_scene("file", scene_path=SCENE)
    obj = next(o for o in app.scene.objects.values() if o.name.endswith(OBJECT_SUFFIX))
    mesh = obj.mesh
    size = args.size
    names = [layer.name for layer in obj.paint.layers] if obj.paint is not None else ["Ebene 1", "Ebene 2"]
    pixels = {}
    if obj.paint is not None and obj.paint.width == size:
        for name in names:
            pixels[name] = app.paint.load(obj, name)
    if not pixels or app.paint.missing:
        flat = np.ascontiguousarray(read_image(str(FLAT))[::-1])
        if flat.shape[0] != size:
            step = flat.shape[0] // size or 1
            flat = np.ascontiguousarray(flat[::step, ::step][:size, :size])
        band = np.zeros_like(flat)
        band[size * 2 // 5:size // 2, size // 4:size * 3 // 4] = (120, 40, 40, 200)
        pixels = {names[0]: flat.copy(), names[1]: band}
        print("layers: synthetic (the layer PNGs are not in the repo) - flat image + a band")
    else:
        print("layers: the scene's own PNGs")
    for name, rgba in pixels.items():
        print(f"  {name}: painted share {float((rgba[..., 3] > 0).mean()):.3f}")
    print(f"object {obj.name!r}: {len(mesh.all_face_ids())} faces")

    for label, new in layouts(mesh).items():
        print(f"\n== layout {label} ({len(new)} faces changed)")
        changed = uv_transfer._Changed(mesh, new)
        t_map, texel_map = best(lambda: TexelMap(changed, size, size, positions=changed), args.repeat)
        split = ", ".join(f"{k} {v:.3f}" for k, v in texel_map.build_seconds.items())
        print(f"map: texel map {t_map:.3f} s ({split})")
        t_plan, plan = best(lambda: uv_transfer.plan(mesh, new, size, size), args.repeat)
        print(f"map: whole plan {t_plan:.3f} s -> rest of the plan {max(t_plan - t_map, 0.0):.3f} s;"
              f" {plan.move.size} texels moved, {plan.keep.size} kept")
        total_layers = 0.0
        for name, rgba in pixels.items():
            t_copy, _ = best(lambda: np.zeros_like(rgba).reshape(-1, 4).__setitem__(plan.keep, rgba.reshape(-1, 4)[plan.keep]),
                             args.repeat)
            t_mask, mask = best(lambda: (uv_transfer._grown(rgba), bool((rgba[..., 3] == 255).all())), args.repeat)
            grown, opaque = mask

            def read_a():
                out = np.empty((plan.move.size, 4), np.uint8)
                for a in range(0, plan.move.size, uv_transfer.CHUNK):
                    b = min(a + uv_transfer.CHUNK, plan.move.size)
                    out[a:b] = uv_transfer._bilinear(rgba, plan.source_uv[a:b], grown, opaque)
                return out

            t_read, _ = best(read_a, args.repeat) if rgba[..., 3].any() else (0.0, None)
            moved = uv_transfer.transfer(rgba, plan)
            t_occ, occ = best(lambda: occupied(moved), args.repeat)
            boxes = [tile_box(tile, size, size) for tile in tiles_in(occ)]
            t_pad, _ = best(lambda: seam_pad(plan.map, boxes, pad_width(size)), args.repeat)
            t_all, _ = best(lambda: uv_transfer.transfer(rgba, plan), args.repeat)
            total_layers += t_all
            print(f"layer {name!r}: transfer {t_all:.3f} s = copy {t_copy:.3f} + mask {t_mask:.3f} + read A {t_read:.3f}"
                  f" + occupied {t_occ:.3f} + seam pad {t_pad:.3f} ({len(boxes)} tiles) + rest")
        print(f"layers total {total_layers:.3f} s")
        rgba = pixels[names[0]]
        grown, opaque = uv_transfer._grown(rgba), bool((rgba[..., 3] == 255).all())
        t_a, _ = best(lambda: [uv_transfer._bilinear(rgba, plan.source_uv[a:a + uv_transfer.CHUNK], grown, opaque)
                               for a in range(0, plan.move.size, uv_transfer.CHUNK)], args.repeat)
        t_b, _ = best(lambda: read_sorted(rgba, plan.source_uv, grown, opaque, uv_transfer.CHUNK), args.repeat)
        t_c, _ = best(lambda: read_nearest(rgba, plan.source_uv), args.repeat)
        print(f"read variants on {names[0]!r}: A app {t_a:.3f} s, B source order {t_b:.3f} s, C nearest {t_c:.3f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
