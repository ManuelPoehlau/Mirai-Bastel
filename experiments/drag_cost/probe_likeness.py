"""Likeness camera probe (AD-042 M1 §10.4, 2026-11-27): what the camera view, the gate and a photo cost in the app frame.

Usage (from the repo root; opens a hidden pyglet window):
    python experiments/drag_cost/probe_likeness.py                     # 1024x768, 30 rounds
    python experiments/drag_cost/probe_likeness.py --draws 5           # container: a function check
    python experiments/drag_cost/probe_likeness.py --photo C:/fotos/anna.jpg   # also time a real JPEG (pyglet / WIC)

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_lookdev.py`). The scene is
`scenes/Gollum_Head_05.mirai.json` as saved, framed at the ¾ angle (`probe_lookdev.set_view("framed")`).

Rows, `Viewport.render()` exactly as `main.py` calls it (overlays included), GL_TIME_ELAPSED after 5 unmeasured rounds:
- `free`                      the Worklight frame, no camera view (today's floor);
- `camera view`               looking through a camera „Neu aus Ansicht“: gate and passepartout, no photo;
- `photo 4096 behind`         a generated 4096 x 3072 photo behind the model, Worklight;
- `lookdev photo 4096 behind` the same in LookDev (Portrait);
- `free after`                left again, LookDev closed: must equal `free`;
- `photo load`                wall ms of read + cap + upload for a generated 6000 x 4000 PNG (`encode_png`), and for
                              `--photo PATH` (a JPEG: the pyglet decode).

Targets (`PROVISIONAL`, AD-042 §10.4): each camera-view row <= its free row + 0.5 ms GPU; `free after` = `free`;
`photo load` of a 24 MP JPEG <= 3 s. In the container this is a function check only; the reference PC decides.

Plain ASCII output; prints the commit and the working-tree state. Changes nothing in `src/`; the generated photos go to
a temporary folder (nothing is written to `scenes/` or the repository).
"""

from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
import tempfile
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import ensure_paths  # noqa: E402

ensure_paths()

WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 30
FRAME_BUDGET_MS = 1000.0 / 30.0
TARGET_MS = 0.5
PHOTO_SIZE = (4096, 3072)
LOAD_SIZE = (6000, 4000)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768), metavar=("W", "H"))
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--photo", type=Path, default=None, help="a photo of your own to time the decode (JPEG)")
    args = parser.parse_args(argv)
    if args.draws < 1:
        parser.error("--draws >= 1")
    if args.photo is not None and not args.photo.is_file():
        parser.error(f"--photo: no file {args.photo}")
    return args


def test_photo(size: tuple[int, int]):
    """A deterministic RGBA photo (a gradient with a grid) of `size` (w, h)."""
    import numpy as np

    w, h = size
    y, x = np.mgrid[0:h, 0:w]
    out = np.empty((h, w, 4), np.uint8)
    out[..., 0] = (x * 255 // max(w - 1, 1)).astype(np.uint8)
    out[..., 1] = (y * 255 // max(h - 1, 1)).astype(np.uint8)
    out[..., 2] = np.where(((x // 64) + (y // 64)) % 2 == 0, 200, 60).astype(np.uint8)
    out[..., 3] = 255
    return out


def rounds(window, size, query, app, draws: int) -> tuple[list[float], list[float]]:
    from drag_cost.probe_lookdev import timed_frame

    gpu, wall = [], []
    for i in range(WARMUP_ROUNDS + draws):
        app.update_viewport(0.0)
        g, w = timed_frame(window, size, query, app.viewport.render)
        if i >= WARMUP_ROUNDS:
            gpu.append(g)
            wall.append(w)
    return gpu, wall


def row(name: str, gpu, wall, floor: float | None = None) -> str:
    p50 = statistics.median(gpu)
    text = (f"  {name:<27} GPU p50 {p50:7.2f} ms (min {min(gpu):6.2f}, max {max(gpu):6.2f})  "
            f"{100.0 * p50 / FRAME_BUDGET_MS:5.1f} % of 33.3 ms   CPU p50 {statistics.median(wall):7.2f} ms")
    if floor is not None:
        delta = p50 - floor
        text += f"   vs free {delta:+6.2f} ms {'ok' if delta <= TARGET_MS else 'OVER'}"
    return text


def load_photo(window, size, query, app, path: Path) -> tuple[float, float, str]:
    """Wall ms of the photo's read + cap (the tick) and of the upload (the first frame that draws it)."""
    from drag_cost.probe_lookdev import timed_frame

    assert app.load_likeness_photo(0, path)
    start = time.perf_counter()
    while app.likeness.pending_photo is not None:
        app.update_viewport(0.0)
    read = (time.perf_counter() - start) * 1e3
    status = app.status_message
    uploads = app.viewport.backdrop_pass.uploads if app.viewport._backdrop_pass is not None else 0
    _gpu, upload = timed_frame(window, size, query, app.viewport.render)
    assert app.viewport.backdrop_pass.uploads == uploads + 1, "the photo was not uploaded"
    return read, upload, status


def main(argv=None) -> int:
    from pyglet import gl

    from drag_cost._paths import source_state
    from drag_cost.probe_drag_gl import machine_info
    from drag_cost.probe_lookdev import SCENE, build_app, set_view
    from mirai.iris_import import encode_png

    args = parse_args(argv)
    window, app = build_app(tuple(args.size))
    size = window.get_framebuffer_size()
    print(f"Likeness camera probe (AD-042 M1), {size[0]}x{size[1]}, {args.draws} rounds after {WARMUP_ROUNDS}")
    for line in machine_info(gl.gl_info.get_version_string(), gl.gl_info.get_renderer()):
        print(line)
    print(f"Source: {source_state()}")
    print(f"Scene: {SCENE.name}, edit object {app.scene.edit_object.name!r}, view framed (3/4)")
    set_view(app, "framed")
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    query = query.value

    gpu, wall = rounds(window, size, query, app, args.draws)
    floor = statistics.median(gpu)
    print(row("free", gpu, wall))

    assert app.new_likeness_camera() and app.look_through(0), app.status_message
    cam = app.likeness.cameras[0]
    print(f"  ({cam.name}: {cam.lens.focal_mm:.1f} mm KB from the view, overscan {app.likeness.overscan})")
    gpu, wall = rounds(window, size, query, app, args.draws)
    print(row("camera view", gpu, wall, floor))

    with tempfile.TemporaryDirectory(prefix="mirai_likeness_probe_") as folder:
        folder = Path(folder)
        photo = folder / "photo_4096.png"
        photo.write_bytes(encode_png(test_photo(PHOTO_SIZE), level=1))
        read, upload, _status = load_photo(window, size, query, app, photo)
        gpu, wall = rounds(window, size, query, app, args.draws)
        print(row("photo 4096 behind", gpu, wall, floor))

        from drag_cost.probe_lookdev import timed_frame

        app.open_lookdev()
        for _ in range(app.LOOKDEV_PREPARE_FRAMES + 2):
            app.update_viewport(0.0)
            timed_frame(window, size, query, app.viewport.render)
        assert app.viewport.shading == "lookdev" and app.camera_view_open
        gpu_ld, wall_ld = rounds(window, size, query, app, args.draws)
        app.set_likeness_view(photo_shown=False)
        gpu_ld0, wall_ld0 = rounds(window, size, query, app, args.draws)
        app.set_likeness_view(photo_shown=True)
        print(row("lookdev (gate, no photo)", gpu_ld0, wall_ld0))
        print(row("lookdev photo 4096 behind", gpu_ld, wall_ld)
              + f"   vs lookdev {statistics.median(gpu_ld) - statistics.median(gpu_ld0):+6.2f} ms")
        app.close_lookdev()
        app.leave_camera_view()
        gpu, wall = rounds(window, size, query, app, args.draws)
        print(row("free after", gpu, wall, floor))

        print("Photo load (wall ms: read + cap in the tick, then the frame that uploads it):")
        print(f"  4096 x 3072 PNG             read {read:8.1f} ms   upload frame {upload:7.1f} ms")
        assert app.look_through(0)
        big = folder / "photo_6000.png"
        big.write_bytes(encode_png(test_photo(LOAD_SIZE), level=1))
        read, upload, status = load_photo(window, size, query, app, big)
        print(f"  6000 x 4000 PNG             read {read:8.1f} ms   upload frame {upload:7.1f} ms   ({status})")
        if args.photo is not None:
            read, upload, status = load_photo(window, size, query, app, args.photo)
            total = read + upload
            print(f"  {args.photo.name:<27} read {read:8.1f} ms   upload frame {upload:7.1f} ms   ({status})"
                  f"   {'ok' if total <= 3000.0 else 'OVER'} (target <= 3 s)")
        app.leave_camera_view()
    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
