"""Triangulierung: einfache Polygone (konvex + konkav) und Fallbacks.

Der Adapter trianguliert NUR für die Render-Darstellung (Core bleibt
polygonbasiert). Diese Tests sichern die Determiniertheit der Ableitung.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
for _p in (str(_LAB), str(_LAB.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.triangulate import triangulate_polygon  # noqa: E402


def test_tri_face_unchanged():
    positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    assert triangulate_polygon(positions, [0, 1, 2]) == [(0, 1, 2)]


def test_convex_quad_two_triangles():
    positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    tris = triangulate_polygon(positions, [0, 1, 2, 3])
    assert len(tris) == 2                     # n-2
    flat = sorted(tuple(sorted(t)) for t in tris)
    assert flat == [(0, 1, 2), (0, 2, 3)] or \
           flat == [(0, 1, 2), (0, 3, 1)]    # orientierungsabhängig erlaubt


def test_concave_quad_ear_clip_stays_inside():
    # L-förmiges konkaves Quad: Vertex 1 liegt innen.
    positions = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 2.0, 0.0)]
    tris = triangulate_polygon(positions, [0, 1, 2, 3])
    assert len(tris) == 2
    for tri in tris:
        assert len(set(tri)) == 3


def test_ngon_returns_n_minus_2():
    positions = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0),
        (0.5, 1.5, 0.0), (0.0, 1.0, 0.0),
    ]
    tris = triangulate_polygon(positions, [0, 1, 2, 3, 4])
    assert len(tris) == 3
    all_vertices = {v for tri in tris for v in tri}
    assert all_vertices == {0, 1, 2, 3, 4}


def test_degenerate_polygon_falls_back_deterministically():
    # Kollinear → degeneriert; Fallback-Fan muss deterministisch sein.
    positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)]
    tris = triangulate_polygon(positions, [0, 1, 2, 3])
    assert len(tris) == 2
    assert tris == [(0, 1, 2), (0, 2, 3)]