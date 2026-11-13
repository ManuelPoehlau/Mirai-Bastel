"""Measurements shared by every scenario. Each function returns plain floats / ints so results serialise to JSON.

Deviation is always measured against the surface *region the point is tracked in*, never only against the globally
nearest surface: `tracked_deviation` descends from the anchor the candidate claims, and `continuity` checks - without
trusting the candidate - that consecutive anchors are connected over the surface by a path about as long as the step
in space. A point that silently switched to another wall has a small global distance but fails that check.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

from .refsurf import RefSurface

_I = np.intp


def dist_stats(d: np.ndarray, ref: RefSurface | None = None, prefix: str = "") -> dict:
    d = np.asarray(d, dtype=np.float64)
    if not len(d):
        return {f"{prefix}mean": 0.0, f"{prefix}p95": 0.0, f"{prefix}max": 0.0}
    out = {f"{prefix}mean": float(d.mean()), f"{prefix}p95": float(np.percentile(d, 95)), f"{prefix}max": float(d.max())}
    if ref is not None:
        out[f"{prefix}max_rel_edge"] = float(d.max() / ref.mean_edge) if ref.mean_edge else 0.0
        out[f"{prefix}max_rel_bbox"] = float(d.max() / ref.bbox_diag) if ref.bbox_diag else 0.0
    return out


def tracked_deviation(ref: RefSurface, pos: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """Distance from each position to the flat reference surface, searched by adjacency descent from the anchor
    triangle the candidate reports (the surface region it claims to be on)."""
    _, _, d, _ = ref.closest_point_local(pos, tri)
    return d


def edge_stats(V0: np.ndarray, V1: np.ndarray, edges: np.ndarray, moved: np.ndarray, bins=None) -> dict:
    """Relative length change of the visible edges with at least one moved end. `moved`: bool per vertex."""
    sel = moved[edges[:, 0]] | moved[edges[:, 1]]
    e = edges[sel]
    if not len(e):
        return {"n_edges": 0}
    l0 = np.linalg.norm(V0[e[:, 0]] - V0[e[:, 1]], axis=1)
    l1 = np.linalg.norm(V1[e[:, 0]] - V1[e[:, 1]], axis=1)
    rel = (l1 - l0) / np.where(l0 > 0, l0, 1.0)
    a = np.abs(rel)
    bins = np.array([0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, np.inf]) if bins is None else bins
    hist, _ = np.histogram(a, bins=bins)
    return {
        "n_edges": int(len(e)),
        "mean_abs_rel": float(a.mean()),
        "p95_abs_rel": float(np.percentile(a, 95)),
        "max_abs_rel": float(a.max()),
        "mean_signed_rel": float(rel.mean()),
        "min_rel": float(rel.min()),
        "max_rel": float(rel.max()),
        "p95_abs_change": float(np.percentile(np.abs(l1 - l0), 95)),
        "hist_bins": [float(b) for b in bins[:-1]],
        "hist": [int(h) for h in hist],
        "collapsed": int(np.sum(l1 < 0.05 * l0)),
    }


def folded_triangles(ref: RefSurface, V1: np.ndarray, verts: np.ndarray, anchor_tri: np.ndarray, moved: np.ndarray
                     ) -> int:
    """Triangles of the moved mesh (with a moved corner) that now face against the surface they lie on: their new
    normal against the mean reference normal at their corners' current anchors (unmoved corners: vertex normal)."""
    here = ref.VN.copy()
    here[verts] = ref.N[anchor_tri]
    T = ref.T[moved[ref.T].any(axis=1)]
    if not len(T):
        return 0
    n1 = np.cross(V1[T[:, 1]] - V1[T[:, 0]], V1[T[:, 2]] - V1[T[:, 0]])
    return int(np.sum(np.einsum("ij,ij->i", n1, here[T].sum(axis=1)) < 0.0))


class SurfaceGraph:
    """Vertex graph over the *triangle* edges of the reference, for bounded surface-distance queries."""

    def __init__(self, ref: RefSurface) -> None:
        a = ref.T.ravel()
        b = np.roll(ref.T, -1, axis=1).ravel()
        pairs = np.unique(np.stack([np.minimum(a, b), np.maximum(a, b)], axis=1), axis=0)
        length = np.linalg.norm(ref.V[pairs[:, 0]] - ref.V[pairs[:, 1]], axis=1)
        src = np.r_[pairs[:, 0], pairs[:, 1]]
        dst = np.r_[pairs[:, 1], pairs[:, 0]]
        w = np.r_[length, length]
        order = np.argsort(src, kind="stable")
        self.ptr = np.r_[0, np.cumsum(np.bincount(src, minlength=ref.nv))].tolist()
        self.nbr = dst[order].tolist()
        self.w = w[order].tolist()
        self.ref = ref

    def distance(self, tri_a: int, p_a: np.ndarray, tri_b: int, p_b: np.ndarray, limit: float) -> float:
        """Upper bound of the surface distance between two anchored points (edge paths), `inf` beyond `limit`."""
        ref = self.ref
        if tri_a == tri_b:
            return float(np.linalg.norm(p_a - p_b))
        goal = {int(v): float(np.linalg.norm(ref.V[v] - p_b)) for v in ref.T[tri_b]}
        heap = [(float(np.linalg.norm(ref.V[v] - p_a)), int(v)) for v in ref.T[tri_a]]
        heapq.heapify(heap)
        dist = {v: d for d, v in heap}
        done: set[int] = set()
        best = math.inf
        while heap:
            d, v = heapq.heappop(heap)
            if v in done:
                continue
            done.add(v)
            if d >= min(best, limit):
                break
            if v in goal:
                best = min(best, d + goal[v])
            for i in range(self.ptr[v], self.ptr[v + 1]):
                o = self.nbr[i]
                nd = d + self.w[i]
                if nd < dist.get(o, math.inf) and nd < limit:
                    dist[o] = nd
                    heapq.heappush(heap, (nd, o))
        return best if best <= limit else math.inf


def continuity(ref: RefSurface, graph: SurfaceGraph, tris: np.ndarray, poss: np.ndarray, drive: np.ndarray) -> dict:
    """Frame-to-frame continuity of one run. `tris (F, n)`, `poss (F, n, 3)` are the anchors' triangles and flat
    positions per frame (frame 0 = start); `drive (F, n)` the free-move step length `w |d_k - d_{k-1}|` of each point.

    - `ratio`: |step in space| / |drive step| (a slide never has to move faster than the drag, so values far above 1
      are pops);
    - a *region jump*: consecutive anchors that share no vertex and whose surface distance exceeds
      `3 x step in space + 2 x mean edge` (or is not reachable at all within that bound): the point left the surface
      part it was on without travelling there.
    """
    F, n = tris.shape
    h = ref.mean_edge
    step = np.linalg.norm(poss[1:] - poss[:-1], axis=2)                  # (F-1, n)
    floor = 1e-9 * max(ref.bbox_diag, 1e-300)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(drive[1:] > floor, step / np.maximum(drive[1:], floor), 0.0)
    # moved although the drag did not: count against one mean edge
    ghost = np.where(drive[1:] <= floor, step / h, 0.0)
    jumps = 0
    worst_detour = 1.0
    events = []
    T = ref.T
    for k in range(1, F):
        ta, tb = tris[k - 1], tris[k]
        differ = ta != tb
        if not np.any(differ):
            continue
        idx = np.flatnonzero(differ)
        va, vb = T[ta[idx]], T[tb[idx]]
        share = (va[:, :, None] == vb[:, None, :]).any(axis=(1, 2))
        for i in idx[~share]:
            e = float(step[k - 1, i])
            limit = 3.0 * e + 2.0 * h
            g = graph.distance(int(ta[i]), poss[k - 1, i], int(tb[i]), poss[k, i], limit)
            if not math.isfinite(g):
                jumps += 1
                if len(events) < 20:
                    events.append({"frame": int(k), "point": int(i), "step": e})
            elif e > 1e-12:
                worst_detour = max(worst_detour, g / e)
    return {
        "max_step_ratio": float(ratio.max(initial=0.0)),
        "p99_step_ratio": float(np.percentile(ratio, 99)) if ratio.size else 0.0,
        "max_ghost_step_rel_edge": float(ghost.max(initial=0.0)),
        "region_jumps": int(jumps),
        "max_detour": float(worst_detour),
        "jump_events": events,
    }


def flag_counts(flags: np.ndarray) -> dict:
    from . import geodesic as geo

    names = {"boundary": geo.FLAG_BOUNDARY, "stuck": geo.FLAG_STUCK, "blocked": geo.FLAG_BLOCKED,
             "maxiter": geo.FLAG_MAXITER, "fallback": geo.FLAG_FALLBACK}
    return {k: int(np.sum((flags & bit) > 0)) for k, bit in names.items()}
