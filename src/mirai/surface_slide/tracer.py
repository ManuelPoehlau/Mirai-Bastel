"""Straightest geodesics on a `SlideReference`, traced for many points at once (one triangle crossing per pass).

Port of the prototype `experiments/surface_slide/geodesic.py` (report §4, §14.5). A ray is `(triangle, barycentric
position, unit 3D direction in the triangle's plane, remaining length)`. Inside a triangle it moves straight; at an
edge the direction is *unfolded* into the next triangle (its components along the edge and perpendicular to it are
kept, the perpendicular now pointing into the neighbour): the straight line of the two triangles laid flat (Polthier &
Schmies 1998). The anchor crosses the edge by relabelling the two shared corners, so it is exact on the surface:
nothing is ever projected.

A start exactly on a vertex has no single triangle: the direction is given in the vertex tangent plane (normal `VN`),
the incident triangle whose corner wedge contains it (seen along the normal) takes the ray, and the direction is lifted
onto that triangle along the normal.

Differences from the prototype: the edge a ray stops at is named by its code (`FLAG_BOUNDARY`, `FLAG_BARRIER`,
`FLAG_CAPTURE` instead of one boundary flag) and returned (`Trace.edge`); `back_off` moves a barrier stop off the
barrier edge (E3). A blocked boundary start keeps the prototype rule here; the along-boundary motion of boundary
vertices is the chain walker's (`curves.EdgeChain`, E5).
"""

from __future__ import annotations

from dataclasses import dataclass

from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from .reference import BARRIER_EDGE, CAPTURE_EDGE, SlideReference, unit

_I = np.intp

FLAG_BOUNDARY = 1    #: stopped at a mesh boundary edge with length left
FLAG_STUCK = 2       #: no progress (degenerate triangles, a vertex the path could not leave, a degenerate chase)
FLAG_BLOCKED = 4     #: a start on a wall vertex pointing off the surface: not moved
FLAG_MAXITER = 8     #: crossing limit reached
FLAG_BARRIER = 16    #: stopped at a barrier edge (seam, hidden face); backed off it by the slide
FLAG_CAPTURE = 32    #: stopped at the border of a region-limited capture: the capture must grow (Phase 2)
FLAG_CHAIN_END = 64  #: a chain walk (seam, open boundary) reached the end or a branch of its chain
FLAG_LAGGING = 128   #: the pursuit has not caught up with the target yet

WALL_FLAGS = FLAG_BOUNDARY | FLAG_BARRIER | FLAG_CAPTURE

#: How far towards the opposite corner a barrier stop is pulled back: the stop lies at this fraction of the way from
#: that corner to the hit point (precedent: `topology.vertex_slide.SYMMETRIC_MAX_AMOUNT`, the Vertex Slide stops at
#: 98 % of an edge towards the seam). Strictly inside the triangle, so off the barrier edge and on the surface.
BARRIER_MAX_AMOUNT = 0.98


@dataclass(frozen=True)
class Trace:
    tri: object        # (n,) end triangle
    bary: object       # (n, 3) end barycentrics
    direction: object  # (n, 3) unit direction at the end point (in the end triangle's plane)
    remaining: object  # (n,) length not travelled (wall / stuck)
    flags: object      # (n,) uint16
    edge: object       # (n,) the wall edge k of `tri` the ray stopped at, -1 otherwise
    crossings: object  # (n,) edges crossed
    passes: int = 0    # passes of the batch loop (= the longest path in crossings)


def launch_from_vertices(ref: SlideReference, rows, t_dir):
    """Rays at vertices `rows` in the unit tangent directions `t_dir` -> `(tri, bary, direction, flags)`."""
    v = np.asarray(rows, dtype=_I)
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
    # lift along the vertex normal (keeps the tangent-plane direction); a triangle seen edge-on or from behind gets
    # the plain projection instead
    d = np.where(lift[:, None], t - (t_nf / np.where(lift, denom, 1.0))[:, None] * nv, t - t_nf[:, None] * nf)
    d = unit(d)
    k1 = (c + 1) % 3
    k2 = (c + 2) % 3
    in1 = np.einsum("ij,ij->i", d, ref.Pin[f, k1])
    in2 = np.einsum("ij,ij->i", d, ref.Pin[f, k2])
    score = np.minimum(in1, in2)
    score = np.where(ref.degenerate[f] | ~np.isfinite(score), -np.inf, score)
    order = np.lexsort((score, rep))
    last = order[np.r_[rep[order][1:] != rep[order][:-1], True]] if total else order
    tri = f[last]
    corner = c[last]
    best = score[last]
    dd = d[last]
    # a direction just outside every wedge (lifting is not exactly consistent between neighbours): walk the edge
    for kk, comp in ((k1[last], in1[last]), (k2[last], in2[last])):
        bad = comp < 0.0
        if np.any(bad):
            dd[bad] -= comp[bad, None] * ref.Pin[tri[bad], kk[bad]]
    dd = unit(dd)
    bary = np.zeros((n, 3))
    bary[np.arange(n), corner] = 1.0
    flags = np.zeros(n, dtype=np.uint16)
    blocked = ref.v_wall[v] & (best < -1e-9)
    flags[blocked] |= FLAG_BLOCKED
    flags[blocked & ref.v_capture[v]] |= FLAG_CAPTURE
    return tri, bary, dd, flags


def launch_from_anchors(ref: SlideReference, tri, direction):
    """A 3D direction projected into the plane of each anchor's triangle (unit)."""
    nf = ref.N[tri]
    return unit(direction - np.einsum("ij,ij->i", direction, nf)[:, None] * nf)


def trace(ref: SlideReference, tri, bary, direction, length, max_passes: int = 100_000) -> Trace:
    """Trace each ray for `length` along the surface; a ray stops at any edge whose `nbr` is negative."""
    nbr_table = ref.nbr
    n = len(tri)
    tri = np.array(tri, dtype=_I)
    bary = np.array(bary, dtype=np.float64)
    d = np.array(direction, dtype=np.float64)
    rem = np.array(length, dtype=np.float64)
    flags = np.zeros(n, dtype=np.uint16)
    edge = np.full(n, -1, dtype=_I)
    crossings = np.zeros(n, dtype=np.int32)
    streak = np.zeros(n, dtype=np.int16)
    tiny = 1e-14 * max(ref.h, 1e-300)
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
        rows = np.arange(len(act))
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
        rex = np.arange(len(i_ex))
        nb = np.maximum(b[ex] + db[ex] * ss[:, None], 0.0)
        nb[rex, kk] = 0.0
        nb /= nb.sum(axis=1, keepdims=True)
        nt_ = nbr_table[tt, kk]
        wall = nt_ < 0
        bary[i_ex] = nb
        rem[i_ex] = L[ex] - ss
        if np.any(wall):
            iw = i_ex[wall]
            code = nt_[wall]
            flags[iw] |= np.where(code == BARRIER_EDGE, FLAG_BARRIER,
                                  np.where(code == CAPTURE_EDGE, FLAG_CAPTURE, FLAG_BOUNDARY)).astype(np.uint16)
            edge[iw] = kk[wall]
        go = ~wall
        i_go = i_ex[go]
        if not len(i_go):
            act = i_go
            continue
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
        nd = unit(alpha[:, None] * e_dir + beta[:, None] * ref.Pin[ng, ko])
        tri[i_go] = ng
        bary[i_go] = newb
        d[i_go] = nd
        crossings[i_go] += 1
        zero = ss[go] <= tiny
        streak[i_go] = np.where(zero, streak[i_go] + 1, 0)
        dead = (streak[i_go] > 64) | ref.degenerate[ng]
        if np.any(dead):
            flags[i_go[dead]] |= FLAG_STUCK
        keep = ~dead & (rem[i_go] > tiny)
        rem[i_go[~dead & ~keep]] = 0.0
        act = i_go[keep]
    return Trace(tri, bary, d, rem, flags, edge, crossings, passes)


def back_off(bary, edge, amount: float = BARRIER_MAX_AMOUNT):
    """Barycentrics `bary` (on edge `edge` of their triangle) pulled towards the opposite corner: the point at `amount`
    of the way from that corner to the hit point. A convex combination, so exactly on the triangle, and the opposite
    corner's coordinate is `1 - amount` > 0: strictly off the edge (no `AMBIGUOUS` partner on the seam)."""
    out = np.array(bary, dtype=np.float64) * amount
    out[np.arange(len(out)), edge] += 1.0 - amount
    return out
