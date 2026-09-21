"""DISCOVERY PROBE — per-face Connect semantics (Wings-3D-style) on src/core.

Status: research script, NOT a tool, NOT wired into the playground,
NOT a proposal for production. See
docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md.

Purpose: show, with the existing Core primitives only (split_edge,
connect_vertices), what a face-size-independent Connect would produce
on the scenarios where the current playground tool refuses to work.

Semantics modelled (from the Wings 3D source, wings_edge_cmd.erl /
wings_vertex.erl — read, not copied):
  1. Drop selected edges whose adjacent faces contain no other selected
     edge (they could never be connected).
  2. Split every remaining edge at its midpoint.
  3. Per ORIGINAL face: collect the new midpoints on its boundary in
     boundary order. 2 midpoints -> connect them. >2 midpoints ->
     connect consecutive midpoints cyclically (an inner polygon).
  4. Midpoints that end up unconnected are reported (Wings would dissolve
     them again; this probe only reports).

Run:  python experiments/topology/connect_per_face_probe.py
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

try:  # structural invariants, if available
    from mesh_invariants import assert_mesh_invariants  # noqa: E402
except Exception:  # pragma: no cover
    assert_mesh_invariants = None


def _midpoint(mesh, eid):
    a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
    return tuple((x + y) / 2.0 for x, y in zip(a, b))


def connect_per_face(mesh: Mesh, edge_ids) -> dict:
    sel = set(edge_ids)
    keep = [
        e for e in sel
        if any((set(mesh.face_edges(f)) - {e}) & sel for f in mesh.edge_faces(e))
    ]
    keep.sort(key=lambda e: _midpoint(mesh, e))  # deterministic, geometry-based

    original_faces = {e: list(mesh.edge_faces(e)) for e in keep}
    mids = {}
    for e in keep:
        v, _, _ = mesh.split_edge(e)
        mids[e] = v
    midset = set(mids.values())

    # Pairs per original face, in boundary order.
    faces = sorted({f for fs in original_faces.values() for f in fs}, key=str)
    pairs = []
    for f in faces:
        if not mesh.is_valid_face(f):
            continue
        on_face = [v for v in mesh.face_vertices(f) if v in midset]
        if len(on_face) == 2:
            pairs.append((on_face[0], on_face[1]))
        elif len(on_face) > 2:
            pairs += [(on_face[i], on_face[(i + 1) % len(on_face)]) for i in range(len(on_face))]

    created, skipped = [], []
    for a, b in pairs:
        target = None
        for f in mesh.all_face_ids():
            vs = mesh.face_vertices(f)
            if a in vs and b in vs:
                i, j = vs.index(a), vs.index(b)
                if (i - j) % len(vs) not in (1, len(vs) - 1):  # not already adjacent
                    target = f
                    break
        if target is None:
            skipped.append((a, b))
            continue
        e, _, _ = mesh.connect_vertices(target, a, b)
        created.append(e)

    connected = {v for e in created for v in mesh.edge_vertices(e)}
    return {
        "dropped_edges": len(sel) - len(keep),
        "created": len(created),
        "skipped_pairs": len(skipped),
        "unconnected_midpoints": len(midset - connected),
    }


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def _grid(n=4):
    m = Mesh()
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = m.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            m.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return m, p


def _e(m, a, b):
    return next(e for e in m.all_edge_ids() if set(m.edge_vertices(e)) == {a, b})


def _summary(m):
    fs = dict(sorted(collections.Counter(len(m.face_vertices(f)) for f in m.all_face_ids()).items()))
    interior = [v for v in m.all_vertex_ids()
                if all(len(m.edge_faces(e)) == 2 for e in m.vertex_edges(v))]
    val = dict(sorted(collections.Counter(len(m.vertex_edges(v)) for v in interior).items()))
    free = sum(1 for e in m.all_edge_ids() if len(m.edge_faces(e)) == 0)
    return fs, val, free


SCENARIOS = {
    "A  Teilschnitt über 1 Quad": lambda m, p: [_e(m, p[(1, 1)], p[(2, 1)]), _e(m, p[(1, 2)], p[(2, 2)])],
    "B  Teilschnitt über 2 Quads": lambda m, p: [_e(m, p[(1, c)], p[(2, c)]) for c in (1, 2, 3)],
    "C  Rand → Rand": lambda m, p: [_e(m, p[(1, c)], p[(2, c)]) for c in range(5)],
    "D  Ecke abschneiden": lambda m, p: [_e(m, p[(1, 1)], p[(1, 2)]), _e(m, p[(1, 2)], p[(2, 2)])],
    "E  'kind v' (kollinear über Vertex)": lambda m, p: [_e(m, p[(2, 1)], p[(2, 2)]), _e(m, p[(2, 2)], p[(2, 3)])],
    "F  Lücke von 1 Quad": lambda m, p: [_e(m, p[(1, 1)], p[(2, 1)]), _e(m, p[(1, 3)], p[(2, 3)])],
    "G  Pfad knickt um 90°": lambda m, p: [_e(m, p[(1, 1)], p[(2, 1)]), _e(m, p[(1, 2)], p[(2, 2)]),
                                        _e(m, p[(2, 2)], p[(2, 3)])],
    "I  alle 4 Kanten eines Quads": lambda m, p: [_e(m, p[(1, 1)], p[(1, 2)]), _e(m, p[(1, 2)], p[(2, 2)]),
                                               _e(m, p[(2, 2)], p[(2, 1)]), _e(m, p[(2, 1)], p[(1, 1)])],
}


def _continuation():
    """A, then continue the cut into the neighbouring (now pentagonal) face."""
    m, p = _grid()
    connect_per_face(m, SCENARIOS["A  Teilschnitt über 1 Quad"](m, p))
    half = next(e for e in m.all_edge_ids()
                if p[(1, 2)] in m.edge_vertices(e)
                and any(abs(m.vertex_position(v)[1] - 1.5) < 1e-9 for v in m.edge_vertices(e)))
    # The new midpoint on x=2 already exists; to continue, the artist selects the
    # next vertical edge together with the pentagon's split half-edge.
    info = connect_per_face(m, [half, _e(m, p[(1, 3)], p[(2, 3)])])
    return m, info


def main():
    print(f"{'Szenario':38} {'neu':>3} {'verworfen':>9} {'lose MP':>7}  Faces nach Ecken   innere Valenzen   freie Kanten")
    for name, fn in SCENARIOS.items():
        m, p = _grid()
        info = connect_per_face(m, fn(m, p))
        if assert_mesh_invariants:
            assert_mesh_invariants(m, context=name)
        fs, val, free = _summary(m)
        print(f"{name:38} {info['created']:>3} {info['dropped_edges']:>9} {info['unconnected_midpoints']:>7}  {str(fs):18} {str(val):17} {free}")
    m, info = _continuation()
    if assert_mesh_invariants:
        assert_mesh_invariants(m, context="A2")
    fs, val, free = _summary(m)
    print(f"{'A2 A + Weiterschneiden am Fünfeck':38} {info['created']:>3} {info['dropped_edges']:>9} {info['unconnected_midpoints']:>7}  {str(fs):18} {str(val):17} {free}")


if __name__ == "__main__":
    main()
