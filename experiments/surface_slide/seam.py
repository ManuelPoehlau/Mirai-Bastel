"""Slide along a curve of reference edges (the symmetry seam): the 1D counterpart of the geodesic walk.

A vertex on the mirror plane must stay on it. A geodesic launched in the plane does not: the tracer passes a vertex on
one side of it, and a seam runs through nothing but vertices. So a seam vertex walks the seam polyline itself by arc
length; every point of it is on a reference edge, hence exactly on the surface and (the seam's vertices having their
plane coordinate exactly on the plane) exactly on the plane.
"""

from __future__ import annotations

import numpy as np

from .refsurf import RefSurface

_I = np.intp


class SeamCurve:
    def __init__(self, ref: RefSurface, seam_edges: np.ndarray) -> None:
        self.ref = ref
        self.nbrs: dict[int, list[int]] = {}
        for a, b in np.asarray(seam_edges, dtype=_I).tolist():
            self.nbrs.setdefault(a, []).append(b)
            self.nbrs.setdefault(b, []).append(a)
        # one triangle (and the two corners) for every seam edge, to express a point on it as an anchor
        self.edge_tri: dict[tuple[int, int], tuple[int, int, int]] = {}
        a = np.roll(ref.T, -1, axis=1)
        b = np.roll(ref.T, -2, axis=1)
        wanted = {(min(x, y), max(x, y)) for x, ys in self.nbrs.items() for y in ys}
        for t in range(ref.nt):
            for k in range(3):
                e = (int(min(a[t, k], b[t, k])), int(max(a[t, k], b[t, k])))
                if e in wanted and e not in self.edge_tri:
                    self.edge_tri[e] = (t, (k + 1) % 3, (k + 2) % 3)

    def slide(self, vertex: int, tangent: np.ndarray) -> tuple[int, np.ndarray, np.ndarray, bool]:
        """Walk from seam vertex `vertex` along the seam by the component of `tangent` along it ->
        `(tri, bary, position, stopped_at_end)`. The first edge is the one the tangent points along best; at every
        further vertex the walk takes the seam edge that is not the one it came by."""
        V = self.ref.V
        best, best_dot = None, 0.0
        for o in self.nbrs.get(int(vertex), []):
            e = V[o] - V[vertex]
            d = float(tangent @ e) / float(np.linalg.norm(e))
            if d > best_dot:
                best, best_dot = o, d
        tri0, bary0 = self.ref.vertex_anchor(np.array([vertex]))
        if best is None:
            return int(tri0[0]), bary0[0], V[vertex].copy(), False
        remaining = best_dot
        prev, cur = int(vertex), int(best)
        while True:
            length = float(np.linalg.norm(V[cur] - V[prev]))
            if remaining <= length:
                f = remaining / length
                t, ka, kb = self.edge_tri[(min(prev, cur), max(prev, cur))]
                bary = np.zeros(3)
                ia = ka if self.ref.T[t, ka] == prev else kb
                ib = kb if ia == ka else ka
                bary[ia], bary[ib] = 1.0 - f, f
                return t, bary, (1.0 - f) * V[prev] + f * V[cur], False
            remaining -= length
            onward = [o for o in self.nbrs[cur] if o != prev]
            if len(onward) != 1:        # the seam ends or branches here
                t, bary = self.ref.vertex_anchor(np.array([cur]))
                return int(t[0]), bary[0], V[cur].copy(), True
            prev, cur = cur, onward[0]
