"""Paint library probes (AD-037 §14 Phase 4c; proposal 2026-11-25 §9 "4c" gates) for the reference PC.

Usage (from the repo root; opens a hidden pyglet window for P-M's textures):
    python experiments/drag_cost/probe_paint_library.py
    python experiments/drag_cost/probe_paint_library.py --no-gl     # P-M without GL textures

Everything is written into a temporary folder (a throw-away user folder); nothing in `~/.mirai_bastel` is touched.

- **P-L** a **1024² import**: `library.open_import` (read the PNG, the suggestion) + `ImportDraft.preview` (the
  normalised grey) + `PaintLibrary.import_alpha` (hash, the PNG and its thumbnail file written), for a smooth image and
  for noise (the worst case for the PNG codec); a 4096² image as information (clamped to 1024). Gate: <= 0.5 s.
- **P-M** the picker's **first open with 50 thumbnails**: a new session's library (44 imported 1024² noise alphas + the
  six built in), each thumbnail's pixels (`gui.brush_picker_model.thumbnail_pixels`: the small thumbnail files, no full
  decode) and its GL texture; then the same 50 again (all cached: the per-frame cost afterwards). Gate: <= 150 ms, no
  per-frame cost afterwards. In the room the textures are also spread over frames (`THUMB_BUDGET_S`).
- **P-N** the **alpha cache**: 60 imported 1024² alphas read for painting one after the other (pixels + mips, LRU);
  the bytes held. Gate: <= 64 MiB.

Plain ASCII output; prints the commit and working-tree state (`_paths.source_state`).
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import ensure_paths, source_state  # noqa: E402

ensure_paths()


def _png(path: Path, grey, alpha=None) -> Path:
    import numpy as np

    from mirai.iris_import import encode_png

    rgba = np.empty(grey.shape + (4,), np.uint8)
    rgba[..., :3] = grey[..., None]
    rgba[..., 3] = 255 if alpha is None else alpha
    path.write_bytes(encode_png(rgba))
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-gl", action="store_true", help="P-M without GL textures")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)

    import numpy as np

    from gui import brush_picker_model as bm
    from mirai.paint import library as lib
    from mirai.paint.brush import BrushSettings

    print(f"Paint library probe (AD-037 Phase 4c) - {source_state()}")
    print(f"python {sys.version.split()[0]}, numpy {np.__version__}")
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:1024, 0:1024]
    smooth = (np.clip(1.0 - np.hypot(x - 511.5, y - 511.5) / 512.0, 0, 1) * 255).astype(np.uint8)
    noise = (rng.random((1024, 1024)) * 255).astype(np.uint8)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        print("\nP-L 1024^2 import (open + suggestion, preview, write PNG + thumbnail), ms       gate <= 500 ms")
        for case, (label, grey, alpha) in enumerate((("smooth, RGB", smooth, None), ("noise, RGB", noise, None),
                                                     ("shape on transparency", np.zeros_like(smooth), noise))):
            times, parts = [], []
            for run in range(args.runs):
                library = lib.PaintLibrary(tmp / f"user_l_{case}_{run}")
                source = _png(tmp / f"src_{run}.png", grey, alpha)
                t0 = time.perf_counter()
                draft, _ = lib.open_import(source)
                t1 = time.perf_counter()
                pixels = draft.preview()
                t2 = time.perf_counter()
                library.import_alpha(pixels, "probe")
                t3 = time.perf_counter()
                times.append((t3 - t0) * 1e3)
                parts.append(((t1 - t0) * 1e3, (t2 - t1) * 1e3, (t3 - t2) * 1e3))
            worst = max(times)
            mode = lib.MODE_LABELS[draft.mode]
            print(f"  {label:24s} p50 {statistics.median(times):6.1f}  max {worst:6.1f}  (open {parts[-1][0]:.0f},"
                  f" preview {parts[-1][1]:.0f}, write {parts[-1][2]:.0f}; suggested {mode})"
                  f"  {'PASS' if worst <= 500 else 'FAIL'}")
        big = np.tile(smooth, (4, 4))
        source = _png(tmp / "big.png", big)
        t0 = time.perf_counter()
        draft, _ = lib.open_import(source)
        lib.PaintLibrary(tmp / "user_big").import_alpha(draft.preview(), "big")
        print(f"  4096^2 (information, clamped to {draft.preview().shape[1]} px): {(time.perf_counter() - t0) * 1e3:.0f} ms")

        print("\nP-M picker first open, 50 thumbnails (44 imported 1024^2 + 6 built in), ms      gate <= 150 ms")
        user = tmp / "user_m"
        setup = lib.PaintLibrary(user)
        for k in range(44):
            setup.import_alpha((rng.random((1024, 1024)) * 255).astype(np.uint8), f"A{k}")

        class App:
            pass

        app = App()
        app.paint_library = lib.PaintLibrary(user)  # a new session: nothing in memory
        app.paint_brush = BrushSettings()
        app.paint_preset = None
        make_texture = None
        window = None
        if not args.no_gl:
            try:
                import pyglet
                from pyglet import image

                window = pyglet.window.Window(64, 64, visible=False)

                def make_texture(rgba):
                    h, w = rgba.shape[:2]
                    return image.ImageData(w, h, "RGBA", rgba[::-1].tobytes(), pitch=w * 4).get_texture()
            except Exception as exc:  # no display
                print(f"  (no GL: {exc.__class__.__name__}; pixels only)")
        t0 = time.perf_counter()
        items = bm.alpha_items(app)
        t1 = time.perf_counter()
        textures, pixel_ms, texture_ms = {}, 0.0, 0.0
        for item in items:
            a = time.perf_counter()
            pixels = bm.thumbnail_pixels(app, item)
            b = time.perf_counter()
            if make_texture is not None:
                textures[bm.thumbnail_key(app, item)] = make_texture(pixels)
            c = time.perf_counter()
            pixel_ms += (b - a) * 1e3
            texture_ms += (c - b) * 1e3
        total = (time.perf_counter() - t0) * 1e3
        print(f"  {len(items)} items: scan {(t1 - t0) * 1e3:.1f}, thumbnails {pixel_ms:.1f}, GL textures {texture_ms:.1f},"
              f" total {total:.1f}  {'PASS' if total <= 150 else 'FAIL'}")
        t0 = time.perf_counter()
        again = sum(1 for item in bm.alpha_items(app) if bm.thumbnail_key(app, item) in textures)
        print(f"  afterwards (all {again} cached, the frame's lookups only) {(time.perf_counter() - t0) * 1e3:.2f} ms;"
              f" alpha cache {app.paint_library.cached_bytes / 2**20:.1f} MiB (thumbnails do not fill it)")
        for texture in textures.values():
            texture.delete()
        if window is not None:
            window.close()

        print("\nP-N alpha cache: 60 imported 1024^2 alphas read for painting, one after the other      gate <= 64 MiB")
        user = tmp / "user_n"
        setup = lib.PaintLibrary(user)
        ids = [setup.import_alpha((rng.random((1024, 1024)) * 255).astype(np.uint8), f"N{k}")[0].id for k in range(60)]
        library = lib.PaintLibrary(user)
        peak, read = 0, []
        for alpha_id in ids:
            t = time.perf_counter()
            library.alpha(alpha_id)
            read.append((time.perf_counter() - t) * 1e3)
            peak = max(peak, library.cached_bytes)
        print(f"  peak {peak / 2**20:.1f} MiB, now {library.cached_bytes / 2**20:.1f} MiB"
              f" ({sum(1 for _ in library._cache)} alphas held); first read of a 1024^2 alpha p50"
              f" {statistics.median(read):.0f} ms  {'PASS' if peak <= 64 * 2**20 else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
