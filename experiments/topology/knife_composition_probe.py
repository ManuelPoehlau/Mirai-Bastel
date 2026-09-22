"""DISCOVERY PROBE — can a knife cut be composed from the public Core API?

Evidence for AD-017 §4 and WP-AP-CUT_PLAN §0. Not a tool, not wired anywhere.

K1: point-to-point path over 3 faces: vertex -> edge@0.3 -> edge@0.6 -> vertex
    using only split_edge + set_vertex_position + connect_vertices.
K3: cut through a point INSIDE a face using remove_face + add_vertex + add_face.

Run:  python experiments/topology/knife_composition_probe.py
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402


def _grid(n=4):
    m, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = m.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            m.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return m, p


def _edge(m, a, b):
    return next(e for e in m.all_edge_ids() if set(m.edge_vertices(e)) == {a, b})


def _split_at(m, a, b, t):
    v, _, _ = m.split_edge(_edge(m, a, b))
    pa, pb = m.vertex_position(a), m.vertex_position(b)
    m.set_vertex_position(v, tuple(x + (y - x) * t for x, y in zip(pa, pb)))
    return v


def _shared_face(m, a, b):
    return next(f for f in m.all_face_ids() if a in m.face_vertices(f) and b in m.face_vertices(f))


def _sizes(m):
    return dict(sorted(collections.Counter(len(m.face_vertices(f)) for f in m.all_face_ids()).items()))


def k1():
    m, p = _grid()
    pts = [p[(1, 1)], _split_at(m, p[(1, 2)], p[(2, 2)], 0.3),
           _split_at(m, p[(1, 3)], p[(2, 3)], 0.6), p[(2, 4)]]
    for a, b in zip(pts, pts[1:]):
        m.connect_vertices(_shared_face(m, a, b), a, b)
    assert_mesh_invariants(m, context="K1")
    return _sizes(m)


def k3():
    m, p = _grid()
    a = _split_at(m, p[(1, 1)], p[(2, 1)], 0.5)
    b = _split_at(m, p[(1, 2)], p[(2, 2)], 0.5)
    f = _shared_face(m, a, b)
    vs = m.face_vertices(f)
    ip = m.add_vertex((1.5, 1.3, 0.0))
    i, j = sorted((vs.index(a), vs.index(b)))
    loop1 = vs[i:j + 1] + [ip]
    loop2 = vs[j:] + vs[:i + 1] + [ip]
    m.remove_face(f)
    m.add_face(loop1)
    m.add_face(loop2)
    assert_mesh_invariants(m, context="K3")
    return _sizes(m)


if __name__ == "__main__":
    print("K1 path over 3 faces:", k1())
    print("K3 interior point via remove/add:", k3())
