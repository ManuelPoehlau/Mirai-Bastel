"""DISCOVERY PROBE — Knife Face Cut: which face-interior results are valid topology?

Evidence for `docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` (Q2, Q3).
Not a tool, not wired anywhere, no Core change. Uses only the public Core API.

Three ways to get a cut with interior points into one face F:
  B2b  remove_face + add_vertex + add_face (tool-layer face surgery, AD-017 B2b);
       `split_face_path()` below also stands in for the proposed B2c primitive —
       same result, only the location of the code differs.
  CSM  connect_vertices(F, a, b) -> split_edge(new edge) k times -> set_vertex_position
       (only the primitives the Knife already uses + set_vertex_position; not in AD-017).

Cases (4x4 quad grid, unit quads, z = 0):
  FC1  edge@t -> 1 interior point -> edge@t        (a, b non-adjacent in F)
  FC2  edge@t -> 2 interior points -> edge@t       (a, b non-adjacent in F)
  FC3  notch: edge@0.3 -> interior -> same edge@0.7 (a, b adjacent in F)
  FC4  vertex -> interior -> adjacent vertex       (a, b adjacent in F)
  FC5  dangling: edge@t -> interior point, path ends there
  FC6  closed interior loop (triangle) with 0 / 1 / 2 bridges to the boundary
  FC7  interior -> interior in two different faces (segment crosses a shared edge)

Run:  python experiments/topology/knife_face_cut_probe.py
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
from core.mesh import MeshError  # noqa: E402
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


def _split(m, a, b, t):
    """Split edge a-b at t measured from a (split_edge measures from edge_vertices()[0])."""
    e = _edge(m, a, b)
    if m.edge_vertices(e)[0] != a:
        t = 1.0 - t
    v, _, _ = m.split_edge(e, t)
    return v


def _face_with(m, *vs):
    return next(f for f in sorted(m.all_face_ids(), key=int)
                if all(v in m.face_vertices(f) for v in vs))


def _sizes(m):
    return dict(sorted(collections.Counter(len(m.face_vertices(f)) for f in m.all_face_ids()).items()))


def _geometry(m):
    """Faces as position cycles (ID-independent), for comparing two constructions."""
    out = []
    for f in m.all_face_ids():
        cyc = [tuple(round(x, 6) for x in m.vertex_position(v)) for v in m.face_vertices(f)]
        out.append(tuple(sorted(cyc)))
    return sorted(out)


def _check(m, label):
    try:
        assert_mesh_invariants(m, context=label)
        return "invariants OK"
    except AssertionError as exc:
        return f"INVARIANT VIOLATION: {str(exc)[:90]}"


# -- construction 1: B2b / B2c stand-in ----------------------------------------------

def split_face_path(m, f, a, b, positions):
    """Split face f along a -> [interior positions...] -> b.

    What a B2c primitive would do, written with remove_face/add_vertex/add_face.
    Returns (new vertex ids in path order, face_1, face_2)."""
    boundary = m.face_vertices(f)
    if a == b or a not in boundary or b not in boundary:
        raise MeshError("a, b must be distinct boundary vertices of f")
    new_vs = [m.add_vertex(p) for p in positions]
    i, j = boundary.index(a), boundary.index(b)
    path = new_vs
    if i > j:
        i, j, path = j, i, list(reversed(new_vs))
    loop1 = boundary[i:j + 1] + list(reversed(path))       # a..b along boundary, back through the path
    loop2 = boundary[j:] + boundary[:i + 1] + list(path)    # b..a along boundary, forward through the path
    if len(loop1) < 3 or len(loop2) < 3:
        raise MeshError("degenerate face")
    m.remove_face(f)
    return new_vs, m.add_face(loop1), m.add_face(loop2)


# -- construction 2: CSM (connect -> split -> move) -----------------------------------

def connect_split_move(m, f, a, b, positions):
    """Same result from connect_vertices + split_edge + set_vertex_position only."""
    e, _, _ = m.connect_vertices(f, a, b)      # rejects adjacent a/b ("degenerate face")
    new_vs, tail = [], e                        # tail = remaining edge from the last point to b
    for pos in positions:
        v, e1, e2 = m.split_edge(tail, 0.5)
        m.set_vertex_position(v, pos)
        new_vs.append(v)
        tail = e2 if b in m.edge_vertices(e2) else e1
    return new_vs


def _pair(case, build):
    """Run one case with both constructions; report validity and whether they agree."""
    res = {}
    for name, fn in (("B2b", split_face_path), ("CSM", connect_split_move)):
        m, f, a, b, pos = build()
        try:
            fn(m, f, a, b, pos)
            res[name] = (m, f"{_check(m, case + ' ' + name)} sizes={_sizes(m)}")
        except MeshError as exc:
            res[name] = (None, f"REJECTED ({exc})")
    same = (res["B2b"][0] is not None and res["CSM"][0] is not None
            and _geometry(res["B2b"][0]) == _geometry(res["CSM"][0]))
    print(f"{case}: B2b -> {res['B2b'][1]}")
    print(f"{' ' * len(case)}  CSM -> {res['CSM'][1]}" + ("   [identical geometry]" if same else ""))


def fc1():
    m, p = _grid()
    a = _split(m, p[(1, 1)], p[(2, 1)], 0.5)
    b = _split(m, p[(1, 2)], p[(2, 2)], 0.5)
    return m, _face_with(m, a, b), a, b, [(1.5, 1.3, 0.0)]


def fc2():
    m, p = _grid()
    a = _split(m, p[(1, 1)], p[(2, 1)], 0.5)
    b = _split(m, p[(1, 2)], p[(2, 2)], 0.5)
    return m, _face_with(m, a, b), a, b, [(1.3, 1.2, 0.0), (1.7, 1.8, 0.0)]


def fc3():
    m, p = _grid()
    a = _split(m, p[(1, 1)], p[(1, 2)], 0.3)
    b = _split(m, a, p[(1, 2)], (0.7 - 0.3) / (1 - 0.3))
    return m, _face_with(m, a, b, p[(2, 2)]), a, b, [(1.5, 1.4, 0.0)]


def fc4():
    m, p = _grid()
    a, b = p[(1, 1)], p[(1, 2)]
    return m, _face_with(m, a, b, p[(2, 2)]), a, b, [(1.5, 1.5, 0.0)]


def fc5():
    """Dangling end: edge point E, interior point P, path stops at P."""
    print("FC5 dangling end (edge@0.5 -> interior, path stops):")
    m, p = _grid()
    e = _split(m, p[(1, 1)], p[(2, 1)], 0.5)
    f = _face_with(m, e, p[(1, 2)])
    boundary = m.face_vertices(f)
    q = m.add_vertex((1.5, 1.5, 0.0))
    i = boundary.index(e)
    spur = boundary[:i + 1] + [q] + boundary[i:]   # ... e, q, e ... (spur walked twice)
    m.remove_face(f)
    try:
        m.add_face(spur)
        print("  (a) spur inside the face boundary: add_face accepted it ->", _check(m, "FC5a"))
    except MeshError as exc:
        print("  (a) spur inside the face boundary: add_face REJECTED:", exc)
    m, p = _grid()
    e = _split(m, p[(1, 1)], p[(2, 1)], 0.5)
    f = _face_with(m, e, p[(1, 2)])
    q = m.add_vertex((1.5, 1.5, 0.0))
    free = m.add_edge(e, q)
    print(f"  (b) free edge via add_edge: {_check(m, 'FC5b')}; edge_faces={m.edge_faces(free)}; "
          f"face {int(f)} unchanged (size {len(m.face_vertices(f))}), q in no face "
          f"-> structurally 'valid', geometrically an edge lying on top of a face (cf. F7 'kind v')")


def fc6():
    """Closed interior loop P1-P2-P3 inside one quad."""
    print("FC6 closed interior loop (triangle inside one quad):")
    tri = [(1.3, 1.3, 0.0), (1.7, 1.3, 0.0), (1.5, 1.7, 0.0)]

    m, p = _grid()
    f = _face_with(m, p[(1, 1)], p[(2, 2)])
    vs = [m.add_vertex(x) for x in tri]
    m.add_face(vs)
    overlap = [int(x) for x in m.all_face_ids() if x == f]
    print(f"  0 bridges: inner face added, outer face kept -> {_check(m, 'FC6-0')}; "
          f"outer face {overlap} still covers the inner one (no hole representable: one boundary list per face)")

    m, p = _grid()
    c = p[(1, 1)]
    f = _face_with(m, c, p[(2, 2)])
    boundary = m.face_vertices(f)
    vs = [m.add_vertex(x) for x in tri]
    i = boundary.index(c)
    keyhole = boundary[:i + 1] + [vs[0], vs[2], vs[1], vs[0]] + boundary[i:]
    m.remove_face(f)
    m.add_face(vs)
    try:
        m.add_face(keyhole)
        print("  1 bridge : keyhole outer face accepted ->", _check(m, "FC6-1"))
    except MeshError as exc:
        print("  1 bridge : keyhole outer face REJECTED:", exc)

    m, p = _grid()
    c0, c2 = p[(1, 1)], p[(2, 2)]
    f = _face_with(m, c0, c2)
    new_vs, f1, f2 = split_face_path(m, f, c0, c2, [tri[0], tri[2]])        # c0 -> P1 -> P3 -> c2
    p1, p3 = new_vs
    g = _face_with(m, p1, p3, p[(1, 2)])                                    # the side containing P2's spot
    split_face_path(m, g, p1, p3, [tri[1]])                                  # P1 -> P2 -> P3 (p1, p3 adjacent)
    print(f"  2 bridges: via 2x split_face_path -> {_check(m, 'FC6-2')} sizes={_sizes(m)}")
    m, p = _grid()
    f = _face_with(m, c0, c2)
    connect_split_move(m, f, c0, c2, [tri[0], tri[2]])
    p1, p3 = (v for v in m.all_vertex_ids() if m.vertex_position(v) in (tri[0], tri[2]))
    g = _face_with(m, p1, p3, p[(1, 2)])
    try:
        connect_split_move(m, g, p1, p3, [tri[1]])
        print("  2 bridges: via 2x CSM ->", _check(m, "FC6-2csm"))
    except MeshError as exc:
        print(f"  2 bridges: via 2x CSM -> second path REJECTED ({exc}) — P1/P3 are adjacent after the first path")


def fc7():
    print("FC7 interior point in F1 -> interior point in neighbour F2:")
    m, p = _grid()
    f1 = _face_with(m, p[(1, 1)], p[(2, 2)])
    f2 = _face_with(m, p[(1, 2)], p[(2, 3)])
    shared = set(m.face_edges(f1)) & set(m.face_edges(f2))
    print(f"  F{int(f1)} and F{int(f2)} share edge {sorted(int(e) for e in shared)}; a segment between an interior "
          f"point of each is in no single face -> needs the crossing point on that edge (Q5), "
          f"otherwise it is not a one-face cut")


def ids_fc1():
    """ID continuity of split_face_path vs. connect_vertices' documented contract."""
    m, f, a, b, pos = fc1()
    before_v, before_e = set(m.all_vertex_ids()), set(m.all_edge_ids())
    boundary_edges = set(m.face_edges(f))
    hi_v, hi_e, hi_f = (max(int(x) for x in s) for s in
                        (m.all_vertex_ids(), m.all_edge_ids(), m.all_face_ids()))
    new_vs, f1, f2 = split_face_path(m, f, a, b, pos)
    new_e = set(m.all_edge_ids()) - before_e
    print("ID continuity (FC1, split_face_path):",
          f"face {int(f)} valid={m.is_valid_face(f)};",
          f"new faces {int(f1)},{int(f2)} > {hi_f}: {int(f1) > hi_f and int(f2) > hi_f};",
          f"new vertices {[int(v) for v in new_vs]} > {hi_v}: {all(int(v) > hi_v for v in new_vs)};",
          f"new edges {sorted(int(e) for e in new_e)} (= k+1 = {len(pos) + 1}) > {hi_e}: "
          f"{all(int(e) > hi_e for e in new_e) and len(new_e) == len(pos) + 1};",
          f"old vertices kept: {before_v <= set(m.all_vertex_ids())};",
          f"F's boundary edges kept: {boundary_edges <= set(m.all_edge_ids())}")


if __name__ == "__main__":
    _pair("FC1 edge -> 1 interior -> edge", fc1)
    _pair("FC2 edge -> 2 interior -> edge", fc2)
    _pair("FC3 notch on one edge (adjacent)", fc3)
    _pair("FC4 vertex -> interior -> adjacent vertex", fc4)
    fc5()
    fc6()
    fc7()
    ids_fc1()
