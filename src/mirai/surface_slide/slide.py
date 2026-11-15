"""`SurfaceSlide`: the anchored geodesic slide with speed-limited pursuit (`geodesic_pursuit[transport]`, E9).

Port of the prototype `GeodesicPursuit("transport")` (`experiments/surface_slide/algorithms.py`, report §4, §14.5) with
the audit's changes (§3.2, §3.7, E3, E5):

- **Transport** (`direct_frames`): the pivot's drag is carried into each vertex's tangent plane by the *direct*
  minimal rotation pivot normal -> vertex normal; continuous in the normal, no tree, no Python loop. Where
  `n_pivot . n_i < -0.5` (the rotation axis is ill-defined near antipodal normals) the rotation is composed along the
  shortest triangle-edge path instead (tree fallback, only for those vertices). `tree_frames` is the tree transport
  for comparison; any `(n, 3, 3)` frames can be injected (the oracle injects the prototype's).
- **Target**: every update traces the whole weighted, transported drag again from the start anchor (absolute: a
  function of the drag alone). Barrier stops are pulled back off the barrier edge (`tracer.back_off`, E3). Rows on an
  `EdgeChain` (seam, open boundary, E5) walk their chain instead of the surface.
- **Pursuit**: a vertex may move at most `(1 + gain) x` the change of its own tangent per update. It takes its target
  when the target is within that budget *and* close over the surface: its triangle shares a corner with the current
  one, or a chase of the chord length lands next to it (snap guard, audit §3.7 item 2: a target behind a thin
  feature is never adopted through the feature). Otherwise it walks the budget along the surface towards the target
  and is `LAGGING`. A chase whose straight-line gap is along the current normal walks against the target's own
  arrival direction (audit §3.7 item 3); if that is degenerate too, it stays (`STUCK`).
- **Exactness**: a tangent of exactly zero restores the start state bit for bit; every position is the flat
  evaluation of an anchor on the reference; weight-0 rows never move.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from .curves import EdgeChain
from .reference import SlideReference, unit
from .tracer import (BARRIER_MAX_AMOUNT, FLAG_BARRIER, FLAG_BLOCKED, FLAG_LAGGING, FLAG_STUCK, back_off,
                     launch_from_anchors, launch_from_vertices, trace)

_I = np.intp

#: Below `n_pivot . n_i` of this the direct rotation is replaced by the tree composition (audit §3.2).
ANTIPODAL_DOT = -0.5


def _tangent(vec, normal):
    return vec - np.einsum("ij,ij->i", vec, normal)[:, None] * normal


def _shares_corner(ta, tb):
    """Per row: do the triangles with corners `ta (n, 3)` and `tb (n, 3)` share a corner?"""
    return np.any(ta[:, :, None] == tb[:, None, :], axis=(1, 2))


def minimal_rotations(a, b):
    """`R (n, 3, 3)` with `R[i] @ a[i] == b[i]`: the rotation of smallest angle between unit vectors (undefined for
    `b == -a`; callers keep away from it)."""
    a = np.broadcast_to(np.asarray(a, dtype=np.float64), np.shape(b))
    v = np.cross(a, b)
    c = np.einsum("ij,ij->i", a, b)
    vx = np.zeros((len(v), 3, 3))
    vx[:, 0, 1], vx[:, 0, 2], vx[:, 1, 0] = -v[:, 2], v[:, 1], v[:, 2]
    vx[:, 1, 2], vx[:, 2, 0], vx[:, 2, 1] = -v[:, 0], -v[:, 1], v[:, 0]
    scale = 1.0 / np.where(1.0 + c > 0.0, 1.0 + c, np.inf)
    return np.eye(3)[None] + vx + np.einsum("nij,njk->nik", vx, vx) * scale[:, None, None]


def _shortest_path_tree(ref: SlideReference, source: int, targets, within=None):
    """Dijkstra over the triangle edges from `source` until every reachable target is settled ->
    `(settle order, parent)`. `within`: rows; only triangles with a corner among them (or the source) are used."""
    T = ref.T
    if within is not None:
        keep = np.zeros(ref.nv, dtype=bool)
        keep[within] = True
        keep[source] = True
        T = T[keep[T].any(axis=1)]
    a = np.r_[T[:, 0], T[:, 1], T[:, 2]]
    b = np.r_[T[:, 1], T[:, 2], T[:, 0]]
    src, dst = np.r_[a, b], np.r_[b, a]
    order = np.argsort(src, kind="stable")
    ptr = np.r_[0, np.cumsum(np.bincount(src, minlength=ref.nv))].tolist()
    nbr = dst[order].tolist()
    length = np.linalg.norm(ref.V[src[order]] - ref.V[dst[order]], axis=1).tolist()
    left = set(int(t) for t in targets)
    dist = {int(source): 0.0}
    parent = {int(source): int(source)}
    heap = [(0.0, int(source))]
    done: set[int] = set()
    settled: list[int] = []
    while heap and left:
        d, v = heapq.heappop(heap)
        if v in done:
            continue
        done.add(v)
        settled.append(v)
        left.discard(v)
        for i in range(ptr[v], ptr[v + 1]):
            o = nbr[i]
            if o in done:
                continue
            nd = d + length[i]
            if nd < dist.get(o, np.inf):
                dist[o] = nd
                parent[o] = v
                heapq.heappush(heap, (nd, o))
    return settled, parent


def _compose(VN, parent: dict, chain: list, base):
    """Rotations along tree paths, batched by depth: for every vertex x of `chain` (parents before children)
    `R[x] = rot(VN[parent x] -> VN[x]) @ R[parent x]`, where a parent outside `chain` contributes `base(parents)`."""
    if not chain:
        return np.zeros((0, 3, 3))
    pos = {x: i for i, x in enumerate(chain)}
    par = np.array([parent[x] for x in chain], dtype=_I)
    L = minimal_rotations(VN[par], VN[np.array(chain, dtype=_I)])
    par_pos = np.array([pos.get(p, -1) for p in par.tolist()], dtype=_I)
    depth = np.zeros(len(chain), dtype=_I)
    for i, j in enumerate(par_pos.tolist()):
        if j >= 0:
            depth[i] = depth[j] + 1
    R = np.empty_like(L)
    top = depth == 0
    R[top] = np.einsum("nij,njk->nik", L[top], base(par[top]))
    for k in range(1, int(depth.max()) + 1):
        lev = depth == k
        R[lev] = np.einsum("nij,njk->nik", L[lev], R[par_pos[lev]])
    return R


def tree_frames(ref: SlideReference, pivot_row: int, rows):
    """The tree transport (the prototype's rule, over triangle edges here): the product of minimal rotations
    normal -> normal along the shortest-path tree from the pivot. A row the pivot cannot reach gets the direct
    rotation. For comparison and fallback; it jumps between neighbours on different branches (audit §3.2)."""
    rows = np.asarray(rows, dtype=_I)
    VN = ref.VN
    settled, parent = _shortest_path_tree(ref, pivot_row, rows.tolist())
    chain = [v for v in settled if v != pivot_row]
    R = _compose(VN, parent, chain, lambda par: np.broadcast_to(np.eye(3), (len(par), 3, 3)))
    at = {v: i for i, v in enumerate(chain)}
    out = minimal_rotations(VN[pivot_row], VN[rows])
    for i, v in enumerate(rows.tolist()):
        if v in at:
            out[i] = R[at[v]]
    return out


def direct_frames(ref: SlideReference, pivot_row: int, rows, *, antipodal_dot: float = ANTIPODAL_DOT):
    """`R (n, 3, 3)`: `R[i] @ t` carries a tangent vector `t` of the pivot into the tangent plane of `rows[i]` by the
    direct minimal rotation of the normals; tree composition where `n_pivot . n_i < antipodal_dot` (module docstring),
    from the last vertex of the path that still has a direct rotation. A row the pivot cannot reach over the surface
    whose normal is near-antipodal keeps the identity (another shell)."""
    rows = np.asarray(rows, dtype=_I)
    VN = ref.VN
    a = VN[pivot_row]
    dot = VN @ a
    R = minimal_rotations(a, VN[rows])
    bad = dot[rows] < antipodal_dot
    if not np.any(bad):
        return R
    R[bad] = np.eye(3)
    targets = rows[bad].tolist()
    settled, parent = _shortest_path_tree(ref, pivot_row, targets, within=rows)
    if any(t not in parent for t in targets):          # a path leaves the rows: search the whole surface
        settled, parent = _shortest_path_tree(ref, pivot_row, targets)
    need: set[int] = set()
    for x in targets:                                  # each bad row and its bad ancestors
        while x in parent and x not in need and dot[x] < antipodal_dot:
            need.add(x)
            x = parent[x]
    chain = [v for v in settled if v in need]
    composed = _compose(VN, parent, chain, lambda par: minimal_rotations(a, VN[par]))
    at = {v: i for i, v in enumerate(chain)}
    for i in np.flatnonzero(bad).tolist():
        v = int(rows[i])
        if v in at:
            R[i] = composed[at[v]]
    return R


def frame_jumps(ref: SlideReference, pivot_row: int, rows, frames, edges=None):
    """The transport continuity metric of the audit (§3.2): for every edge between two of `rows`, the angle in degrees
    between the pivot's first frame vector carried to one end and carried to the other (then moved across the edge by
    the minimal rotation of the two normals). 0 for a perfectly continuous transport. `edges`: `(k, 2)` rows to
    measure on (the audit used the polygon edges); default every triangle edge."""
    rows = np.asarray(rows, dtype=_I)
    VN = ref.VN
    n0 = VN[pivot_row]
    e1 = unit(np.cross(n0, np.eye(3)[int(np.argmin(np.abs(n0)))])[None])[0]
    t = unit(_tangent(np.einsum("nij,j->ni", frames, e1), VN[rows]))
    row_of = np.full(ref.nv, -1, dtype=_I)
    row_of[rows] = np.arange(len(rows))
    if edges is None:
        a = np.r_[ref.T[:, 0], ref.T[:, 1], ref.T[:, 2]]
        b = np.r_[ref.T[:, 1], ref.T[:, 2], ref.T[:, 0]]
        e = np.unique(np.stack([np.minimum(a, b), np.maximum(a, b)], axis=1), axis=0)
    else:
        e = np.asarray(edges, dtype=_I).reshape(-1, 2)
    e = e[(row_of[e[:, 0]] >= 0) & (row_of[e[:, 1]] >= 0)]
    if not len(e):
        return np.zeros(0)
    ia, ib = row_of[e[:, 0]], row_of[e[:, 1]]
    moved = np.einsum("nij,nj->ni", minimal_rotations(VN[e[:, 0]], VN[e[:, 1]]), t[ia])
    return np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", unit(moved), t[ib]), -1.0, 1.0)))


@dataclass(frozen=True)
class SlideFrame:
    positions: object   # (n, 3) read-only, row i belongs to `SurfaceSlide.rows[i]`
    flags: object       # (n,) uint16, `tracer.FLAG_*`; 0 = clean
    lagging: int        # rows still chasing their target


class SurfaceSlide:
    """One slide gesture on `reference` (module docstring).

    `rows`: the reference rows that move (distinct), `weights` in [0, 1] (default 1), `pivot`: the index *into rows* of
    the vertex the drag is meant for. `frames`: `(n, 3, 3)` transport, default `direct_frames`. `chains`: `EdgeChain`s;
    a row on one walks the first chain listing it (pass the seam before the boundary). `gain`: the pursuit's catch-up
    rate. `barrier_amount`: `tracer.back_off`."""

    def __init__(self, reference: SlideReference, rows, weights=None, pivot: int = 0, *, frames=None,
                 chains: tuple[EdgeChain, ...] | list[EdgeChain] = (), gain: float = 1.0,
                 barrier_amount: float = BARRIER_MAX_AMOUNT) -> None:
        ref = reference
        rows = np.array(rows, dtype=_I).reshape(-1)
        n = len(rows)
        if n == 0:
            raise ValueError("a slide needs at least one row")
        if len(np.unique(rows)) != n:
            raise ValueError("rows must be distinct")
        if not 0 <= pivot < n:
            raise ValueError("pivot is an index into rows")
        w = np.ones(n) if weights is None else np.array(weights, dtype=np.float64).reshape(-1)
        if len(w) != n or not np.all(np.isfinite(w)) or np.any(w < 0.0) or np.any(w > 1.0):
            raise ValueError("weights must be n values in [0, 1]")
        if gain < 0.0 or not 0.0 < barrier_amount < 1.0:
            raise ValueError("gain must be >= 0 and barrier_amount in (0, 1)")
        self.ref = ref
        self.rows = rows
        self.weights = w
        self.pivot = int(pivot)
        self.gain = float(gain)
        self.barrier_amount = float(barrier_amount)
        for name in ("rows", "weights"):
            getattr(self, name).flags.writeable = False

        self._tri0, self._bary0 = ref.vertex_anchor(rows)
        self._p0 = ref.V[rows].copy()
        self._n0 = ref.VN[rows].copy()
        R = direct_frames(ref, int(rows[pivot]), rows) if frames is None else np.array(frames, dtype=np.float64)
        if R.shape != (n, 3, 3):
            raise ValueError("frames must be (n, 3, 3)")
        self.frames = R
        self.frames.flags.writeable = False
        npv = self._n0[self.pivot]
        e1 = unit(np.cross(npv, np.eye(3)[int(np.argmin(np.abs(npv)))])[None])[0]
        self._e1, self._e2 = e1, np.cross(npv, e1)

        chain_of = np.full(n, -1, dtype=_I)
        self._chains = list(chains)
        for c, chain in enumerate(self._chains):
            if chain.ref is not ref:
                raise ValueError("a chain belongs to another reference")
            chain_of[(chain_of < 0) & chain.on_chain[rows]] = c
        self._chain_of = chain_of
        self._chain_rows = np.flatnonzero(chain_of >= 0)
        self._surf = np.flatnonzero(chain_of < 0)
        self._reset()

    # -- public ------------------------------------------------------------------------------------------------------

    @property
    def pivot_frame(self):
        """`(normal, e1, e2)` of the pivot's start tangent plane; `tangent_of` measures in `(e1, e2)`."""
        return self._n0[self.pivot].copy(), self._e1.copy(), self._e2.copy()

    def tangent_of(self, delta) -> tuple[float, float]:
        """The drag projected into the pivot's start tangent plane, in the pivot frame (linear in `delta`)."""
        tp = self._pivot_tangent(delta)
        return float(tp @ self._e1), float(tp @ self._e2)

    def start_positions(self):
        return self._p0.copy()

    @property
    def lagging_mask(self):
        return self._lagging.copy()

    def anchors(self):
        """The current anchors `(tri, bary)` (copies); `positions == reference.point(*anchors())`."""
        return self._tri.copy(), self._bary.copy()

    def targets(self):
        """The anchors `(tri, bary)` the rows pursue (copies); equal to `anchors()` for every row not lagging."""
        return self._tgt_tri.copy(), self._tgt_bary.copy()

    def update(self, delta) -> SlideFrame:
        """`delta`: the drag since the press as a world-space 3-vector; only its component in the pivot's start
        tangent plane counts (the M1 mapping produces exactly such a vector, audit §3.4)."""
        tp = self._pivot_tangent(delta)
        t = _tangent(np.einsum("nij,j->ni", self.frames, tp), self._n0) * self.weights[:, None]
        if not np.any(t):
            self._reset()
            return self._frame(np.zeros(len(self.rows), dtype=np.uint16))
        self._set_target(t)
        budget = (1.0 + self.gain) * np.linalg.norm(t - self._t, axis=1) + 1e-12 * self.ref.h
        self._t = t
        return self._chase(budget)

    def settle(self, max_step: float) -> SlideFrame:
        """Let lagging rows close in on their targets by up to `max_step` each without a change of the drag (for the
        host while the pointer rests). Does nothing when nothing lags."""
        return self._chase(np.where(self._lagging, float(max_step), 0.0))

    # -- internals ---------------------------------------------------------------------------------------------------

    def _pivot_tangent(self, delta):
        delta = np.asarray(delta, dtype=np.float64).reshape(3)
        npv = self._n0[self.pivot]
        return delta - (delta @ npv) * npv

    def _reset(self) -> None:
        n = len(self.rows)
        self._tri, self._bary, self._pos = self._tri0.copy(), self._bary0.copy(), self._p0.copy()
        self._at_start = np.ones(n, dtype=bool)
        self._t = np.zeros((n, 3))
        self._tgt_tri, self._tgt_bary = self._tri0.copy(), self._bary0.copy()
        self._tgt_flags = np.zeros(n, dtype=np.uint16)
        self._tgt_dir = np.zeros((n, 3))
        self._lagging = np.zeros(n, dtype=bool)
        self._arm = np.full(n, -1, dtype=_I)           # chain rows: the arm the current point is on
        self._s = np.zeros(n)                           # chain rows: arc length from the start vertex
        self._tgt_arm = np.full(n, -1, dtype=_I)
        self._tgt_s = np.zeros(n)

    def _frame(self, flags) -> SlideFrame:
        pos = self._pos.copy()
        pos.flags.writeable = False
        return SlideFrame(pos, flags, int(self._lagging.sum()))

    def _launch(self, idx, tri, bary, tangent, at_vertex):
        """Rays for the tangent vectors `tangent` (length = distance) from the anchors of rows `idx`."""
        ref = self.ref
        length = np.linalg.norm(tangent, axis=1)
        unit_t = tangent / np.where(length > 0.0, length, 1.0)[:, None]
        tri = np.array(tri, dtype=_I)
        bary = np.array(bary, dtype=np.float64)
        d = np.zeros((len(idx), 3))
        flags = np.zeros(len(idx), dtype=np.uint16)
        moving = length > 0.0
        vs = at_vertex & moving
        if np.any(vs):
            tri[vs], bary[vs], d[vs], flags[vs] = launch_from_vertices(ref, self.rows[idx[vs]], unit_t[vs])
        rest = ~at_vertex & moving
        if np.any(rest):
            d[rest] = launch_from_anchors(ref, tri[rest], unit_t[rest])
        length = np.where((flags & FLAG_BLOCKED) > 0, 0.0, length)
        tr = trace(ref, tri, bary, d, length)
        out_bary = tr.bary
        hit = (tr.flags & FLAG_BARRIER) > 0
        if np.any(hit):
            out_bary = out_bary.copy()
            out_bary[hit] = back_off(out_bary[hit], tr.edge[hit], self.barrier_amount)
        return tr.tri, out_bary, tr.direction, flags | tr.flags

    def _set_target(self, t) -> None:
        s = self._surf
        if len(s):
            tri, bary, d, flags = self._launch(s, self._tri0[s], self._bary0[s], t[s], np.ones(len(s), dtype=bool))
            self._tgt_tri[s], self._tgt_bary[s], self._tgt_dir[s], self._tgt_flags[s] = tri, bary, d, flags
        for i in self._chain_rows.tolist():
            chain = self._chains[self._chain_of[i]]
            row = int(self.rows[i])
            arm, length = chain.arm(row, t[i])
            tri, bary, travelled, flags = chain.walk(row, arm, length)
            self._tgt_arm[i], self._tgt_s[i] = arm, travelled
            self._tgt_tri[i], self._tgt_bary[i], self._tgt_flags[i] = tri, bary, flags

    def _chase(self, budget) -> SlideFrame:
        ref = self.ref
        n = len(self.rows)
        flags = self._tgt_flags.copy()
        tri, bary = self._tri.copy(), self._bary.copy()
        lagging = np.zeros(n, dtype=bool)

        s = self._surf
        if len(s):
            tgt_tri, tgt_bary = self._tgt_tri[s], self._tgt_bary[s]
            gap_vec = ref.point(tgt_tri, tgt_bary) - self._pos[s]
            gap = np.linalg.norm(gap_vec, axis=1)
            within = gap <= budget[s]
            adopt = within & _shares_corner(ref.T[self._tri[s]], ref.T[tgt_tri])
            tri[s[adopt]], bary[s[adopt]] = tgt_tri[adopt], tgt_bary[adopt]
            need = np.flatnonzero(~adopt)
            if len(need):
                idx = s[need]
                at_vertex = self._at_start[idx]
                normal = np.where(at_vertex[:, None], self._n0[idx], ref.N[self._tri[idx]])
                g_t = _tangent(gap_vec[need], normal)
                g_len = np.linalg.norm(g_t, axis=1)
                flat_gap = g_len <= 1e-9 * gap[need]
                if np.any(flat_gap):
                    # the target is straight above / below: the surface folded back in between; go against the
                    # target's arrival direction (audit §3.7 item 3)
                    alt = _tangent(-self._tgt_dir[idx[flat_gap]], normal[flat_gap])
                    g_t[flat_gap] = alt
                    dead = np.linalg.norm(alt, axis=1) <= 1e-9
                    flags[idx[flat_gap][dead]] |= FLAG_STUCK
                    g_t[np.flatnonzero(flat_gap)[dead]] = 0.0
                step = unit(g_t) * np.minimum(budget[idx], gap[need])[:, None]
                c_tri, c_bary, _, c_flags = self._launch(idx, self._tri[idx], self._bary[idx], step, at_vertex)
                flags[idx] |= c_flags
                # a chase over the whole chord that ends next to the target: the target is close over the surface
                caught = within[need] & _shares_corner(ref.T[c_tri], ref.T[tgt_tri[need]])
                tri[idx] = np.where(caught, tgt_tri[need], c_tri)
                bary[idx] = np.where(caught[:, None], tgt_bary[need], c_bary)
                lagging[idx] = ~caught

        for i in self._chain_rows.tolist():
            lag = self._chase_chain(i, float(budget[i]))
            if lag is not None:
                tri[i], bary[i], f = lag
                flags[i] |= f
                lagging[i] = True
            else:
                tri[i], bary[i] = self._tgt_tri[i], self._tgt_bary[i]

        self._tri, self._bary = tri, bary
        self._pos = ref.point(tri, bary)
        self._at_start &= np.all(bary == self._bary0, axis=1) & (tri == self._tri0)
        self._lagging = lagging
        flags[lagging] |= FLAG_LAGGING
        return self._frame(flags)

    def _chase_chain(self, i: int, budget: float):
        """One chain row's pursuit in arc length -> `None` (took its target) or `(tri, bary, flags)` (lagging)."""
        arm, cur = int(self._arm[i]), float(self._s[i])
        t_arm, tgt = int(self._tgt_arm[i]), float(self._tgt_s[i])
        if cur == 0.0:
            arm = t_arm
        if tgt == 0.0:
            t_arm = arm
        gap = abs(tgt - cur) if arm == t_arm else tgt + cur
        if gap <= budget:
            self._arm[i], self._s[i] = t_arm, tgt
            return None
        if arm == t_arm:
            cur += budget if tgt > cur else -budget
        elif cur >= budget:
            cur -= budget
        else:
            arm, cur = t_arm, budget - cur
        chain = self._chains[self._chain_of[i]]
        tri, bary, travelled, flags = chain.walk(int(self.rows[i]), arm, cur)
        self._arm[i], self._s[i] = arm, travelled
        return tri, bary, flags
