"""Headless cost and memory of the Core mesh on a dense OBJ (architecture audit 2026-10-20).

Read-only: loads a mesh, times `vertex_edges`, `face_edges`, `export_state`, `load_state`, and measures the
memory of the mesh and of one `export_state()` snapshot (what one undo step stores twice). No GL, no window.
Run: python experiments/architecture_audit_probes/probe_mesh_cost.py [obj ...]
"""
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "examples")]

from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402


def median_ms(fn, n=3):
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def main(paths):
    for path in paths:
        tracemalloc.start()
        scene = build_core_scene_from_obj(path)
        mesh_bytes, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mesh = scene.mesh
        verts = mesh.all_vertex_ids()
        v, e, f = len(verts), len(mesh.all_edge_ids()), len(mesh.all_face_ids())
        tracemalloc.start()
        state = mesh.export_state()
        snap_bytes, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        vid = verts[v // 2]
        print(f"{Path(path).name}: V={v} E={e} F={f}")
        print(f"  mesh + scene memory ~{mesh_bytes / 1e6:.1f} MB; one snapshot ~{snap_bytes / 1e6:.0f} MB, "
              f"one undo step (before + after) ~{2 * snap_bytes / 1e6:.0f} MB")
        print(f"  vertex_edges (1 call, O(E))      {median_ms(lambda: mesh.vertex_edges(vid), 5):8.2f} ms")
        print(f"  face_edges of every face         {median_ms(lambda: [mesh.face_edges(x) for x in mesh.all_face_ids()]):8.1f} ms")
        print(f"  export_state                     {median_ms(mesh.export_state):8.1f} ms")
        print(f"  load_state                       {median_ms(lambda: mesh.load_state(state)):8.1f} ms")
        print(f"  export_state() == state          {median_ms(lambda: mesh.export_state() == state):8.1f} ms (incl. one export)")


if __name__ == "__main__":
    args = sys.argv[1:] or [str(ROOT / "examples/meshes/gollum_20k.obj"), str(ROOT / "examples/meshes/gollum.obj")]
    main(args)
