"""Headless-Tests für AP-05 Loop/Ring-Erkennung.

    1. edge_ring auf Cube → 4 Edges, geschlossen
    2. edge_loop auf Cube → 1 Edge (Valenz-3-Vertices stoppen sofort), offen
    3. edge_loop durch Valenz-4-Vertex (2×2-Quad-Grid) → 2 Edges, offen
    4. edge_ring auf offenem Mesh (Boundary-Kante) → partieller Ring, offen
    5. Ungültige Edge → LoopRingError
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.mesh import Mesh  # noqa: E402
from playground.topology_tools.loop_ring import (  # noqa: E402
    edge_loop,
    edge_ring,
    LoopRingError,
    Traversal,
)
from playground.app import PlaygroundApp  # noqa: E402


def _cube_mesh() -> Mesh:
    app = PlaygroundApp()
    app.load_cube()
    return app.scene.mesh


def _2x2_grid() -> tuple[Mesh, dict]:
    mesh = Mesh()
    p = {}
    for row in range(3):
        for col in range(3):
            p[(row, col)] = mesh.add_vertex((float(col), float(row), 0.0))
    mesh.add_face([p[(0, 0)], p[(0, 1)], p[(1, 1)], p[(1, 0)]])
    mesh.add_face([p[(0, 1)], p[(0, 2)], p[(1, 2)], p[(1, 1)]])
    mesh.add_face([p[(1, 0)], p[(1, 1)], p[(2, 1)], p[(2, 0)]])
    mesh.add_face([p[(1, 1)], p[(1, 2)], p[(2, 2)], p[(2, 1)]])
    return mesh, p


# ---------------------------------------------------------------------------
# 1. edge_ring auf Cube → 4 Edges, geschlossen
# ---------------------------------------------------------------------------

def test_ring_cube_closed():
    mesh = _cube_mesh()
    start = next(iter(mesh.all_edge_ids()))
    traversal = edge_ring(mesh, start)
    assert isinstance(traversal, Traversal)
    assert traversal.closed is True
    assert len(traversal.edges) == 4
    assert start in traversal.edges
    assert len(set(traversal.edges)) == 4, "Keine Duplikate"


# ---------------------------------------------------------------------------
# 2. edge_loop auf Cube → nur Startkante (Valenz 3 bricht sofort ab)
# ---------------------------------------------------------------------------

def test_loop_cube_stops_at_valence_3():
    mesh = _cube_mesh()
    start = next(iter(mesh.all_edge_ids()))
    traversal = edge_loop(mesh, start)
    assert traversal.closed is False
    assert len(traversal.edges) == 1
    assert traversal.edges[0] == start


# ---------------------------------------------------------------------------
# 3. edge_loop durch Valenz-4-Vertex im 2×2-Grid → 2 Edges, offen
# ---------------------------------------------------------------------------

def test_loop_through_valence4_vertex():
    mesh, p = _2x2_grid()
    center = p[(1, 1)]

    # Finde Kante (p10, center) — grenzt links/rechts keine gemeinsame Face
    edge_to_center = None
    for eid in mesh.all_edge_ids():
        if set(mesh.edge_vertices(eid)) == {p[(1, 0)], center}:
            edge_to_center = eid
            break
    assert edge_to_center is not None

    traversal = edge_loop(mesh, edge_to_center)
    assert traversal.closed is False
    assert len(traversal.edges) == 2, "Startkante + eine durch Valenz-4-Vertex"
    assert edge_to_center in traversal.edges


# ---------------------------------------------------------------------------
# 4. edge_ring auf offenem Mesh (2-Quad-Strip, Boundary-Kante)
# ---------------------------------------------------------------------------

def test_ring_open_mesh_partial():
    """Ring auf offener Kante: läuft nur soweit Quad-Faces vorhanden sind."""
    mesh = Mesh()
    a = mesh.add_vertex((0.0, 0.0, 0.0))
    b = mesh.add_vertex((1.0, 0.0, 0.0))
    c = mesh.add_vertex((2.0, 0.0, 0.0))
    d = mesh.add_vertex((0.0, 1.0, 0.0))
    e = mesh.add_vertex((1.0, 1.0, 0.0))
    f = mesh.add_vertex((2.0, 1.0, 0.0))
    mesh.add_face([a, b, e, d])
    mesh.add_face([b, c, f, e])

    # Boundary-Kante a-d (nur in einer Face)
    edge_ad = None
    for eid in mesh.all_edge_ids():
        if set(mesh.edge_vertices(eid)) == {a, d}:
            edge_ad = eid
            break
    assert edge_ad is not None

    traversal = edge_ring(mesh, edge_ad)
    assert traversal.closed is False
    assert len(traversal.edges) >= 1
    assert edge_ad in traversal.edges


# ---------------------------------------------------------------------------
# 5. Ungültige Edge → LoopRingError
# ---------------------------------------------------------------------------

def test_loop_invalid_edge_raises():
    from core.ids import EdgeId
    mesh = _cube_mesh()
    with pytest.raises(LoopRingError):
        edge_loop(mesh, EdgeId(9999))


def test_ring_invalid_edge_raises():
    from core.ids import EdgeId
    mesh = _cube_mesh()
    with pytest.raises(LoopRingError):
        edge_ring(mesh, EdgeId(9999))


import pytest  # noqa: E402  (nach den Tests — pytest wird nur für raises gebraucht)
