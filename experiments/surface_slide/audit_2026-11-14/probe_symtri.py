"""Probe: is the drawn triangulation (viewport.derived.triangulate_face) mirror-symmetric on the Gollum cage?"""
import sys, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "src", REPO / "examples", REPO / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
R = str(REPO)
from pathlib import Path
from core.serialization import scene_from_json
from viewport.derived import triangulate_face
from surface_slide.fields import mirror_partners
from surface_slide.refsurf import triangulate as proto_tri

scene = scene_from_json(Path(R + "/scenes/Gollum_Head_01.mirai.json").read_text(encoding="utf-8"))
mesh = scene.mesh
vids = list(mesh.all_vertex_ids()); idx = {v: i for i, v in enumerate(vids)}
V = np.array([mesh.vertex_position(v) for v in vids])
faces = [[idx[v] for v in mesh.face_vertices(f)] for f in mesh.all_face_ids()]
partner = mirror_partners(V)
pos = {i: tuple(V[i]) for i in range(len(V))}
h = np.mean([np.linalg.norm(V[f[k]] - V[f[(k + 1) % len(f)]]) for f in faces for k in range(len(f))])
drawn = [triangulate_face(f, pos) for f in faces]
key = {frozenset(f): i for i, f in enumerate(faces)}
mism = 0; mism_tris = 0; self_mirror = 0; straddle = 0; folds = []; kinds = {}
convex_fan = sum(1 for f, t in zip(faces, drawn) if t == [(f[0], f[i], f[i + 1]) for i in range(1, len(f) - 1)])
for i, f in enumerate(faces):
    j = key.get(frozenset(int(partner[v]) for v in f))
    if j is None:
        continue
    if j == i:
        self_mirror += 1
        x = V[f, 0]
        if np.any(x > 0) and np.any(x < 0) and not set(map(tuple, (sorted(t) for t in drawn[i]))) == set(map(tuple, (sorted(int(partner[v]) for v in t) for t in drawn[i]))):
            straddle += 1
        continue
    if j < i:
        continue
    a = {tuple(sorted(int(partner[v]) for v in t)) for t in drawn[i]}
    b = {tuple(sorted(t)) for t in drawn[j]}
    if a != b:
        mism += 1; mism_tris += len(drawn[j])
        kinds[len(f)] = kinds.get(len(f), 0) + 1
        if len(f) == 4:
            q = V[f]
            folds.append(np.linalg.norm((q[0] + q[2]) / 2 - (q[1] + q[3]) / 2) / h)
# prototype rules: shorter diagonal + ear clip, unmirrored
T0, _ = proto_tri(V, faces)
tri0 = {tuple(sorted(t)) for t in T0.tolist()}
unm0 = sum(1 for t in T0.tolist() if tuple(sorted(int(partner[v]) for v in t)) not in tri0)
dr = [t for tt in drawn for t in tt]
drs = {tuple(sorted(t)) for t in dr}
unm_drawn = sum(1 for t in dr if tuple(sorted(int(partner[v]) for v in t)) not in drs)
folds = np.array(folds)
print(f"faces {len(faces)}, polygons drawn as plain fan {convex_fan}, h={h:.4f}")
print(f"drawn (fan/ear) triangulation: mirror pairs with non-mirrored triangles: {mism} faces ({mism_tris} tris) by size {kinds}; drawn triangles without mirror image: {unm_drawn} / {len(dr)}")
print(f"  quad fold height (diag-midpoint distance) on those quads: mean {folds.mean():.3f} h, p95 {np.percentile(folds,95):.3f} h, max {folds.max():.3f} h")
print(f"prototype per-face rules: triangles without mirror image {unm0} / {len(T0)}")
print(f"self-mirror faces {self_mirror}; of these with vertices on both sides and an asymmetric triangulation: {straddle}")

# accurate: distance from points of the drawn -x half to the mirror image of the drawn surface
from surface_slide.refsurf import RefSurface
from surface_slide.fields import mirror
T = np.array(dr, dtype=np.intp)
Vm = mirror(V)
mref = RefSurface(Vm, T[:, [0, 2, 1]])          # mirror image of the drawn surface (all of it)
P = []
for t in dr:
    a, b, c = V[list(t)]
    for w in ((1/3, 1/3, 1/3), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)):
        P.append(w[0] * a + w[1] * b + w[2] * c)
P = np.array(P)
P = P[P[:, 0] < -1e-9]
_, _, d = mref.closest_point(P)
print(f"drawn surface vs its own mirror image (points of the -x half): mean {d.mean()/h:.4f} h, p95 {np.percentile(d,95)/h:.3f} h, max {d.max()/h:.3f} h")
