"""Measurement script for the draw-binding spike (§8 of the handoff).

Runs the four scenarios against the real head mesh
(`examples/meshes/head_basemesh.obj`, 326V/324Q) with `SpikeGLStore` (real
GL) and reports avg/p95/max event-to-draw CPU ms plus the relevant
counters. Numbers from the sandbox this was developed in are NOT
representative of anything (see handoff §8, "Label sandbox numbers as
not representative") — this script exists so Manu can run it on his own
PC with `python run_bench.py` for a number that means something.

Usage:
    python run_bench.py            # visible window, one frame per scenario step
    xvfb-run -a python run_bench.py --headless
"""

from __future__ import annotations

import argparse
import statistics
import time

import _bootstrap  # noqa: F401

import pyglet

from core import Selection
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import build_core_scene_from_obj
from mirai.viewport.camera import OrbitCamera
from viewport.viewport import Viewport

from drawing import draw_frame
from spike_gl_store import SpikeGLStore

HEAD_OBJ = _bootstrap._REPO_ROOT / "examples" / "meshes" / "head_basemesh.obj"


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _report(name: str, times_ms: list[float], counters: dict, extra: dict | None = None) -> None:
    print(f"\n--- {name} ---")
    print(f"  n = {len(times_ms)}")
    print(f"  avg = {statistics.mean(times_ms):.4f} ms")
    print(f"  p95 = {_percentile(times_ms, 0.95):.4f} ms")
    print(f"  max = {max(times_ms):.4f} ms")
    for key in ("geometry_uploads", "partial_updates", "structural_rebuilds",
                "gpu_resource_creations", "bytes_uploaded"):
        if key in counters:
            print(f"  {key} = {counters[key]}")
    if extra:
        for k, v in extra.items():
            print(f"  {k} = {v}")


def run(headless: bool) -> None:
    win = pyglet.window.Window(960, 720, visible=not headless)

    scene = build_core_scene_from_obj(HEAD_OBJ)
    mesh = scene.mesh
    selection = Selection()
    vp = Viewport(mesh, selection, store_type=SpikeGLStore)
    camera = OrbitCamera()
    center, radius = mesh_center_and_radius(mesh)
    camera.frame_on_bounds(center, radius)
    vp.bind_camera(camera)
    vp.on_camera_changed(aspect=win.width / win.height)
    vp.sync()
    program = SpikeGLStore.program()

    def frame() -> None:
        win.switch_to()
        win.clear()
        draw_frame(program, vp.render_mesh.store)
        from pyglet import gl
        gl.glFinish()

    all_vertex_ids = list(mesh.all_vertex_ids())

    print(f"Mesh: {HEAD_OBJ.name} — {len(all_vertex_ids)}V")
    print("Sandbox numbers below are NOT representative (see handoff §8).")

    # -- Scenario 1: orbit, 100 frames -----------------------------------------
    stats_before = dict(vp.benchmark_counters)
    times = []
    for i in range(100):
        t0 = time.perf_counter()
        camera.orbit(0.02, 0.01)
        vp.on_camera_changed()
        vp.sync()
        frame()
        times.append((time.perf_counter() - t0) * 1000.0)
    uploads_delta = vp.benchmark_counters.get("geometry_uploads", 0) - stats_before.get("geometry_uploads", 0)
    _report("Orbit, 100 frames", times, vp.benchmark_counters,
             {"geometry_uploads (delta)": uploads_delta})

    # -- Scenario 2: single-vertex move, 100x -----------------------------------
    v0 = all_vertex_ids[0]
    times = []
    partial_before = vp.benchmark_counters.get("partial_updates", 0)
    bytes_before = 0  # SpikeGLStore doesn't track bytes separately from RenderMesh's stats
    for i in range(100):
        px, py, pz = mesh.vertex_position(v0)
        t0 = time.perf_counter()
        mesh.set_vertex_position(v0, (px, py, pz + 0.001))
        vp.on_vertices_moved({v0})
        vp.sync()
        frame()
        times.append((time.perf_counter() - t0) * 1000.0)
    partial_delta = vp.benchmark_counters.get("partial_updates", 0) - partial_before
    _report("Single-vertex move, 100x", times, vp.benchmark_counters,
            {"partial_updates (delta)": partial_delta})

    # -- Scenario 3: multi-vertex move (50 verts), 50x --------------------------
    move_set = set(all_vertex_ids[:50])
    times = []
    for i in range(50):
        t0 = time.perf_counter()
        for vid in move_set:
            px, py, pz = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (px, py, pz + 0.0005))
        vp.on_vertices_moved(move_set)
        vp.sync()
        frame()
        times.append((time.perf_counter() - t0) * 1000.0)
    _report("Multi-vertex move (50 verts), 50x", times, vp.benchmark_counters,
            {"note": "RenderMesh issues one store.update() call per moved vertex "
                     "(Spec §12 open question) — not batched into a single upload"})

    # -- Scenario 4: edge split, 10x ---------------------------------------------
    times = []
    rebuilds_before = vp.benchmark_counters.get("structural_rebuilds", 0)
    for i in range(10):
        edge_id = next(iter(mesh.all_edge_ids()))
        t0 = time.perf_counter()
        mesh.split_edge(edge_id)
        vp.on_topology_changed()
        vp.sync()
        frame()
        times.append((time.perf_counter() - t0) * 1000.0)
    rebuilds_delta = vp.benchmark_counters.get("structural_rebuilds", 0) - rebuilds_before
    _report("Edge split, 10x", times, vp.benchmark_counters,
            {"structural_rebuilds (delta)": rebuilds_delta})

    win.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true",
                         help="create an invisible window (still needs a GL context, "
                              "e.g. via xvfb-run)")
    args = parser.parse_args()
    run(headless=args.headless)


if __name__ == "__main__":
    main()
