"""Lookdev step 1 (2026-11-13): the Worklight's shading cost at close-up coverage - `drag_cost/probe_shading_gpu.py`
unchanged (same fixture, the same four face-data variants, the same GL_TIME_ELAPSED loop and image check), only with
the camera dollied toward the framed centre before the passes are drawn.

Usage (from the repo root; opens hidden pyglet windows, imports src/ through the drag_cost probe):
    python experiments/lookdev_gpu_probe/probe_worklight_coverage.py
    python experiments/lookdev_gpu_probe/probe_worklight_coverage.py --size 1920 1080

Why: `probe_shading_gpu.py` frames the whole 87.5k fixture (`Application.frame_scene`), so the mesh covers about 14 %
of a 1024x768 frame and about 11 % of 1920x1080 (container, 2026-11-13). A Lookdev close-up fills the frame, and the
fragment cost does not scale linearly with coverage (at the framed view several triangles share a pixel). `--dolly`
multiplies the camera distance (`OrbitCamera.dolly`) per run; 1.0 is exactly the baseline view. The printed
`coverage` is the share of the frame the `o2` image covers.

The production shader, `GLRenderStore` and the drag_cost probe are not modified: `measure()` imports `build_app` from
`drag_cost.probe_morph_gl` when it runs, and this wrapper swaps that attribute for the duration of one call.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost import probe_shading_gpu as shading  # noqa: E402  (also puts src/ on sys.path)
from lookdev_gpu_probe import cube_math as cm  # noqa: E402

DEFAULT_DOLLY = (1.0, 0.5, 0.3)


def build_parser() -> argparse.ArgumentParser:
    """The drag_cost probe's options with its defaults (pinned by a test), plus `--dolly`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asset", default=str(shading.DENSE.relative_to(shading.REPO_ROOT)),
                        help="OBJ path relative to the repo root")
    parser.add_argument("--size", nargs=2, type=int, default=[1024, 768], metavar=("W", "H"), help="window size")
    parser.add_argument("--draws", type=int, default=shading.DEFAULT_DRAWS, help="measured rounds")
    parser.add_argument("--flat", action="store_true", help="Flat instead of Smooth")
    parser.add_argument("--dolly", nargs="+", type=float, default=list(DEFAULT_DOLLY), metavar="F",
                        help="camera distance factors, one run each (1.0 = the probe_shading_gpu view)")
    return parser


def dollied(build_app, factor: float):
    def build(path):
        window, app = build_app(path)
        app.camera.dolly(factor)
        return window, app

    return build


def measure_at(path: Path, size: tuple[int, int], draws: int, flat: bool, factor: float) -> list[str]:
    import drag_cost.probe_morph_gl as morph_gl

    original = morph_gl.build_app
    morph_gl.build_app = dollied(original, factor)
    try:
        return shading.measure(path, size, draws, flat)
    finally:
        morph_gl.build_app = original


def coverage_line(header: str, factor: float) -> str:
    parsed = cm.coverage(header)
    if parsed is None:
        return f"  dolly {factor:g}: coverage unknown"
    width, height, covered = parsed
    return f"  dolly {factor:g}: coverage {100.0 * covered / (width * height):.1f} % of {width}x{height}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = shading.resolve_asset(args.asset)
    import pyglet

    from drag_cost.probe_drag_gl import machine_info

    probe = pyglet.window.Window(width=64, height=64, visible=False)
    info = machine_info(pyglet.gl.gl_info.get_version_string(), pyglet.gl.gl_info.get_renderer())
    probe.close()
    print("Worklight coverage probe (2026-11-13): drag_cost/probe_shading_gpu.measure with the camera dollied in")
    for line in info:
        print(line)
    print(f"Source: {cm.source_state(shading.REPO_ROOT)}")
    status = 0
    for factor in args.dolly:
        print()
        try:
            lines = measure_at(path, tuple(args.size), args.draws, args.flat, factor)
        except ValueError as exc:
            if "min()" not in str(exc):
                raise
            print(f"  dolly {factor:g}: probe_shading_gpu.measure raised {exc!r} in its NOTE check - every GPU time "
                  "was <= 0.5 ms (fast GPU or software renderer); the measured numbers are lost (README, findings)")
            status = 1
            continue
        print(lines[0])
        print(coverage_line(lines[0], factor))
        for line in lines[1:]:
            print(line)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
