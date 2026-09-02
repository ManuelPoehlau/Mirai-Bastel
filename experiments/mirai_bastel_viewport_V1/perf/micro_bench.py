"""Headless CPU-Mikrobenchmarks der Viewport-Hot-Path-Bausteine (kein GL).

Misst die reinen Python-Kosten der Bausteine, die app.py pro Event/Frame
ausfuehrt — ohne Fenster, ohne GPU, reproduzierbar:

- Picking:  pick_nearest_vertex / pick_nearest_edge / pick_face
            (1 Projektion pro Vertex, 2 pro Edge, Ray-Triangle pro Face-Dreieck)
- camera.project_to_screen Einzelaufruf (inkl. basis()-Neuberechnung)
- Normalen-Rebuild: exakte Spiegelung von ModelerWindow._compute_normals
  (O(V*F)-Loop mit face_vertices-Kopien)
- Triangle-Array-Rebuild: Spiegelung von ModelerWindow._face_triangle_arrays
  (SHADED-Variante)
- Voller CPU-Anteil eines _rebuild_geometry (Arrays, ohne GL/VertexLists)
- Python-Allokationen pro Rebuild (tracemalloc)

Ausfuehrung:  python -m perf.micro_bench   (aus experiments/mirai_bastel_viewport_V1)
"""
from __future__ import annotations

import math
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

_THIS = Path(__file__).resolve().parent
_VIEWPORT_V1_DIR = _THIS.parent
_EXPERIMENTS_DIR = _VIEWPORT_V1_DIR.parent
for _path in (
    str(_VIEWPORT_V1_DIR),
    str(_EXPERIMENTS_DIR / "mirai_bastel_core_V1"),
    str(_EXPERIMENTS_DIR / "rigging-skinning-morphing"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from viewport.camera import OrbitCamera  # noqa: E402
from viewport.picking import pick_face, pick_nearest_edge, pick_nearest_vertex  # noqa: E402

from perf.synthetic_meshes import build_scaling_scenes  # noqa: E402
from viewport_adapter import DEFAULT_HEAD_ASSET, build_scene_from_obj, frame_camera_on_bounds  # noqa: E402

_WIDTH, _HEIGHT = 1024, 768
_REPS = 30


def measure(fn, reps: int = _REPS, budget_s: float = 8.0) -> tuple[float, float, float]:
    """Gibt (median_ms, min_ms, max_ms) ueber die Laeufe zurueck.

    Adaptive Wiederholungen: max. `reps` Laeufe, aber Abbruch, sobald die
    kumulierte Messzeit `budget_s` ueberschreitet (mind. 1 Lauf). Damit
    bleiben auch sekundenlange O(V*F)-Messungen bei 20k Quads handhabbar —
    bei grossen Meshes wird dann ein Einzel-Lauf berichtet.
    """
    times = []
    for _ in range(reps):
        start = time.perf_counter_ns()
        fn()
        times.append((time.perf_counter_ns() - start) / 1e6)
        if (sum(times) / 1000.0) > budget_s:
            break
    return statistics.median(times), min(times), max(times)


def reps_for(mesh) -> int:
    faces = len(mesh.all_face_ids())
    if faces <= 2000:
        return _REPS
    if faces <= 8000:
        return 3
    return 1


def compute_normals_like_app(mesh):
    """Exakte Spiegelung von ModelerWindow._compute_normals (app.py).

    Bewusst derselbe O(V*F)-Algorithmus inklusive face_vertices()-Kopien —
    die gemessenen Kosten sind also die echten Kosten dieser Stufe.
    """
    face_normals = {}
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        if len(boundary) < 3:
            face_normals[fid] = (0.0, 0.0, 1.0)
            continue
        p0 = mesh.vertex_position(boundary[0])
        p1 = mesh.vertex_position(boundary[1])
        p2 = mesh.vertex_position(boundary[2])
        ux, uy, uz = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        vx, vy, vz = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        face_normals[fid] = (
            (nx / length, ny / length, nz / length) if length > 1e-9 else (0.0, 0.0, 1.0)
        )

    vertex_normals = {}
    for vid in mesh.all_vertex_ids():
        acc = (0.0, 0.0, 0.0)
        for _fid, n in face_normals.items():
            if vid in mesh.face_vertices(_fid):
                acc = (acc[0] + n[0], acc[1] + n[1], acc[2] + n[2])
        length = math.sqrt(acc[0] ** 2 + acc[1] ** 2 + acc[2] ** 2)
        vertex_normals[vid] = (
            (acc[0] / length, acc[1] / length, acc[2] / length) if length > 1e-9 else (0.0, 0.0, 1.0)
        )
    return face_normals, vertex_normals


def face_triangle_arrays_like_app(mesh, face_normals, vertex_normals, display_flat: bool):
    """Spiegelung von ModelerWindow._face_triangle_arrays (SHADED/FLAT).

    App-korrekt: `_compute_normals()` läuft EINMAL pro Rebuild, danach
    verwenden die Triangle-Arrays die gemittelten/face-Normalen direkt —
    hier werden sie als Parameter übergeben (kein internes O(V*F)-Recompute).
    """
    positions, normals = [], []
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        if len(boundary) < 3:
            continue
        p0 = mesh.vertex_position(boundary[0])
        for i in range(1, len(boundary) - 1):
            vids = (boundary[0], boundary[i], boundary[i + 1])
            points = (p0, mesh.vertex_position(boundary[i]), mesh.vertex_position(boundary[i + 1]))
            for vid, pos in zip(vids, points):
                positions.extend(pos)
                normals.extend(face_normals[fid] if display_flat else vertex_normals[vid])
    return positions, normals


def cpu_rebuild_like_app(mesh) -> None:
    """CPU-Anteil eines _rebuild_geometry (Arrays), ohne GL/VertexLists.

    Exakt die App-Reihenfolge: Positions-/Edge-Flattening, dann EINMAL
    Normalen-Rebuild, dann Triangle-Arrays mit den gecachten Normalen.
    """
    vertex_ids = list(mesh.all_vertex_ids())
    positions = [c for vid in vertex_ids for c in mesh.vertex_position(vid)]
    edge_positions = []
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        edge_positions.extend(mesh.vertex_position(va))
        edge_positions.extend(mesh.vertex_position(vb))
    face_normals, vertex_normals = compute_normals_like_app(mesh)
    face_triangle_arrays_like_app(mesh, face_normals, vertex_normals, display_flat=False)


def run_mesh_block(title: str, mesh) -> str:
    camera = OrbitCamera()
    frame_camera_on_bounds(camera, mesh)
    sx, sy = _WIDTH * 0.5, _HEIGHT * 0.5
    reps = reps_for(mesh)

    single_proj = measure(
        lambda: camera.project_to_screen(mesh.vertex_position(min(mesh.all_vertex_ids())), _WIDTH, _HEIGHT),
        reps=500,
    )
    pick_v = measure(lambda: pick_nearest_vertex(camera, mesh, sx, sy, _WIDTH, _HEIGHT), reps=reps)
    pick_e = measure(lambda: pick_nearest_edge(camera, mesh, sx, sy, _WIDTH, _HEIGHT), reps=reps)
    pick_f = measure(lambda: pick_face(camera, mesh, sx, sy, _WIDTH, _HEIGHT), reps=reps)
    normals = measure(lambda: compute_normals_like_app(mesh), reps=reps)
    face_normals, vertex_normals = compute_normals_like_app(mesh)  # einmal (Cache wie in app)
    tri_arrays = measure(
        lambda: face_triangle_arrays_like_app(mesh, face_normals, vertex_normals, display_flat=False),
        reps=reps,
    )
    cpu_rebuild = measure(lambda: cpu_rebuild_like_app(mesh), reps=reps)

    # tracemalloc verlangsamt Allokationen erheblich (bis zu ~3-5x); deshalb
    # nur fuer kleine Meshes (< 8000 Faces) messen, bei grossen auslassen.
    peak_kib = float("nan")
    if len(mesh.all_face_ids()) < 8000:
        tracemalloc.start()
        cpu_rebuild_like_app(mesh)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_kib = peak / 1024.0

    v = len(mesh.all_vertex_ids())
    e = len(mesh.all_edge_ids())
    f = len(mesh.all_face_ids())

    alloc_text = f"{peak_kib:8.1f} KiB" if peak_kib == peak_kib else "   (ausgelassen, grosses Mesh)"
    lines = [
        f"--- {title}  (V={v}, E={e}, F={f}, reps<= {reps}, Budget 8 s/Messung) ---",
        f"project_to_screen (1 Vertex, inkl. basis()):  med={single_proj[0]:.4f} ms",
        f"pick_nearest_vertex (O(V)):                   med={pick_v[0]:8.2f} ms  max={pick_v[2]:8.2f}",
        f"pick_nearest_edge (O(E)):                     med={pick_e[0]:8.2f} ms  max={pick_e[2]:8.2f}",
        f"pick_face (O(F) Ray-Tri):                     med={pick_f[0]:8.2f} ms  max={pick_f[2]:8.2f}",
        f"normals-Rebuild O(V*F):                       med={normals[0]:8.2f} ms  max={normals[2]:8.2f}",
        f"face-triangle-Arrays (alle Faces):            med={tri_arrays[0]:8.2f} ms  max={tri_arrays[2]:8.2f}",
        f"CPU-Rebuild gesamt (ohne GL):                 med={cpu_rebuild[0]:8.2f} ms  max={cpu_rebuild[2]:8.2f}",
        f"Python-Allokationen pro CPU-Rebuild:          peak={alloc_text}",
    ]
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Viewport CPU-Mikrobenchmark (headless)")
    parser.add_argument(
        "--labels", type=str, default="324,1.3k,5k,20k",
        help="Komma-separierte Torus-Groessen (Standard: alle)",
    )
    args = parser.parse_args()
    labels = [l.strip() for l in args.labels.split(",") if l.strip()]

    out_path = _THIS / "micro_bench_results.txt"
    head_scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
    parts = [run_mesh_block("HEAD head_basemesh.obj", head_scene.mesh)]
    out_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")  # inkrementell sichern

    scenes = build_scaling_scenes()
    for label in labels:
        mesh = scenes[label].mesh
        faces = len(mesh.all_face_ids())
        parts.append(run_mesh_block(f"TORUS ~{label} (tatsaechlich {faces} Quads)", mesh))
        out_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")  # inkrementell sichern
        print(f"[block done] {label}", flush=True)

    report = "\n\n".join(parts)
    print(report)
    print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()
