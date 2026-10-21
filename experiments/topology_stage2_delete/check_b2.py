"""AD-022 §8 "evidence still needed before B1 vs B2", on the machine it runs on (meant for the reference PC):

1. **`gl_PrimitiveID` exactness:** per pixel, the face the B2 face pass names (`gl_PrimitiveID` -> face row ->
   FaceId, `gpu_pick.py`) equals the face the spike's B1 pass names (own buffers, a per-vertex ID attribute,
   no `gl_PrimitiveID`; `gpu_picking_spike/id_picker.py`), for two framed cameras - on the fresh mesh, after a
   V1 Delete of 20 faces (degenerate triangles in the index buffer, B1 rebuilt for the new mesh) and after its
   Undo. Same for the point pass (`gl_VertexID` -> vertex slot vs B1's point list).
2. **Attribute location** of `position` in the store's program and in both ID programs (`layout(location = …)`).
3. **Agreement with the CPU picker** on 300 cursors per camera (face and vertex mode, Shaded): same element,
   same at the pixel centre (AD-022 §4.2, "half-px"), GPU none / CPU element, other.
4. **Cost** of one pick after a camera change (ID render + read, wall clock; GPU time of the render by timer
   query), p50 / max over 20 orbit steps.

Run (repo root; headless: `xvfb-run -a`):  python experiments/topology_stage2_delete/check_b2.py
`probe_stage2.py` runs it at the end. Lines starting with `B2 RESULT` go into the probe's summary.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS = Path(__file__).resolve().parents[1]
if str(_EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS))

from topology_stage2_delete._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

W, H = 1024, 768
GOLLUM_20K = "examples/meshes/gollum_20k.obj"


def _same(a, b) -> bool:
    return type(a) is type(b) and a == b


def set_camera(app, yaw_deg: float, pitch_deg: float) -> None:
    from mirai.mesh_geometry import mesh_center_and_radius

    center, radius = mesh_center_and_radius(app.scene.mesh)
    cam = app.camera
    cam.yaw, cam.pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    cam.frame_on_bounds(center, radius)
    app._camera_changed()
    app.viewport.sync()


def b2_faces(picker, rm) -> list:
    from topology_stage2_delete import render_patch

    rows, table = rm._triangle_face_rows, render_patch.row_face(rm)
    return [table[rows[t]] if t >= 0 else None for t in picker.read(0, 0, 0, W - 1, H - 1)]


def b2_points(picker, rm) -> list:
    from topology_stage2_delete import render_patch

    table = render_patch.slot_vertex(rm)
    return [table[s] if s >= 0 else None for s in picker.read(1, 0, 0, W - 1, H - 1)]


def b1_ids(b1, target: int, ids: list) -> list:
    _x, _y, _w, _h, block = b1.read_id_block(target, 0, 0, W - 1, H - 1)
    return [ids[i] if i >= 0 else None for i in block]


def compare(label: str, app, picker) -> tuple[int, int]:
    """Per-pixel difference counts (faces, points) between B2 and a fresh B1 for the current mesh and camera."""
    from gpu_picking_spike.id_picker import FACES as B1_FACES
    from gpu_picking_spike.id_picker import VERTICES as B1_VERTICES
    from gpu_picking_spike.id_picker import GpuIdPicker

    rm = app.viewport.render_mesh
    mesh = app.scene.mesh
    picker.prepare(app, points=True)
    faces2, points2 = b2_faces(picker, rm), b2_points(picker, rm)
    b1 = GpuIdPicker(mesh, W, H)
    try:
        b1.render(app.camera, occlusion=True)
        faces1 = b1_ids(b1, B1_FACES, b1.face_ids)
        points1 = b1_ids(b1, B1_VERTICES, b1.vertex_ids)
    finally:
        b1.release()
    face_diff = sum(1 for a, b in zip(faces1, faces2) if a != b)
    point_diff = sum(1 for a, b in zip(points1, points2) if a != b)
    covered = sum(1 for a in faces1 if a is not None)
    dead = sum(1 for a in faces2 if a is not None and not mesh.is_valid_face(a))
    print(f"  {label:34s} face pixels covered {covered:7d}; B2 face == B1 face on {W * H - face_diff}/{W * H} px "
          f"(differ {face_diff}, dead IDs {dead}); B2 point == B1 point on {W * H - point_diff}/{W * H} px "
          f"(differ {point_diff})")
    return face_diff, point_diff


def agreement(app, picker, mode_key: str, cursors) -> dict:
    from mirai.interaction.input import Input
    from mirai.viewport.picking import pick_component
    from mirai.viewport.picking_cache import PickCache

    app.key_press(Input("key", mode_key))
    out = {"same": 0, "half-px": 0, "gpu none": 0, "cpu none": 0, "other": 0, "both none": 0}
    cache = PickCache()
    mesh, mode = app.scene.mesh, app.selection.mode
    for x, y in cursors:
        gpu = picker.pick(app, float(x), float(y))
        cpu = pick_component(app._edit_camera, mesh, mode, x, y, W, H, cache=cache, occlusion=True)
        if gpu is None and cpu is None:
            out["both none"] += 1
        elif _same(gpu, cpu):
            out["same"] += 1
        elif _same(gpu, pick_component(app._edit_camera, mesh, mode, x + 0.5, y + 0.5, W, H, cache=cache,
                                       occlusion=True)):
            out["half-px"] += 1
        elif gpu is None:
            out["gpu none"] += 1
        elif cpu is None:
            out["cpu none"] += 1
        else:
            out["other"] += 1
    return out


def main(argv: list[str]) -> int:
    import pyglet

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets")
    parser.add_argument("--cursors", type=int, default=300)
    args = parser.parse_args(argv)

    from topology_stage2_delete import gpu_pick, stage2

    stage2.install("all")
    import main as src_main
    from drag_cost import probe_drag_gl as drag
    from gpu_picking_spike.probe_gpu_picking import cursors as spike_cursors
    from mirai.application import Application
    from mirai.interaction.input import Input
    from pyglet import gl
    from viewport.gl_render_store import GLRenderStore

    asset = Path(args.assets) if args.assets else REPO_ROOT / GOLLUM_20K
    window = pyglet.window.Window(width=W, height=H, visible=False)
    app = Application()
    app.init_scene("obj", obj_path=asset, **src_main.GL_TYPES)
    app.set_viewport_size(W, H)
    app.frame_scene()
    app.viewport.sync()
    app.viewport.render()
    for line in drag.machine_info(gl.gl_info.get_version(), gl.gl_info.get_renderer()):
        print(line)
    mesh = app.scene.mesh
    print(f"[{asset.stem}] {len(mesh.all_vertex_ids())} V / {len(mesh.all_face_ids())} F, window {W}x{H}")

    picker = gpu_pick.GpuPicker()
    picker.prepare(app, points=True)
    face_prog, point_prog = picker._programs
    locations = (GLRenderStore.program().attributes["position"]["location"],
                 face_prog.attributes["position"]["location"], point_prog.attributes["position"]["location"])
    print(f"attribute location of 'position': store program {locations[0]} | face ID program {locations[1]} | "
          f"point ID program {locations[2]}")

    total_face = total_point = 0
    cameras = (("front", 30, 15), ("back", 210, -20))
    print("1. per-pixel B2 vs B1 (Shaded: points depth-tested against the faces)")
    for name, yaw, pitch in cameras:
        set_camera(app, yaw, pitch)
        f, p = compare(f"{name}, fresh mesh", app, picker)
        total_face, total_point = total_face + f, total_point + p
    # A V1 Delete of 20 faces around the front-most vertex, then its Undo.
    seed = drag.seed_with_ring(mesh)[0]
    from drag_cost import probe_navigation_gl as nav
    from core import FaceId

    patch = nav._face_patch(mesh, seed, 20)
    app.key_press(Input("key", "3"))
    app.selection.set({FaceId(f) for f in patch})
    app.key_press(Input("key", "delete"))
    for name, yaw, pitch in cameras:
        set_camera(app, yaw, pitch)
        f, p = compare(f"{name}, after Delete 20 faces", app, picker)
        total_face, total_point = total_face + f, total_point + p
    app.key_press(Input("key", "z", frozenset({"ctrl"})))
    for name, yaw, pitch in cameras:
        set_camera(app, yaw, pitch)
        f, p = compare(f"{name}, after its Undo", app, picker)
        total_face, total_point = total_face + f, total_point + p

    print(f"2./3. agreement with the CPU picker, {args.cursors} cursors per camera (integer pixel corners; "
          "half-px = the CPU agrees at the pixel centre)")
    real_total = 0
    for name, yaw, pitch in cameras:
        set_camera(app, yaw, pitch)
        points = spike_cursors(app.camera, mesh, args.cursors, seed=100 + len(name))
        for label, mode_key in (("face", "3"), ("vertex", "1")):
            res = agreement(app, picker, mode_key, points)
            nontrivial = args.cursors - res["both none"]
            real = res["gpu none"] + res["cpu none"] + res["other"]
            real_total += real
            share = 100.0 * res["same"] / nontrivial if nontrivial else float("nan")
            print(f"  {name:5s} {label:6s} non-trivial {nontrivial:3d}: same {res['same']:3d} ({share:5.1f} %), "
                  f"half-px {res['half-px']:3d}, gpu none {res['gpu none']:2d}, cpu none {res['cpu none']:2d}, "
                  f"other {res['other']:2d}")

    print("4. one pick after a camera change (ID render + read), 20 orbit steps, face / vertex mode")
    query = None
    try:
        query = drag_query()
    except Exception:  # noqa: BLE001 - a driver without GL_TIME_ELAPSED gives "n/a"
        pass
    cx, cy = W / 2.0, H / 2.0
    for label, mode_key in (("face", "3"), ("vertex", "1")):
        app.key_press(Input("key", mode_key))
        set_camera(app, 30, 15)
        walls, gpus = [], []
        for i in range(20):
            app.camera.orbit(0.01, 0.0)
            app._camera_changed()
            app.viewport.sync()
            gl.glFinish()
            if query is not None:
                query.begin()
            start = time.perf_counter()
            picker.pick(app, cx, cy)
            walls.append((time.perf_counter() - start) * 1000.0)
            if query is not None:
                gpus.append(query.end_ms())
        gpu_txt = f"; GPU time p50 {statistics.median(gpus):.2f} ms" if gpus else ""
        print(f"  {label:6s} wall p50 {statistics.median(walls):6.2f} ms, max {max(walls):6.2f} ms{gpu_txt}")

    verdict = "EXACT" if total_face == 0 else "NOT EXACT"
    print(f"B2 RESULT gl_PrimitiveID face mapping {verdict} (differing face pixels {total_face}, point pixels "
          f"{total_point}); position location store/face/point {locations}; real pick differences vs CPU "
          f"{real_total}")
    window.close()
    return 0


def drag_query():
    from drag_cost.probe_navigation_gl import _TimerQuery

    return _TimerQuery()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
