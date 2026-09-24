"""VBO-Daten für das Lab — reine, GL-freie Funktionen.

Adaptiert (kopiert, nicht importiert — Handoff Slice 2 §2.1) aus
`playground/vbo_builder.py` (`build_face_data`, `build_edge_data`,
`build_vertex_data`, `build_selection_vertex_data`), Stand `324c2e0`.

Abweichung: `face_data` liefert nur Positionen + Smooth-Normalen. Flat-Normalen
und Per-Vertex-Farben entfallen, weil das Lab nur einen Shaded-Modus zeichnet.

Slice 3: `plane_outline_data` (Lab-eigen) zeichnet die Symmetrie-Ebene als
Rechteck-Umriss in der Ebene durch den Ursprung (E1), bemessen auf die
Mesh-Bounds der beiden Achsen, die in der Ebene liegen.
"""

from __future__ import annotations

from collections.abc import Iterable

from typing import Optional

from core import Mesh, VertexId
from mirai.mesh_geometry import mesh_bounds
from viewport.derived import DerivedGeometry, triangulate_face

from .lab_symmetry import AXIS_INDEX

#: Umriss ragt um diesen Anteil der größten In-Ebene-Ausdehnung über die Bounds.
PLANE_MARGIN = 0.1


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
    """Positionen der übergebenen Vertices für GL_POINTS (Auswahl, Vorschau, Befund)."""
    positions: list[float] = []
    for vid in selected:
        positions.extend(mesh.vertex_position(vid))
    return positions


def plane_outline_data(mesh: Mesh, axis: Optional[str]) -> list[float]:
    """GL_LINES-Positionen (4 Linien) des Ebenen-Umrisses; leer, wenn aus."""
    if axis is None:
        return []
    normal_i = AXIS_INDEX[axis]
    u, w = (i for i in range(3) if i != normal_i)
    lo, hi = mesh_bounds(mesh)
    pad = PLANE_MARGIN * max(hi[u] - lo[u], hi[w] - lo[w], 1e-6)
    corners2d = (
        (lo[u] - pad, lo[w] - pad),
        (hi[u] + pad, lo[w] - pad),
        (hi[u] + pad, hi[w] + pad),
        (lo[u] - pad, hi[w] + pad),
    )
    corners = []
    for cu, cw in corners2d:
        p = [0.0, 0.0, 0.0]
        p[u], p[w] = cu, cw
        corners.append(p)
    positions: list[float] = []
    for a, b in zip(corners, corners[1:] + corners[:1]):
        positions.extend(a)
        positions.extend(b)
    return positions
