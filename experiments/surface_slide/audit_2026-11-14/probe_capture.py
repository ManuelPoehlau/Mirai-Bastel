"""Probe: Production-side costs the prototype bench did not include (container)."""
import sys, time, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "src", REPO / "examples", REPO / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
R = str(REPO)
from loaders.obj_loader import load_obj
from mirai.scene_factory import mesh_from_obj_data
from viewport.derived import triangulate_mesh_face, triangulate_face
from surface_slide.refsurf import RefSurface

def t(f, n=3):
    best = 1e9; out = None
    for _ in range(n):
        s = time.perf_counter(); out = f(); best = min(best, time.perf_counter() - s)
    return best * 1e3, out

for path in (R + "/examples/meshes/gollum.obj", R + "/experiments/drag_cost/fixtures/gollum_87k.obj"):
    mesh = mesh_from_obj_data(load_obj(path))
    vids = list(mesh.all_vertex_ids()); fids = list(mesh.all_face_ids())
    ms_ids, (vids, index) = t(lambda: (lambda v: (v, {x: i for i, x in enumerate(v)}))(list(mesh.all_vertex_ids())))
    ms_pos, V = t(lambda: np.array([mesh.vertex_position(v) for v in vids], dtype=np.float64))
    ms_faces, faces = t(lambda: [[index[v] for v in mesh.face_vertices(f)] for f in fids])
    ms_tri, tris = t(lambda: [tri for f in fids for tri in triangulate_mesh_face(mesh, f)], 1)
    T = np.array([[index[a], index[b], index[c]] for a, b, c in tris], dtype=np.intp)
    ms_ref, ref = t(lambda: RefSurface(V, T), 1)
    # journal write of 1000 vertices (core only, no viewport)
    sel = vids[:1000]
    def write():
        ch = mesh.begin_change()
        for v in sel:
            p = mesh.vertex_position(v)
            mesh.set_vertex_position(v, (p[0] + 1e-9, p[1], p[2]))
        d = mesh.end_change(ch)
        return d
    ms_w, _ = t(write)
    print(f"{path.split('/')[-1]}: nv={len(vids)} nf={len(fids)} nt={len(T)} | ids+index {ms_ids:.1f} ms, positions->array {ms_pos:.1f} ms, faces->index {ms_faces:.1f} ms, "
          f"triangulate_mesh_face(all) {ms_tri:.0f} ms, RefSurface build {ms_ref:.0f} ms | core journal write 1000 V {ms_w:.2f} ms")
