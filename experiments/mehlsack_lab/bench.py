"""Mehlsack Lab bench: hover, drag step and Nachführen cost on the 32 × 32 box (handoff §6).

Usage (from the repo root; needs pyglet and a GL context — headless: `xvfb-run -a`):
    python experiments/mehlsack_lab/bench.py --host "Manu-PC"
    python experiments/mehlsack_lab/bench.py --host "cloud" --runs 10

Every number says where it was measured (`--host`, GL_VERSION / GL_RENDERER). The 8 ms bar
is AD-020 S2c's; the reference PC decides, container numbers only show orders of magnitude.

Rows (median / max over `--runs`, ms), per radius step:
- `hover pick`: `pick_nearest_edge` with `PickCache` + occlusion, cache warm (a plain motion event)
- `hover pick (cold)`: the same right after a position change (cache refresh included)
- `hover change`: target (Loop/Ring) + signed influence of a newly hovered edge (no cache)
- `drag step`: one `drag_step` (op update) + `mark_vertices_dirty` (the event handler)
- `drag sync`: the next frame's `RenderMesh.sync()` + overlay refresh (wire, bands) + draw
- `nachführen`: one curve edit re-evaluating the last gesture (distances cached)
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from mehlsack_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

BOX = dict(height=2.0, width=1.5, h=32, n=32)
RADIUS_PERCENTS = (15, 50, 200)
DEFAULT_RUNS = 20


def _stats(samples: list[float]) -> tuple[float, float]:
    return statistics.median(samples), max(samples)


def run_bench(host: str, runs: int = DEFAULT_RUNS, width: int = 1280, height: int = 800,
              box: dict = BOX, visible: bool = False) -> str:
    from pyglet import gl
    from mirai.soft_selection.settings import RADIUS_STEPS_PERCENT
    from mirai.viewport.picking import pick_nearest_edge

    from mehlsack_lab.box import BoxParams
    from mehlsack_lab.lab_window import PICK_RADIUS_PX, MehlsackLabWindow
    from mehlsack_lab.signed_curve import PRESET_HAT, SignedCurve
    from mehlsack_lab.targets import MODE_LOOP

    window = MehlsackLabWindow(width, height, visible=visible, box=BoxParams(**box))
    window.switch_to()
    fb_w, fb_h = window.get_framebuffer_size()
    gl.glViewport(0, 0, fb_w, fb_h)
    state = window.state
    window.handle(state.key("RETURN"))
    session = state.session
    mesh = session.mesh
    cam = window.scene.camera

    # a cursor position over a mid-height horizontal edge, found by projection
    edge = None
    for eid in session.finder.index.edges:
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
        if abs(a[1]) < 1e-9 and abs(b[1]) < 1e-9 and abs(a[2] - b[2]) < 1e-9 and a[2] > 0:
            edge = eid
            break
    a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(edge))
    mid = tuple((p + q) / 2 for p, q in zip(a, b))
    sx, sy = cam.project_to_screen(mid, width, height)

    lines = [
        f"Mehlsack Lab bench · host: {host} · window {'visible' if visible else 'hidden'} {width}x{height}",
        f"GL_VERSION: {state.gl_version} · GL_RENDERER: {state.gl_renderer}",
        f"Box h={box['h']} n={box['n']}: V {len(mesh.all_vertex_ids())} / E {len(session.finder.index.edges)} / "
        f"F {len(mesh.all_face_ids())} · runs {runs} · median / max in ms",
        "",
        "| Radius | hover pick | hover pick (cold) | hover change | Einfluss-Vertices | drag step | drag sync | nachführen |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for percent in RADIUS_PERCENTS:
        state.radius_step = RADIUS_STEPS_PERCENT.index(percent)
        state.curve = SignedCurve.from_preset("smooth")
        warm, cold, change, step, sync, retune = [], [], [], [], [], []
        influenced = 0
        for _ in range(runs):
            window._pick_cache.invalidate()
            t0 = time.perf_counter()
            found = pick_nearest_edge(cam, mesh, sx, sy, width, height, PICK_RADIUS_PX,
                                      cache=window._pick_cache, occlusion=True)
            cold.append((time.perf_counter() - t0) * 1e3)
            t0 = time.perf_counter()
            pick_nearest_edge(cam, mesh, sx, sy, width, height, PICK_RADIUS_PX,
                              cache=window._pick_cache, occlusion=True)
            warm.append((time.perf_counter() - t0) * 1e3)
            session.finder.clear()
            session.cache.clear()
            t0 = time.perf_counter()
            target = session.target(found, MODE_LOOP)
            weights = state.preview_weights(target)
            change.append((time.perf_counter() - t0) * 1e3)
            influenced = len(weights)

            state.begin_drag(target)
            for i in range(3):
                t0 = time.perf_counter()
                state.drag_step((0.0, 0.004, 0.0))
                window.scene.positions_changed(session.drag.weights)
                step.append((time.perf_counter() - t0) * 1e3)
                t0 = time.perf_counter()
                window.scene.draw()
                gl.glFinish()
                sync.append((time.perf_counter() - t0) * 1e3)
            state.end_drag()
            t0 = time.perf_counter()
            out = state.set_curve(SignedCurve.from_preset(PRESET_HAT))
            window.scene.positions_changed(out.changed)
            retune.append((time.perf_counter() - t0) * 1e3)
            state.set_curve(SignedCurve.from_preset("smooth"))
            session.undo()
            window.scene.positions_changed(None)
            window.scene.draw()
        cells = [f"{m:.2f} / {x:.2f}" for m, x in map(_stats, (warm, cold, change))]
        cells2 = [f"{m:.2f} / {x:.2f}" for m, x in map(_stats, (step, sync, retune))]
        lines.append(f"| {percent} % | " + " | ".join(cells) + f" | {influenced} | " + " | ".join(cells2) + " |")
    window.close()
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mehlsack Lab bench (32 × 32 box)")
    parser.add_argument("--host", default="unlabeled", help="where this was measured")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--visible", action="store_true", help="visible window (reference PC)")
    args = parser.parse_args(argv)
    print(run_bench(args.host, runs=args.runs, visible=args.visible))
    return 0


if __name__ == "__main__":
    sys.exit(main())
