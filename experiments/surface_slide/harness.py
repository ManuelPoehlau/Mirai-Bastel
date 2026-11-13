"""Run one candidate over one scenario and measure it. A scenario fixes everything but the algorithm: the reference
surface, the moving points with their weights, and the drag as a list of absolute world-space deltas (one per
frame), so candidates are compared under identical conditions and a failure is reproducible from the scenario name."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import metrics as M
from .algorithms import Candidate, SlideSetup
from .refsurf import RefSurface, triangulate


def build_ref(V: np.ndarray, faces: list, partner: np.ndarray | None = None) -> RefSurface:
    """`partner` (mirror partner per vertex) makes the triangulation mirror-symmetric (`refsurf.triangulate`)."""
    T, tri_face = triangulate(V, faces, partner)
    return RefSurface(V, T, tri_face, faces)


def line_path(delta, frames: int) -> np.ndarray:
    delta = np.asarray(delta, dtype=np.float64)
    return np.array([delta * (k / frames) for k in range(1, frames + 1)])


def polyline_path(points, frames_per_leg: int) -> np.ndarray:
    """Through the given deltas in order, starting from zero."""
    out = []
    prev = np.zeros(3)
    for p in points:
        p = np.asarray(p, dtype=np.float64)
        out += [prev + (p - prev) * (k / frames_per_leg) for k in range(1, frames_per_leg)] + [p.copy()]
        prev = p
    return np.array(out)


def circle_path(u, v, radius: float, frames: int, turns: float = 1.0) -> np.ndarray:
    """A closed loop of drag vectors through zero: centre `radius * u`, starting and ending at delta = 0."""
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    a = np.linspace(0.0, 2.0 * np.pi * turns, frames + 1)[1:]
    return radius * ((1.0 - np.cos(a))[:, None] * u + np.sin(a)[:, None] * v)


@dataclass
class Scenario:
    name: str
    ref: RefSurface
    setup: SlideSetup
    path: np.ndarray                                   # (F, 3) absolute drag per frame
    analytic: object | None = None                     # .distance(P) to the smooth surface the mesh samples
    #: (setup, final delta) -> intended end positions, where an exact or analytic answer exists
    truth: Callable | None = None
    #: (tri, bary, pos) -> integer region label per point; `expected_region` the label each point must keep
    region: Callable | None = None
    expected_region: np.ndarray | None = None
    notes: str = ""
    tags: dict = field(default_factory=dict)


@dataclass
class Run:
    scenario: str
    candidate: str
    metrics: dict
    pos: np.ndarray        # (F + 1, n, 3), frame 0 = start
    tri: np.ndarray        # (F + 1, n)
    bary: np.ndarray       # (F + 1, n, 3)
    flags: np.ndarray      # (n,) or-ed over frames


_GRAPHS: dict[int, M.SurfaceGraph] = {}


def _graph(ref: RefSurface) -> M.SurfaceGraph:
    g = _GRAPHS.get(id(ref))
    if g is None or g.ref is not ref:
        g = _GRAPHS[id(ref)] = M.SurfaceGraph(ref)
    return g


def run(scn: Scenario, cand: Candidate) -> Run:
    ref, setup = scn.ref, scn.setup
    n, F = setup.n, len(scn.path)
    pos = np.zeros((F + 1, n, 3))
    tri = np.zeros((F + 1, n), dtype=np.intp)
    bary = np.zeros((F + 1, n, 3))
    flags = np.zeros(n, dtype=np.uint8)
    pos[0], tri[0], bary[0] = setup.p0, setup.tri0, setup.bary0
    t0 = time.perf_counter()
    cand.begin(setup)
    t_begin = time.perf_counter() - t0
    times = []
    passes = 0
    for k, delta in enumerate(scn.path, start=1):
        t0 = time.perf_counter()
        r = cand.update(delta)
        times.append(time.perf_counter() - t0)
        pos[k], tri[k], bary[k] = r.pos, r.tri, r.bary
        flags |= r.flags
        passes = max(passes, r.passes)

    final = pos[-1]
    w = setup.weights
    moved_rows = w > 0.0
    m: dict = {"n_points": int(n), "frames": int(F), "begin_ms": t_begin * 1e3,
               "update_ms_mean": float(np.mean(times) * 1e3), "update_ms_max": float(np.max(times) * 1e3),
               "max_passes": int(passes)}
    m["flags"] = M.flag_counts(flags)

    # A. deviation from the reference surface, in the tracked region
    flat = ref.point(tri[-1], bary[-1])
    m["dev_anchor"] = M.dist_stats(np.linalg.norm(final - flat, axis=1), ref)
    m["dev_tracked"] = M.dist_stats(M.tracked_deviation(ref, final, tri[-1]), ref)
    worst_tracked = 0.0
    for k in range(1, F + 1):
        worst_tracked = max(worst_tracked, float(M.tracked_deviation(ref, pos[k], tri[k]).max(initial=0.0)))
    m["dev_tracked_max_over_frames"] = worst_tracked
    m["dev_tracked_max_over_frames_rel_edge"] = worst_tracked / ref.mean_edge
    if scn.analytic is not None:
        m["dev_analytic"] = M.dist_stats(scn.analytic.distance(final), ref)
        m["dev_analytic_start"] = M.dist_stats(scn.analytic.distance(setup.p0), ref)
    if scn.truth is not None:
        intended = scn.truth(setup, scn.path[-1])
        m["err_intended"] = M.dist_stats(np.linalg.norm(final - intended, axis=1), ref)
    if scn.region is not None:
        wrong_final = scn.region(tri[-1], bary[-1], final) != scn.expected_region
        wrong_any = np.zeros(n, dtype=bool)
        for k in range(1, F + 1):
            wrong_any |= scn.region(tri[k], bary[k], pos[k]) != scn.expected_region
        m["wrong_region_final"] = int(wrong_final.sum())
        m["wrong_region_any_frame"] = int(wrong_any.sum())

    # B. edge lengths of the moving mesh (self-slide: its vertices are the reference's)
    if np.all(setup.verts >= 0):
        V1 = ref.V.copy()
        V1[setup.verts] = final
        moved = np.zeros(ref.nv, dtype=bool)
        moved[setup.verts[moved_rows]] = True
        m["edges"] = M.edge_stats(ref.V, V1, ref.edges, moved)
        # the same weights moved freely in space (no surface): the distortion the falloff alone causes
        Vfree = ref.V.copy()
        Vfree[setup.verts] = setup.p0 + w[:, None] * scn.path[-1][None, :]
        m["edges_free_move"] = M.edge_stats(ref.V, Vfree, ref.edges, moved)
        # edges whose two ends both carry full weight: a rigid piece of the selection, no falloff involved
        full = np.zeros(ref.nv, dtype=bool)
        full[setup.verts[w >= 1.0 - 1e-12]] = True
        both = full[ref.edges[:, 0]] & full[ref.edges[:, 1]]
        if np.any(both):
            m["edges_rigid"] = M.edge_stats(ref.V, V1, ref.edges[both], full)
        m["folded_tris"] = M.folded_triangles(ref, V1, setup.verts, tri[-1], moved)
        m["folded_tris_free_move"] = M.folded_triangles(ref, Vfree, setup.verts, setup.tri0, moved)

    # C. stability
    drive = np.zeros((F + 1, n))
    prev = np.zeros(3)
    for k, delta in enumerate(scn.path, start=1):
        drive[k] = w * np.linalg.norm(delta - prev)
        prev = delta
    flat_frames = np.stack([ref.point(tri[k], bary[k]) for k in range(F + 1)])
    m["continuity"] = M.continuity(ref, _graph(ref), tri, flat_frames, drive)
    m["travel_rel_edge"] = float(np.linalg.norm(final - setup.p0, axis=1).max() / ref.mean_edge)
    if np.allclose(scn.path[-1], 0.0):
        m["closure"] = M.dist_stats(np.linalg.norm(final - setup.p0, axis=1), ref)
    return Run(scn.name, cand.label, m, pos, tri, bary, flags)


def run_many(scn: Scenario, cands: list[Candidate]) -> dict[str, Run]:
    return {c.label: run(scn, c) for c in cands}
