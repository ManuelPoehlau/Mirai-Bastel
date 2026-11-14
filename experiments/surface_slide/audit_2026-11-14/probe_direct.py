"""Probe: direct minimal-rotation transport (pivot normal -> vertex normal, no tree) vs tree transport."""
import sys, time, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "src", REPO / "examples", REPO / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from surface_slide import algorithms as A, scenarios as S, harness as H
from surface_slide.fields import EdgeGraph, soft_weights, transport_frames, minimal_rotation

def direct_frames(VN, pivot_v, verts):
    a = VN[pivot_v]; b = VN[verts]
    v = np.cross(a[None, :], b); c = b @ a
    vx = np.zeros((len(verts), 3, 3))
    vx[:, 0, 1], vx[:, 0, 2], vx[:, 1, 0] = -v[:, 2], v[:, 1], v[:, 2]
    vx[:, 1, 2], vx[:, 2, 0], vx[:, 2, 1] = -v[:, 0], -v[:, 1], v[:, 0]
    anti = c < -1.0 + 1e-9               # opposite normals: no unique minimal rotation (identity, as fields.py)
    if np.any(anti):
        print(f"    direct transport: {int(anti.sum())} vertices with a normal opposite to the pivot's")
    R = np.eye(3)[None] + vx + np.einsum("nij,njk->nik", vx, vx) / np.where(anti, 1.0, 1.0 + c)[:, None, None]
    R[anti] = np.eye(3)
    return R

def jumps(ref, verts, R, v):
    n0 = ref.VN[v]; e1 = np.cross(n0, np.eye(3)[int(np.argmin(np.abs(n0)))]); e1 /= np.linalg.norm(e1)
    row = {int(x): i for i, x in enumerate(verts)}
    t = np.einsum("nij,j->ni", R, e1); t /= np.linalg.norm(t, axis=1, keepdims=True)
    out = []
    for a, b in ref.edges.tolist():
        if a in row and b in row:
            ta = minimal_rotation(ref.VN[a], ref.VN[b]) @ t[row[a]]
            out.append(np.degrees(np.arccos(np.clip(ta @ t[row[b]], -1, 1))))
    return max(out)

mesh, cage = S.gollum_cage_ref()
graph = EdgeGraph(cage.nv, cage.edges, cage.V)
cand = np.flatnonzero(np.abs(cage.V[:, 0]) < 0.03); tip = int(cand[np.argmax(cage.V[cand, 2])])
print("edge frame jump (max deg): tree vs direct")
for name, v in [("nose_tip", tip)] + [(f, S.front_vertex(cage, *S.CAGE_FEATURES[f])) for f in ("brow", "nose_side", "eye_rim_low", "upper_lip")]:
    verts, w = soft_weights(graph, [v], 0.15)
    Rt = transport_frames(cage, graph, v, verts); Rd = direct_frames(cage.VN, v, verts)
    print(f"  {name:12s} tree {jumps(cage, verts, Rt, v):5.1f}   direct {jumps(cage, verts, Rd, v):5.1f}   min n_p.n_i {float((cage.VN[verts] @ cage.VN[v]).min()):.2f}")

# distortion on the measured scenarios: tree transport vs direct transport (geodesic_pursuit[transport])
def with_direct(scn):
    s = scn.setup
    verts = s.verts
    R = direct_frames(scn.ref.VN, int(verts[s.pivot]), verts)
    return A.SlideSetup(s.ref, s.tri0, s.bary0, s.p0, s.n0, s.weights, s.verts, s.pivot, R, s.nbr)

import copy
scns = [x for x in S.cylinder_scenarios() if "rigid" in x.name] + [x for x in S.sphere_scenarios() if "rigid" in x.name] \
     + [x for x in S.gollum_scenarios("cage")] + [x for x in S.u_scenarios() if "C4" in x.name]
print(f"{'scenario':34s} | tree: rigid mean/max  all mean  ratio  closure | direct: rigid mean/max  all mean  ratio  closure")
for scn in scns:
    if scn.setup.transport is None:
        continue
    rt = H.run(scn, A.GeodesicPursuit("transport")).metrics
    s2 = copy.copy(scn); s2.setup = with_direct(scn)
    rd = H.run(s2, A.GeodesicPursuit("transport")).metrics
    def f(m):
        er = m.get("edges_rigid") or {}
        ea = m.get("edges") or {}
        return (f"{er.get('mean_abs_rel', float('nan'))*100:5.1f}%/{er.get('max_abs_rel', float('nan'))*100:5.1f}%  "
                f"{ea.get('mean_abs_rel', float('nan'))*100:6.1f}%  {m['continuity']['max_step_ratio']:5.2f}  {m['closure']['max'] if m.get('closure') else float('nan'):.2g}")
    print(f"{scn.name:34s} | {f(rt)} | {f(rd)}")
# begin cost: tree loop vs vectorised direct, 1000 / 10000 vertices on the 100k sphere
from surface_slide import geometries as G
g = G.cube_sphere(129); ref = H.build_ref(g.V, g.faces); gr = EdgeGraph(ref.nv, ref.edges, ref.V)
v = S.nearest_vertex(ref, (0, 0, 1.0))
for k in (1000, 10000):
    r = np.sqrt(k / (ref.nv / (4 * np.pi))) / np.sqrt(np.pi) * 1.0
    verts, w = soft_weights(gr, [v], r)
    t0 = time.perf_counter(); transport_frames(ref, gr, v, verts); t1 = time.perf_counter(); direct_frames(ref.VN, v, verts); t2 = time.perf_counter()
    print(f"begin transport, {len(verts)} vertices on {ref.nv}: tree {1e3*(t1-t0):.1f} ms, direct {1e3*(t2-t1):.2f} ms")
