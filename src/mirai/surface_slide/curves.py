"""`EdgeChain`: sliding along a chain of reference edges, the 1D counterpart of the geodesic trace.

The prototype's seam walker (`experiments/surface_slide/seam.py`) generalised to any chain of edges: the declared
symmetry seam, and open boundary loops (eye and mouth openings, E5: boundary vertices slide along the boundary).

A vertex on the chain walks the chain polyline by arc length. Every point of it is on a reference edge, so it is
exactly on the surface; the anchor's third barycentric coordinate is exactly 0, so a point between two seam vertices
whose plane coordinate is exactly on the plane has that coordinate exactly on the plane too.

A walk is described by the vertex it starts at, the *arm* (the chain neighbour it leaves by) and the arc length. The
arm is the chain edge the tangent points along best (positive component only); the length is the tangent's component
along that first edge (the prototype's rule). At every further vertex the walk takes the chain edge it did not come
by; it stops with `FLAG_CHAIN_END` where the chain ends or branches, and where a closed loop comes back to its start.
"""

from __future__ import annotations

from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from .reference import BOUNDARY_EDGE, SlideReference
from .tracer import FLAG_CHAIN_END, FLAG_STUCK

_I = np.intp


class EdgeChain:
    """The chain of `edges` (`(k, 2)` reference rows, either order) on `ref` (module docstring)."""

    def __init__(self, ref: SlideReference, edges) -> None:
        edges = np.asarray(edges, dtype=_I).reshape(-1, 2)
        tri, k = ref.edge_slots(edges)
        if np.any(tri < 0):
            raise ValueError("a chain edge is not an edge of the reference")
        self.ref = ref
        self.nbrs: dict[int, list[int]] = {}
        self._slot: dict[tuple[int, int], tuple[int, int, int]] = {}
        for (a, b), t, kk in zip(edges.tolist(), tri.tolist(), k.tolist()):
            if a == b or (min(a, b), max(a, b)) in self._slot:
                continue
            self.nbrs.setdefault(a, []).append(b)
            self.nbrs.setdefault(b, []).append(a)
            self._slot[(min(a, b), max(a, b))] = (t, (kk + 1) % 3, (kk + 2) % 3)
        self.n_edges = len(self._slot)
        mask = np.zeros(ref.nv, dtype=bool)
        mask[list(self.nbrs)] = True
        self.on_chain = mask
        self.on_chain.flags.writeable = False

    @classmethod
    def boundary(cls, ref: SlideReference) -> "EdgeChain":
        """The chain of every open boundary edge of `ref` (not barriers, not capture borders)."""
        return cls(ref, ref.edges_with_code(BOUNDARY_EDGE))

    def arm(self, row: int, tangent) -> tuple[int, float]:
        """`(neighbour, length)`: the chain edge at `row` the tangent points along best and the tangent's component
        along it; `(-1, 0.0)` when it points along none (or `row` is not on the chain)."""
        V = self.ref.V
        best, best_dot = -1, 0.0
        for o in self.nbrs.get(int(row), ()):
            e = V[o] - V[row]
            d = float(tangent @ e) / float(np.linalg.norm(e))
            if d > best_dot:
                best, best_dot = o, d
        return best, best_dot

    def walk(self, row: int, neighbour: int, length: float):
        """Walk from `row` along the chain, leaving by `neighbour`, for `length` ->
        `(tri, bary (3,), travelled, flags)`. `neighbour < 0` or `length <= 0` stays at `row`."""
        ref, V = self.ref, self.ref.V
        row = int(row)
        if neighbour < 0 or not length > 0.0:
            t, b = ref.vertex_anchor(np.array([row]))
            return int(t[0]), b[0], 0.0, 0
        remaining = float(length)
        travelled = 0.0
        prev, cur = row, int(neighbour)
        for _ in range(self.n_edges + 1):
            seg = float(np.linalg.norm(V[cur] - V[prev]))
            if remaining <= seg and seg > 0.0:
                f = remaining / seg
                t, ka, kb = self._slot[(min(prev, cur), max(prev, cur))]
                bary = np.zeros(3)
                ia = ka if ref.T[t, ka] == prev else kb
                ib = kb if ia == ka else ka
                bary[ia], bary[ib] = 1.0 - f, f
                return t, bary, travelled + remaining, 0
            remaining -= seg
            travelled += seg
            onward = [o for o in self.nbrs[cur] if o != prev]
            if len(onward) != 1 or cur == row:      # the chain ends, branches, or a loop came round to its start
                t, b = ref.vertex_anchor(np.array([cur]))
                return int(t[0]), b[0], travelled, FLAG_CHAIN_END
            prev, cur = cur, onward[0]
        t, b = ref.vertex_anchor(np.array([cur]))
        return int(t[0]), b[0], travelled, FLAG_STUCK
