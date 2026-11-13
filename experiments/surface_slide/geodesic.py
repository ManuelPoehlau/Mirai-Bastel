"""Straightest geodesics on a `RefSurface`, traced for many points at once (NumPy, one triangle crossing per pass).

A ray is `(triangle, barycentric position, unit 3D direction in the triangle's plane, remaining length)`. Inside a
triangle it moves straight; at an edge the direction is *unfolded* into the next triangle (its components along the edge
and perpendicular to it are kept, the perpendicular now pointing into the neighbour), which is the straight line of the
two triangles laid flat - Polthier & Schmies, "Straightest Geodesics on Polyhedral Surfaces" (1998). The anchor is
carried across each edge by relabelling the two shared corners, so it is always exact on the surface: nothing is ever
projected.

A start exactly on a vertex (the normal case: a mesh vertex sliding over its own snapshot) has no single triangle. The
direction is given in the vertex tangent plane (normal `VN`); the triangle whose corner wedge contains it, seen along
the normal, takes the ray, and the direction is lifted onto that triangle along the normal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .refsurf import RefSurface, _unit

_I = np.intp

FLAG_BOUNDARY = 1    #: stopped at a boundary (or barrier) edge with length left
FLAG_STUCK = 2       #: no progress (degenerate triangles or a vertex the path could not leave)
FLAG_BLOCKED = 4     #: a start on a boundary vertex pointing off the surface: not moved
FLAG_MAXITER = 8     #: crossing limit reached
FLAG_FALLBACK = 16   #: (projection candidates) the primary query failed, a fallback answered
FLAG_VERTEX = 32     #: (diagnostic) the path passed within tolerance of a vertex


@dataclass
class Trace:
    tri: np.ndarray        # (n,)
    bary: np.ndarray       # (n, 3)
    direction: np.ndarray  # (n, 3) unit direction at the end point (in the end triangle's plane)
    remaining: np.ndarray  # (n,) length not travelled (boundary / stuck)
    flags: np.ndarray      # (n,) uint8
    crossings: np.ndarray  # (n,) edges crossed
    passes: int = 0        # passes of the batch loop (= the longest path in crossings)


def launch_from_vertices(ref: RefSurface, v: np.ndarray, t_dir: np.ndarray, nbr: np.ndarray | None = None
                         ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Start rays at vertices `v` in the unit tangent directions `t_dir` -> `(tri, bary, direction, flags)`."""
    v = np.asarray(v, dtype=_I)
    n = len(v)
    cnt = ref.valence[v]
    total = int(cnt.sum())
    rep = np.repeat(np.arange(n, dtype=_I), cnt)
    pos = np.arange(total, dtype=_I) - np.repeat(np.cumsum(cnt) - cnt, cnt) + np.repeat(ref.vt_ptr[v], cnt)
    f = ref.vt_tri[pos]
    c = ref.vt_corner[pos]
    nv = ref.VN[v][rep]
    nf = ref.N[f]
    t = t_dir[rep]
    denom = np.einsum("ij,ij->i", nv, nf)
    t_nf = np.einsum("ij,ij->i", t, nf)
    lift = denom > 0.05
    # lift along the vertex normal (keeps the tangent-plane direction); a triangle seen edge-on or from behind
    # gets the plain projection instead
    d = np.where(lift[:, None], t - (t_nf / np.where(lift, denom, 1.0))[:, None] * nv, t - t_nf[:, None] * nf)
    d = _unit(d)
    k1 = (c + 1) % 3
    k2 = (c + 2) % 3
    rows = np.arange(total)
    in1 = np.einsum("ij,ij->i", d, ref.Pin[f, k1])
    in2 = np.einsum("ij,ij->i", d, ref.Pin[f, k2])
    score = np.minimum(in1, in2)
    score = np.where(ref.degenerate[f] | ~np.isfinite(score), -np.inf, score)
    order = np.lexsort((score, rep))
    last = order[np.r_[rep[order][1:] != rep[order][:-1], True]]   # the best incident triangle of each ray
    tri = f[last]
    corner = c[last]
    best = score[last]
    dd = d[last]
    # a direction just outside every wedge (lifting is not exactly consistent between neighbours): walk the edge
    for kk, comp in ((k1[last], in1[last]), (k2[last], in2[last])):
        bad = comp < 0.0
        if np.any(bad):
            dd[bad] -= comp[bad, None] * ref.Pin[tri[bad], kk[bad]]
    dd = _unit(dd)
    bary = np.zeros((n, 3))
    bary[np.arange(n), corner] = 1.0
    flags = np.zeros(n, dtype=np.uint8)
    blocked = ref.v_boundary[v] & (best < -1e-9)
    if nbr is not None:  # a barrier vertex behaves like a boundary vertex
        on_barrier = np.zeros(ref.nv, dtype=bool)
        cut = (nbr < 0) & (ref.nbr >= 0)
        tt, kk = np.nonzero(cut)
        on_barrier[ref.T[tt, (kk + 1) % 3]] = True
        on_barrier[ref.T[tt, (kk + 2) % 3]] = True
        blocked |= on_barrier[v] & (best < -1e-9)
    flags[blocked] |= FLAG_BLOCKED
    return tri, bary, dd, flags


def launch_from_anchors(ref: RefSurface, tri: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """A 3D direction projected into the plane of each anchor's triangle (unit)."""
    nf = ref.N[tri]
    return _unit(direction - np.einsum("ij,ij->i", direction, nf)[:, None] * nf)


def trace(ref: RefSurface, tri: np.ndarray, bary: np.ndarray, direction: np.ndarray, length: np.ndarray,
          nbr: np.ndarray | None = None, max_passes: int = 100_000) -> Trace:
    """Trace each ray for `length` along the surface. `nbr` replaces the adjacency (same shape as `ref.nbr`; -1 where
    an edge must act as a barrier, e.g. a symmetry seam)."""
    nbr_table = ref.nbr if nbr is None else nbr
    n = len(tri)
    tri = np.array(tri, dtype=_I)
    bary = np.array(bary, dtype=np.float64)
    d = np.array(direction, dtype=np.float64)
    rem = np.array(length, dtype=np.float64)
    flags = np.zeros(n, dtype=np.uint8)
    crossings = np.zeros(n, dtype=np.int32)
    streak = np.zeros(n, dtype=np.int16)
    scale = max(ref.mean_edge, 1e-300)
    tiny = 1e-14 * scale
    act = np.flatnonzero(rem > tiny)
    passes = 0
    while len(act):
        if passes >= max_passes:
            flags[act] |= FLAG_MAXITER
            break
        passes += 1
        t = tri[act]
        b = bary[act]
        dd = d[act]
        L = rem[act]
        m = len(act)
        rows = np.arange(m)
        db = np.einsum("nkj,nj->nk", ref.G[t], dd)             # barycentric velocity per unit length
        leaving = db < -1e-13 * ref.Gn[t]
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(leaving, b / -db, np.inf)
        k = np.argmin(s, axis=1)
        smin = s[rows, k]
        stay = smin >= L

        if np.any(stay):
            i_st = act[stay]
            nb = np.maximum(b[stay] + db[stay] * L[stay, None], 0.0)
            bary[i_st] = nb / nb.sum(axis=1, keepdims=True)
            rem[i_st] = 0.0

        ex = ~stay
        if not np.any(ex):
            break
        i_ex = act[ex]
        kk = k[ex]
        tt = t[ex]
        ss = smin[ex]
        me = len(i_ex)
        rex = np.arange(me)
        nb = np.maximum(b[ex] + db[ex] * ss[:, None], 0.0)
        nb[rex, kk] = 0.0
        nb /= nb.sum(axis=1, keepdims=True)
        rem_ex = L[ex] - ss
        nt_ = nbr_table[tt, kk]
        wall = nt_ < 0
        bary[i_ex] = nb
        rem[i_ex] = rem_ex
        if np.any(wall):
            flags[i_ex[wall]] |= FLAG_BOUNDARY
        go = ~wall
        i_go = i_ex[go]
        if len(i_go):
            tg, kg, ng = tt[go], kk[go], nt_[go]
            ko = ref.nbr_k[tg, kg]
            fl = ref.nbr_flip[tg, kg]
            rg = np.arange(len(i_go))
            nbg = nb[go]
            w_start = nbg[rg, (kg + 1) % 3]     # weight of the edge's start corner (k+1) in the old triangle
            w_end = nbg[rg, (kg + 2) % 3]
            newb = np.zeros((len(i_go), 3))
            # a consistently wound neighbour runs the edge backwards: its corner ko+1 is our end corner
            newb[rg, (ko + 1) % 3] = np.where(fl, w_start, w_end)
            newb[rg, (ko + 2) % 3] = np.where(fl, w_end, w_start)
            ddg = dd[ex][go]
            e_dir = ref.E[tg, kg]
            alpha = np.einsum("ij,ij->i", ddg, e_dir)
            beta = np.maximum(-np.einsum("ij,ij->i", ddg, ref.Pin[tg, kg]), 0.0)
            nd = alpha[:, None] * e_dir + beta[:, None] * ref.Pin[ng, ko]
            nd = _unit(nd)
            tri[i_go] = ng
            bary[i_go] = newb
            d[i_go] = nd
            crossings[i_go] += 1
            zero = ss[go] <= tiny
            streak[i_go] = np.where(zero, streak[i_go] + 1, 0)
            dead = (streak[i_go] > 64) | ref.degenerate[ng]
            if np.any(dead):
                flags[i_go[dead]] |= FLAG_STUCK
            near_vertex = newb.max(axis=1) > 1.0 - 1e-9
            if np.any(near_vertex):
                flags[i_go[near_vertex]] |= FLAG_VERTEX
            keep = ~dead & (rem[i_go] > tiny)
            done = ~dead & ~keep
            rem[i_go[done]] = 0.0
            act = i_go[keep]
        else:
            act = i_go
    return Trace(tri, bary, d, rem, flags, crossings, passes)
