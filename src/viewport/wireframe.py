"""Wireframe-Segmente (WP-06 B5a, E38) — headless.

Zwei Endpunkte (Weltpositionen) pro Mesh-Edge, in `mesh.all_edge_ids()`-
Reihenfolge. Gezeichnet werden sie von `gl_line_overlay.GLLineOverlay`;
dieses Modul kennt kein GL. Bewusst nicht in `SelectionOverlay`: Wireframe
ist Darstellung, keine Selektion.
"""

from __future__ import annotations

from core import Mesh

Point = tuple[float, float, float]


def edge_segments(mesh: Mesh) -> list[tuple[Point, Point]]:
    """Ein `(a, b)`-Paar pro Edge — die Weltpositionen ihrer beiden Vertices."""
    position = mesh.vertex_position
    segments = []
    for edge_id in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(edge_id)
        segments.append((tuple(position(va)), tuple(position(vb))))
    return segments
