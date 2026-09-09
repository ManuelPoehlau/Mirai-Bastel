"""Integration Lab — headless Report / Performance-Probe (ohne Fenster).

    python experiments/mirai_bastel_integration_lab/report.py

Diese Probe nutzt exakt dieselbe Integrationskette wie das interaktive Lab
(OBJ-Loader -> src.core -> Core->Render-Adapter -> Production-Viewport
`src.viewport`), aber mit dem deterministischen `TraceStore` statt des
pyglet-GPU-Pfads. Sie misst die
vier für die Lag-Frage relevanten Szenarien am REALEN Head-Basemesh:

1. initialer Aufbau (Mesh-Ableitung + RenderMesh.build)
2. Kamera-Orbit  (nur camera_uniforms; keine Geometry-/Mesh-Rebuilds)
3. Selection     (nur highlight_flags; keine Geometry)
4. Vertex-Move   (Geometry-Partial-Update; Core zuerst)

Kein Benchmark-Framework — nur ein sichtbarer Kodiertest, um festzustellen,
OB der alte Lag weiter existiert und WELCHE Integrationsgrenze ihn erzeugt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO_ROOT), str(_REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import CoreRenderBinding, render_triangle_count  # noqa: E402
from adapters.obj_to_core import (  # noqa: E402
    DEFAULT_HEAD_ASSET,
    face_type_counts,
    mesh_debug_report,
)
from lab_camera import LabOrbitCamera  # noqa: E402
from scene.scene_objects import build_cube_scene, build_head_scene, build_lab_scene  # noqa: E402

from viewport.resource_store import TraceStore  # noqa: E402  (Production, Gate 5)


def _timeit(fn, *args, **kwargs) -> tuple[float, object]:
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return (time.perf_counter() - t0) * 1000.0, result


def _counter_delta(binding: CoreRenderBinding, name: str) -> int:
    return binding.render.stats.counters.get(name, 0)


def probe_object(name: str, core_mesh) -> None:
    print("=" * 72)
    print(f"OBJEKT: {name}")
    print("=" * 72)
    print(mesh_debug_report(name, core_mesh).rstrip())

    # -- 1) Initialer Aufbau -------------------------------------------------
    t_build, binding = _timeit(CoreRenderBinding, core_mesh, TraceStore)
    print(f"Triangulierte Render-Triangles : {binding.triangle_count} "
          f"(Formel: {render_triangle_count(core_mesh)})")
    print(f"Initialer Aufbau               : {t_build:8.2f} ms "
          f"({binding.render.stats.counters.get('gpu_resource_creations', 0)} "
          f"Resource-Creations)")

    camera = LabOrbitCamera(distance=8.0)
    binding.bind_camera(camera)
    binding.render.aspect = 1.6
    base_rebuilds = _counter_delta(binding, "mesh_rebuilds")

    # Einmaliger Warm-up: legt die camera_uniforms-Ressource an (beim
    # interaktiven Lab passiert das beim Build; hier wird die Kamera erst
    # NACH dem Build gebunden). Danach ist die IDs-Basis stabil.
    camera.orbit(0.0, 0.0)
    binding.apply_camera(aspect=1.6)
    ids_before = dict(binding.render.store.resource_ids())

    # -- 2) Kamera-Orbit (nur Uniforms) ---------------------------------------
    n = 60
    t0 = time.perf_counter()
    for _ in range(n):
        camera.orbit(0.01, 0.005)
        binding.apply_camera(aspect=1.6)
    t_cam = (time.perf_counter() - t0) * 1000.0
    ids_after_cam = dict(binding.render.store.resource_ids())
    print(f"\n[Camera] {n} Orbits                : {t_cam:7.2f} ms "
          f"({t_cam / n:5.2f} ms/Op)")
    print(f"         camera_updates={_counter_delta(binding, 'camera_updates')}  "
          f"mesh_rebuilds={_counter_delta(binding, 'mesh_rebuilds') - base_rebuilds}  "
          f"partial_updates={_counter_delta(binding, 'partial_updates')}  "
          f"IDs stabil={ids_before == ids_after_cam}")

    # -- 3) Selection (nur Overlay) ------------------------------------------
    n = 20
    t0 = time.perf_counter()
    for i in range(n):
        vid = binding.core_mesh.all_vertex_ids()[i * 17 % len(binding.core_mesh.all_vertex_ids())]
        binding.select_vertex(vid)
    t_sel = (time.perf_counter() - t0) * 1000.0
    print(f"\n[Selection] {n} Setz-Operationen    : {t_sel:7.2f} ms "
          f"({t_sel / n:5.2f} ms/Op)")
    print(f"         selection_updates={_counter_delta(binding, 'selection_updates')}  "
          f"mesh_rebuilds={_counter_delta(binding, 'mesh_rebuilds') - base_rebuilds}")

    # -- 4) Vertex-Move (Core zuerst, dann Geometry-Partial-Update) ----------
    n = 40
    moved = binding.core_mesh.all_vertex_ids()[:n]
    t0 = time.perf_counter()
    for i, vid in enumerate(moved):
        binding.move_vertex(vid, (0.0, 0.05 * i, 0.0))
    t_move = (time.perf_counter() - t0) * 1000.0
    print(f"\n[Vertex-Move] {n} Moves (+Y)         : {t_move:7.2f} ms "
          f"({t_move / n:5.2f} ms/Move)")
    print(f"         vertex_updates={_counter_delta(binding, 'vertex_updates')}  "
          f"partial_updates={_counter_delta(binding, 'partial_updates')}  "
          f"geometry_uploads={_counter_delta(binding, 'geometry_uploads')}  "
          f"mesh_rebuilds={_counter_delta(binding, 'mesh_rebuilds') - base_rebuilds}")
    print()


def main() -> int:
    print("Mirai-Bastel — Integration Lab: Headless Report (TraceStore)")
    lab = build_lab_scene()
    for obj in lab.objects:
        probe_object(obj.name, obj.mesh)
    print("=" * 72)
    print("Hinweis: Diese Probe läuft mit dem in-memory `TraceStore` (CPU).")
    print("GPU-Frame-Zeiten sind nur interaktiv messbar (run.py).")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())