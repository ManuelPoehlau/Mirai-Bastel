"""VBO-Daten für das Lab — reine, GL-freie Funktionen.

Adaptiert (kopiert, nicht importiert — Handoff Slice 2 §2.1) aus
`playground/vbo_builder.py` (`build_face_data`, `build_edge_data`,
`build_vertex_data`, `build_selection_vertex_data`), Stand `324c2e0`.

Abweichung: `face_data` liefert nur Positionen + Smooth-Normalen. Flat-Normalen
und Per-Vertex-Farben entfallen, weil das Lab nur einen Shaded-Modus zeichnet.
"""

from __future__ import annotations

from collections.abc import Iterable

from core import Mesh, VertexId
from viewport.derived import DerivedGeometry, triangulate_face


def face_data(mesh: Mesh) -> tuple[list[float], list[float]]:
    """(positions, normals) für GL_TRIANGLES, expandiert (kein Index-Buffer)."""
    derived = DerivedGeometry(mesh)
    positions: list[float] = []
    normals: list[float] = []
    for fid in mesh.all_face_ids():
        for tri in triangulate_face(mesh.face_vertices(fid)):
            for vid in tri:
                positions.extend(mesh.vertex_position(vid))
                normals.extend(derived.vertex_normals.get(vid, (0.0, 1.0, 0.0)))
    return positions, normals


def edge_data(mesh: Mesh) -> list[float]:
    """Positionen für GL_LINES: zwei Punkte pro Edge."""
    positions: list[float] = []
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        positions.extend(mesh.vertex_position(va))
        positions.extend(mesh.vertex_position(vb))
    return positions


def vertex_data(mesh: Mesh) -> list[float]:
    """Positionen für GL_POINTS: ein Punkt pro Vertex."""
    positions: list[float] = []
    for vid in mesh.all_vertex_ids():
        positions.extend(mesh.vertex_position(vid))
    return positions


def highlight_data(mesh: Mesh, selected: Iterable[VertexId]) -> list[float]:
    """Positionen der selektierten Vertices für GL_POINTS."""
    positions: list[float] = []
    for vid in selected:
        positions.extend(mesh.vertex_position(vid))
    return positions
