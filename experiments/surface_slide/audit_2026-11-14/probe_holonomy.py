"""Probe: discontinuity of the tree-based tangent transport between neighbouring vertices (holonomy across the cut)."""
import sys, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "src", REPO / "examples", REPO / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from surface_slide import scenarios as S, geometries as G, harness as H
from surface_slide.fields import EdgeGraph, soft_weights, transport_frames, minimal_rotation

def frame_jumps(ref, v, radius):
    graph = EdgeGraph(ref.nv, ref.edges, ref.V)
    verts, w = soft_weights(graph, [v], radius)
    R = transport_frames(ref, graph, v, verts)
    n0 = ref.VN[v]; e1 = np.cross(n0, np.eye(3)[int(np.argmin(np.abs(n0)))]); e1 /= np.linalg.norm(e1)
    row = {int(x): i for i, x in enumerate(verts)}
    t = np.einsum("nij,j->ni", R, e1)
    t -= np.einsum("ij,ij->i", t, ref.VN[verts])[:, None] * ref.VN[verts]
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    angs, wmin = [], []
    for a, b in ref.edges.tolist():
        if a in row and b in row:
            ta = minimal_rotation(ref.VN[a], ref.VN[b]) @ t[row[a]]
            c = np.clip(ta @ t[row[b]], -1, 1)
            angs.append(np.degrees(np.arccos(c))); wmin.append(min(w[row[a]], w[row[b]]))
    angs = np.array(angs); wmin = np.array(wmin)
    defect = 2 * np.pi - 0.0
    return len(verts), angs.max(), np.percentile(angs, 99), (angs > 10).sum(), wmin[np.argmax(angs)]

mesh, cage = S.gollum_cage_ref()
# nose tip: front-most vertex near x=0 at nose height
cand = np.flatnonzero(np.abs(cage.V[:, 0]) < 0.03)
tip = int(cand[np.argmax(cage.V[cand, 2])])
cases = {"nose_tip(front-most near plane)": tip}
for f in ("cheek", "brow", "nose_side", "eye_rim_low", "upper_lip"):
    cases[f] = S.front_vertex(cage, *S.CAGE_FEATURES[f])
for name, v in cases.items():
    for rad in (0.09, 0.15):
        n, mx, p99, big, wm = frame_jumps(cage, v, rad)
        print(f"cage {name:32s} r={rad:.2f} verts={n:4d}  edge frame jump max {mx:6.1f} deg  p99 {p99:5.1f}  edges>10deg {big:3d}  (min weight at worst edge {wm:.2f})")
g = G.cube_sphere(16); ref = H.build_ref(g.V, g.faces)
v = S.nearest_vertex(ref, (0, 0, 1.0))
for rad in (0.5, 1.0):
    n, mx, p99, big, wm = frame_jumps(ref, v, rad)
    print(f"sphere n16 face centre r={rad:.1f}R verts={n:4d}  edge frame jump max {mx:6.1f} deg  p99 {p99:5.1f}  edges>10deg {big:3d}")
