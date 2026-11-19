"""LookDev room probe (AD-038 LD-1, 2026-11-19): what the built room costs in the real app frame.

Usage (from the repo root; opens a hidden pyglet window):
    python experiments/drag_cost/probe_lookdev_room.py                 # 1024x768, 30 rounds
    python experiments/drag_cost/probe_lookdev_room.py --draws 5       # container: a function check
    python experiments/drag_cost/probe_lookdev_room.py --size 1920 1080

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_lookdev.py`). The scene is
`scenes/Gollum_Head_05.mirai.json` as saved (the painted head is the edit object, two eyes; teeth and the older head
hidden), framed at the ¾ angle (`probe_lookdev.set_view("framed")`), surfaces `cage` (SubD off) and `subd1`.

Rows, `Viewport.render()` exactly as `main.py` calls it (overlays included), timed with GL_TIME_ELAPSED after 5
unmeasured rounds:
- `modelling`  the room closed: today's Worklight frame (the LD-D10 floor; compare with `probe_lookdev.py`'s
               `app render` and `probe_d3_acceptance.py` for E16);
- `lookdev`    the room open (`Application.open_lookdev`, Portrait, every object Neutral): background, the LookDev
               skin pass with the paint composite, the eyes' LOOKDEV variant in the "full" tier;
- `modelling after`  the room closed again: the Worklight frame must be what it was (LookDev leaves nothing behind).

Entering (first in the process, then once more):
- `open_lookdev` wall ms (display values, sync_views, the LookDraws);
- the shader preparation behind the status line (`Viewport.prepare_lookdev`): programs compiled and their ms - cold
  the first time, cached the second;
- the ticks until the first LookDev frame (`update_viewport`; the first one syncs the UV request on the head's drawn
  surface, `_triangle_uvs_flat`; the last one compiles);
- the first LookDev frame (GPU and wall ms).

Plain ASCII output; prints the commit and the working-tree state. Changes nothing in `src/`.
"""

from __future__ import annotations

import argparse
import ctypes
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import ensure_paths  # noqa: E402

ensure_paths()

WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 30
SURFACES = ("cage", "subd1")
FRAME_BUDGET_MS = 1000.0 / 30.0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, nargs=2, default=(1024, 768), metavar=("W", "H"))
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--surfaces", default=",".join(SURFACES))
    args = parser.parse_args(argv)
    args.surfaces = tuple(s for s in args.surfaces.split(",") if s)
    if args.draws < 1 or not set(args.surfaces) <= set(SURFACES):
        parser.error("--draws >= 1, --surfaces from cage,subd1")
    return args


def summary(values) -> tuple[float, float, float]:
    return statistics.median(values), min(values), max(values)


def frame(window, size, query, app) -> tuple[float, float]:
    """One cleared frame of `Viewport.render()` (as `main.on_draw` after its clear): (GPU ms, wall ms)."""
    from drag_cost.probe_lookdev import timed_frame

    return timed_frame(window, size, query, app.viewport.render)


def rounds(window, size, query, app, draws: int) -> tuple[list[float], list[float]]:
    gpu, wall = [], []
    for i in range(WARMUP_ROUNDS + draws):
        app.update_viewport(0.0)
        g, w = frame(window, size, query, app)
        if i >= WARMUP_ROUNDS:
            gpu.append(g)
            wall.append(w)
    return gpu, wall


def row(name: str, gpu, wall, floor: float | None = None) -> str:
    p50, lo, hi = summary(gpu)
    text = (f"  {name:<16} GPU p50 {p50:7.2f} ms (min {lo:6.2f}, max {hi:6.2f})  {100.0 * p50 / FRAME_BUDGET_MS:5.1f} % "
            f"of 33.3 ms   CPU p50 {statistics.median(wall):7.2f} ms")
    if floor is not None:
        text += f"   vs modelling {p50 - floor:+6.2f} ms"
    return text


def enter(window, size, query, app, label: str) -> list[str]:
    """Open the room and drive the ticks until its first LookDev frame; what each step costs."""
    viewport = app.viewport
    start = time.perf_counter()
    app.open_lookdev()
    open_ms = (time.perf_counter() - start) * 1e3
    needed = bool(app.lookdev.preparing)
    prepare_ms, compiled = 0.0, 0
    original = viewport.prepare_lookdev

    def timed():
        nonlocal prepare_ms, compiled
        t = time.perf_counter()
        compiled = original()
        prepare_ms = (time.perf_counter() - t) * 1e3
        return compiled

    viewport.prepare_lookdev = timed
    ticks = []
    while True:
        start = time.perf_counter()
        app.update_viewport(0.0)  # the first tick syncs the UV request (`Viewport.sync`, `_triangle_uvs_flat`)
        ticks.append((time.perf_counter() - start) * 1e3)
        if not app.lookdev.preparing:
            break
        frame(window, size, query, app)  # a frame that shows the status line (still the Worklight)
    del viewport.prepare_lookdev
    gpu, wall = frame(window, size, query, app)
    assert viewport.shading == "lookdev"
    tick_text = ", ".join(f"{t:.1f}" for t in ticks)
    return [f"  {label}: open_lookdev {open_ms:.1f} ms; ticks until the first LookDev frame [{tick_text}] ms (the "
            f"first holds the UV request); programs compiled {compiled} in {prepare_ms:.0f} ms "
            f"({'behind the status line' if needed else 'none needed'}); first LookDev frame GPU {gpu:.2f} ms, "
            f"wall {wall:.1f} ms"]


def main(argv=None) -> int:
    import pyglet
    from pyglet import gl

    from drag_cost._paths import source_state
    from drag_cost.probe_drag_gl import machine_info
    from drag_cost.probe_lookdev import SCENE, build_app, set_surface, set_view, triangles

    args = parse_args(argv)
    window, app = build_app(tuple(args.size))
    size = window.get_framebuffer_size()
    print(f"LookDev room probe (AD-038 LD-1, 2026-11-19), {size[0]}x{size[1]}, {args.draws} rounds after "
          f"{WARMUP_ROUNDS}")
    for line in machine_info(gl.gl_info.get_version_string(), gl.gl_info.get_renderer()):
        print(line)
    print(f"Source: {source_state()}")
    print(f"Scene: {SCENE.name}, edit object {app.scene.edit_object.name!r}, view framed (3/4)")
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    first = True
    for surface in args.surfaces:
        if not set_surface(app, surface):
            print(f"[{surface}] could not set the surface - skipped")
            continue
        set_view(app, "framed")
        drawn = app.viewport.surface_render_mesh or app.viewport.render_mesh
        print()
        print(f"[{surface}] the head draws {triangles(drawn)} triangles")
        gpu, wall = rounds(window, size, query, app, args.draws)
        floor = summary(gpu)[0]
        lines = [row("modelling", gpu, wall)]
        entry = enter(window, size, query, app, "entry (first in this process)" if first else "entry")
        first = False
        gpu, wall = rounds(window, size, query, app, args.draws)
        lines.append(row("lookdev", gpu, wall, floor))
        app.close_lookdev()
        gpu, wall = rounds(window, size, query, app, args.draws)
        lines.append(row("modelling after", gpu, wall, floor))
        for line in entry + lines:
            print(line)
    print()
    print("Entering once more (programs cached in this process):")
    print(enter(window, size, query, app, "entry again")[0])
    app.close_lookdev()
    print()
    print(f"glGetError at the end: 0x{gl.glGetError():04X}")
    window.close()
    del pyglet
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
