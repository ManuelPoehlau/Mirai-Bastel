"""Probe: can geodesic_pursuit adopt a torn target on the other side of a thin feature (chord gap <= budget)?"""
import sys, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "src", REPO / "examples", REPO / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from surface_slide import algorithms as A, geometries as G, harness as H
from surface_slide.fields import EdgeGraph, soft_weights, transport_frames

def run(thick, n, seed_xy, radius_h, circle_h, frames, gain=1.0, seed=0):
    g = G.cube_sphere(n)
    V = g.V * np.array([1.0, 1.0, thick])
    ref = H.build_ref(V, g.faces)
    h = ref.mean_edge
    front = np.flatnonzero(ref.V[:, 2] > 0.5 * thick)
    d = np.hypot(ref.V[front, 0] - seed_xy[0], ref.V[front, 1] - seed_xy[1])
    v = int(front[np.argmin(d)])
    graph = EdgeGraph(ref.nv, ref.edges, ref.V)
    verts, w = soft_weights(graph, [v], radius_h * h)
    pivot = int(np.flatnonzero(verts == v)[0])
    R = transport_frames(ref, graph, v, verts)
    setup = A.SlideSetup.from_vertices(ref, verts, w, pivot, R)
    rng = np.random.default_rng(seed)
    # drag: out towards the rim (+x) and round in circles of changing direction (turning drags tear)
    ang = np.linspace(0, 6 * np.pi, frames)
    rad = circle_h * h * np.minimum(1.0, np.linspace(0, 3, frames))
    path = np.stack([rad * np.cos(ang) + np.linspace(0, 1.2, frames), rad * np.sin(ang), np.zeros(frames)], axis=1)
    path += rng.normal(0, 0.05 * h, path.shape) * (np.arange(frames) > 0)[:, None]
    worst = {"teleports": 0, "max_ratio": 0.0, "lag_max": 0}
    for name, cand in (("pursuit", A.GeodesicPursuit("transport", gain=gain)), ("abs", A.GeodesicAbs("transport"))):
        cand.begin(setup)
        prev = setup.p0.copy(); prev_t = np.zeros((setup.n, 3)); tele = 0; ratio = 0.0; lag = 0
        side_prev = np.sign(prev[:, 2])
        for d_ in path:
            r = cand.update(d_)
            t = cand._target.tangents(d_) if name == "pursuit" else cand.tangents(d_)
            step = np.linalg.norm(r.pos - prev, axis=1); dt = np.linalg.norm(t - prev_t, axis=1)
            ok = dt > 1e-12
            if np.any(ok): ratio = max(ratio, float(np.max(step[ok] / dt[ok])))
            side = np.sign(r.pos[:, 2])
            far = (np.abs(prev[:, 2]) > 0.6 * thick) & (np.abs(r.pos[:, 2]) > 0.6 * thick)
            tele += int(np.sum((side != side_prev) & far))
            if name == "pursuit": lag = max(lag, int(cand.lagging.sum()))
            prev, prev_t, side_prev = r.pos, t, side
        crossed = int(np.sum(r.pos[:, 2] < 0))
        print(f"crossed to the back at the end: {crossed:3d}  thick={thick:<5} n={n:<3} {name:8s} vertices={setup.n:4d} front->back without passing the rim: {tele:4d}  max step/drag {ratio:6.2f}  max lagging {lag}")

for thick in (0.05, 0.02):
    for n in (8, 16):
        run(thick, n, (0.6, 0.0), 4.0, 2.0, 240)
