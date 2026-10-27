"""Morph-target cost probe with the real GL backend (AD-025 Phase 3, 2026-10-27).

Usage (from the repo root, Windows and Linux alike; opens a hidden pyglet window):
    python experiments/drag_cost/probe_morph_gl.py
    python experiments/drag_cost/probe_morph_gl.py --assets head_basemesh --steps 300
    python experiments/drag_cost/probe_morph_gl.py --assets examples/meshes/gollum_20k.obj

Headless container: prefix with `xvfb-run -a`.

What it measures, in the window's own chain (`Application` -> `Viewport` -> `GLRenderStore`, the
`GL_TYPES` of `src/main.py`), per asset and per target occupancy (15 % / 100 % of the points carry an
offset; the offsets are a smooth bump):

- `weight step`  one +/-1 % weight step as the hold-N drag makes it: `pointer_motion` (sets the weight)
                 + `update_viewport` (claims the H7 slot, the provider patches the mix, `Viewport.sync`
                 uploads it). The Phase 3 bar: <= 16.7 ms p95 on head and man_with_shoes on the
                 reference PC; gollum_20k "usable" (H5c).
- `(draw)`       `Viewport.render()` + `glFinish()` of that frame (a software rasteriser is not GPU time).
- `first show`   the step from 0 % to 1 % (builds the evaluated surface once).
- `tap N`        0 % -> the last weight (the evaluated surface is kept; its GL buffers are rebuilt).
- `view commit`  Tab into the editing view, a W drag of the front-most region (36 points), and the
                 release: the time of the release (the offset write through `TranslatingHistory`) and
                 of the frame after it.
- `apply`        Ctrl+A in `4` on the placed base with its target (positions + `map_vector_layers`).

Numbers from a container must be labelled as such (`docs/architecture/REFERENCE_HARDWARE.md` §4); only
the reference PC decides the 16.7 ms bar. Output is plain ASCII.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

from drag_cost.probe_drag_gl import HEIGHT, WIDTH, Stats, grow_region, machine_info  # noqa: E402

DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh", "examples/meshes/gollum_20k.obj")
DEFAULT_STEPS = 200
OCCUPANCIES = (15, 100)
THRESHOLD_P95_MS = 16.7


def resolve_mesh(name: str) -> Path:
    from loaders.assets import asset_names, asset_path

    if name in asset_names():
        return Path(asset_path(name))
    path = Path(name)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file():
        raise SystemExit(f"unknown asset or file: {name!r}; known: {', '.join(asset_names())}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morph-target cost of the real GL chain (AD-025 Phase 3)")
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help="registry names or .obj paths (default: head, body, gollum_20k)")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="weight steps per row")
    return parser


def _key(value, *mods):
    from mirai.interaction.input import Input

    return Input("key", value, frozenset(mods))


def build_app(path: Path):
    import pyglet

    import main as src_main
    from mirai.application import Application

    window = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    app = Application()
    app.init_scene("obj", obj_path=path, **src_main.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.update_viewport(0.0)
    return window, app


def fill_target(app, occupancy: int) -> int:
    """A smooth bump on `occupancy` % of the points (the ones nearest the front-most point)."""
    mesh = app.scene.mesh
    lid = mesh.point_layer_ids()[0]
    ids = mesh.all_vertex_ids()
    seed = max(ids, key=lambda v: (mesh.vertex_position(v)[2], int(v)))
    sp = mesh.vertex_position(seed)
    ordered = sorted(ids, key=lambda v: math.dist(mesh.vertex_position(v), sp))
    chosen = ordered[: max(1, len(ids) * occupancy // 100)]
    reach = math.dist(mesh.vertex_position(chosen[-1]), sp) or 1.0

    def write():
        for v in chosen:
            r = math.dist(mesh.vertex_position(v), sp) / reach
            mesh.set_layer_value(lid, v, (0.0, 0.02 * (1.0 - r * r) + 1e-6, 0.05 * (1.0 - r * r) + 1e-6))

    app.apply_mesh_change("probe offsets", lambda: write() or set())
    return len(chosen)


def frame(app):
    from pyglet import gl

    start = time.perf_counter()
    app.update_viewport(0.0)
    mid = time.perf_counter()
    app.viewport.render()
    gl.glFinish()
    return (mid - start) * 1000.0, (time.perf_counter() - mid) * 1000.0


def weight_rows(app, steps: int) -> tuple[Stats, Stats, float]:
    from mirai.morph_targets import DRAG_PIXELS_PER_PERCENT

    app.set_morph_weight(0)
    frame(app)
    n = _key("n")
    app.key_press(n)
    start = time.perf_counter()
    app.pointer_motion(400, 300, DRAG_PIXELS_PER_PERCENT, 0.0)
    _, draw = frame(app)
    first = (time.perf_counter() - start) * 1000.0 - draw
    samples, draws = [], []
    direction = 1.0
    for i in range(steps):
        if app.morph_weight >= 100:
            direction = -1.0
        elif app.morph_weight <= 1:
            direction = 1.0
        t0 = time.perf_counter()
        app.pointer_motion(400, 300, direction * DRAG_PIXELS_PER_PERCENT, 0.0)
        _, draw = frame(app)
        samples.append((time.perf_counter() - t0) * 1000.0 - draw)
        draws.append(draw)
    app.key_release(n)
    return Stats.of(samples), Stats.of(draws), first


def ab_row(app, reps: int = 4) -> Stats:
    """Tap N: 0 % -> the last weight (the surface is kept, its GL buffers are rebuilt)."""
    n = _key("n")
    samples = []
    app.set_morph_weight(60)
    frame(app)
    for _ in range(reps):
        for _ in range(2):
            t0 = time.perf_counter()
            app.key_press(n)
            app.key_release(n)
            _, draw = frame(app)
            if app.morph_weight:
                samples.append((time.perf_counter() - t0) * 1000.0 - draw)
    return Stats.of(samples)


def view_commit_row(app, reps: int = 5) -> tuple[Stats, Stats]:
    releases, frames = [], []
    for _ in range(reps):
        app.key_press(_key("tab"))
        frame(app)
        region = grow_region(app.scene.mesh, 36)
        app.selection.set(set(region))
        app.viewport.on_selection_changed()
        w = _key("w")
        app.key_press(w)
        for i in range(10):
            app.pointer_motion(400 + i, 300, 2.0, 1.0)
        frame(app)
        t0 = time.perf_counter()
        app.key_release(w)
        releases.append((time.perf_counter() - t0) * 1000.0)
        frames.append(frame(app)[0])
        app.key_press(_key("tab"))
        frame(app)
    return Stats.of(releases), Stats.of(frames)


def apply_row(app) -> float:
    from core import ObjectTransform
    from mirai import object_space

    obj = app.scene.edit_object
    obj.transform = ObjectTransform(
        translation=(0.3, 0.0, 0.0), rotation=object_space.axis_angle_rotation((0.0, 1.0, 0.0), 0.4), scale=1.5
    )
    app._placement_changed()
    app.key_press(_key("4"))
    app.selection.objects = {obj.id}
    t0 = time.perf_counter()
    ok = app.dispatch_command("ApplyTransform")
    elapsed = (time.perf_counter() - t0) * 1000.0
    if not ok:
        raise RuntimeError(app.status_message)
    app.key_press(_key("z", "ctrl"))
    app.key_press(_key("1"))
    return elapsed


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    paths = [resolve_mesh(a) for a in args.assets]
    lines = []
    for path in paths:
        window, app = build_app(path)
        if not lines:
            from pyglet.gl import gl_info

            lines += machine_info(gl_info.get_version_string(), gl_info.get_renderer())
            lines.append(f"Morph probe (AD-025 Phase 3), {args.steps} weight steps per row; bar {THRESHOLD_P95_MS} ms p95")
        count = len(app.scene.mesh.all_vertex_ids())
        app.key_press(_key("n", "ctrl"))
        for occupancy in OCCUPANCIES:
            stored = fill_target(app, occupancy)
            step, draw, first = weight_rows(app, args.steps)
            verdict = "ok" if step.p95 <= THRESHOLD_P95_MS else "OVER"
            lines.append(
                f"{path.stem:<26} {count:>6} V  offsets {occupancy:>3} % ({stored:>6})  weight step {step.text()}"
                f"  [{verdict}]  (draw p50 {draw.p50:.2f})  first show {first:.1f} ms"
            )
        lines.append(f"{path.stem:<26} tap N 0 % -> 60 %: {ab_row(app).text()}")
        release, after = view_commit_row(app)
        lines.append(f"{path.stem:<26} view commit (36 points): release {release.text()}  frame after {after.text()}")
        lines.append(f"{path.stem:<26} apply transform with one target: {apply_row(app):.1f} ms")
        window.close()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
