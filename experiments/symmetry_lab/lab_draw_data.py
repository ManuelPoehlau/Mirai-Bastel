"""VBO-Daten für das Lab — reine, GL-freie Funktionen.

Adaptiert (kopiert, nicht importiert — Handoff Slice 2 §2.1) aus
`playground/vbo_builder.py` (`build_face_data`, `build_edge_data`,
`build_vertex_data`, `build_selection_vertex_data`), Stand `324c2e0`.

Abweichung: `face_data` liefert nur Positionen + Smooth-Normalen. Flat-Normalen
und Per-Vertex-Farben entfallen, weil das Lab nur einen Shaded-Modus zeichnet.

Slice 3: `plane_outline_data` (Lab-eigen) zeichnet die Symmetrie-Ebene als
Rechteck-Umriss in der Ebene durch den Ursprung (E1), bemessen auf die
Mesh-Bounds der beiden Achsen, die in der Ebene liegen.

Slice 4 (E10, Lab-lokal — keine Änderung an `viewport.derived`): `face_data`
trianguliert und berechnet Normalen selbst, statt `DerivedGeometry`/
`triangulate_face` zu benutzen:

- Befund (verifiziert): Die Production-Fan-Triangulierung wählt die
  Quad-Diagonale nach der gespeicherten Vertex-Reihenfolge (immer v0-v2).
  Bei einem gespiegelten Quad-Paar ist diese Diagonale i. A. nicht die
  gespiegelte der anderen Seite (`subd_cube` X: alle 24 gespiegelten
  Quad-Zuordnungen asymmetrisch). Mit "kürzere Diagonale" (Abstände sind
  spiegelinvariant) sind es 0 (`head_basemesh` X: dort war die
  Fan-Diagonale bereits in beiden Fällen 0 — kein Unterschied).
- Deshalb: Quads werden hier an der kürzeren Diagonale trianguliert (bei
  exakt gleicher Länge: bisheriges Fan-Verhalten, Diagonale v0-v2).
  Dreiecke und n-Gons bleiben unverändert `triangulate_face`.
- Face-Normale ebenfalls lab-lokal nach Newell (ordnungsunabhängig vom
  Start-Vertex, spiegeläquivariant) statt "erstes Fan-Dreieck"
  (`DerivedGeometry`, dort vom Start-Vertex abhängig und deshalb bei
  gespiegelten Quads asymmetrisch). Vertex-Normale = normierte Summe der
  Normalen der angrenzenden Faces — gleiches Schema wie `DerivedGeometry`,
  hier nur mit den Newell-Face-Normalen.
- Grenze, dokumentiert, nicht gelöst: Ein Quad, das selbst über die
  Symmetrie-Ebene reicht, kann prinzipiell nicht symmetrisch in zwei
  Dreiecke geteilt werden (siehe README).
- Reine Anzeige-Entscheidung des Labs: Übernahme nach Production (betrifft
  Playground, Picking, Normal-Space) ist eine spätere, eigene Entscheidung.

Slice 5 (E15): `resym_preview_data` liefert die Punkte/Linien der
Re-Symmetrize-Vorschau aus demselben `ResymPlan`, den die Ausführung benutzt.

Slice 7 (E30): `knife_preview_data` liefert die Marker der Knife-Session —
Start-Vertex + Spiegelpartner aus der Session, Hover-Punkt + Spiegelpunkt
aus demselben Dry-Run (`KnifeHoverPreview`), den die Statuszeile nennt.
Der geschnittene Pfad selbst braucht keine eigene Struktur: jeder
angenommene Klick mutiert das Mesh sofort (Slice 6).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from typing import Optional

from core import FaceId, Mesh, VertexId
from mirai.mesh_geometry import mesh_bounds
from viewport.derived import triangulate_face

from .lab_knife import LabKnifeTool
from .lab_knife_preview import KnifeHoverPreview
from .lab_resymmetrize import PositionChange, ResymPlan
from .lab_symmetry import AXIS_INDEX

Vec3 = tuple[float, float, float]

#: Umriss ragt um diesen Anteil der größten In-Ebene-Ausdehnung über die Bounds.
PLANE_MARGIN = 0.1


def _distance(a: Vec3, b: Vec3) -> float:
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def _newell_normal(positions: list[Vec3]) -> Vec3:
    """Face-Normale nach Newell (E10): ordnungsunabhängig vom Start-Vertex
    der Boundary, spiegeläquivariant — anders als die Production-Face-Normale
    (`viewport.derived.DerivedGeometry`), die das erste Fan-Dreieck nimmt.
    """
    nx = ny = nz = 0.0
    count = len(positions)
    for i in range(count):
        x0, y0, z0 = positions[i]
        x1, y1, z1 = positions[(i + 1) % count]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def face_normals(mesh: Mesh) -> dict[FaceId, Vec3]:
    """Face-Normale je Face nach Newell (E10). Öffentlich für die
    Charakterisierungstests (`tests/test_draw_data.py`)."""
    return {
        fid: _newell_normal([mesh.vertex_position(v) for v in mesh.face_vertices(fid)])
        for fid in mesh.all_face_ids()
    }


def vertex_normals(mesh: Mesh) -> dict[VertexId, Vec3]:
    """Normierte Summe der Normalen der angrenzenden Faces (gleiches Schema
    wie `viewport.derived.DerivedGeometry`, hier mit den Newell-Face-Normalen,
    E10). Öffentlich für die Charakterisierungstests."""
    fn = face_normals(mesh)
    sums: dict[VertexId, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for fid in mesh.all_face_ids():
        normal = fn[fid]
        for vid in mesh.face_vertices(fid):
            acc = sums[vid]
            acc[0] += normal[0]
            acc[1] += normal[1]
            acc[2] += normal[2]
    result: dict[VertexId, Vec3] = {}
    for vid in mesh.all_vertex_ids():
        acc = sums.get(vid, [0.0, 0.0, 0.0])
        length = math.sqrt(sum(c * c for c in acc))
        result[vid] = tuple(c / length for c in acc) if length >= 1e-12 else (0.0, 0.0, 0.0)
    return result


def triangulate_face_symmetric(
    mesh: Mesh, face_id: FaceId
) -> list[tuple[VertexId, VertexId, VertexId]]:
    """Trianguliert ein Quad an der kürzeren Diagonale (E10, spiegelinvariant,
    da Abstände sich unter Spiegelung nicht ändern). Bei exakt gleicher
    Diagonalenlänge: bisheriges Fan-Verhalten (Diagonale v0-v2). Dreiecke und
    n-Gons: unverändert `triangulate_face`. Öffentlich für die
    Charakterisierungstests.
    """
    boundary = mesh.face_vertices(face_id)
    if len(boundary) != 4:
        return triangulate_face(boundary)
    v0, v1, v2, v3 = boundary
    p0, p1, p2, p3 = (mesh.vertex_position(v) for v in boundary)
    if _distance(p1, p3) < _distance(p0, p2):
        return [(v0, v1, v3), (v1, v2, v3)]
    return [(v0, v1, v2), (v0, v2, v3)]


def face_data(mesh: Mesh) -> tuple[list[float], list[float]]:
    """(positions, normals) für GL_TRIANGLES, expandiert (kein Index-Buffer).

    Triangulierung und Normalen sind lab-lokal (E10, siehe Modul-Docstring).
    """
    v_normals = vertex_normals(mesh)
    positions: list[float] = []
    normals: list[float] = []
    for fid in mesh.all_face_ids():
        for tri in triangulate_face_symmetric(mesh, fid):
            for vid in tri:
                positions.extend(mesh.vertex_position(vid))
                normals.extend(v_normals.get(vid, (0.0, 1.0, 0.0)))
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


@dataclass(frozen=True)
class ResymPreviewData:
    """GL_POINTS-/GL_LINES-Positionen der Re-Symmetrize-Vorschau (E15)."""

    #: Zielseiten-Vertices, die sich bewegen werden: aktuelle Position + Linie zum Ziel.
    move_points: list[float]
    move_lines: list[float]
    #: Seam-Vertices, die auf die Ebene gelegt werden: aktuelle Position + Linie.
    seam_points: list[float]
    seam_lines: list[float]
    #: Zielseiten-Vertices ohne Partner, die unverändert bleiben.
    keep_points: list[float]


def _points_and_lines(changes: Iterable[PositionChange]) -> tuple[list[float], list[float]]:
    points: list[float] = []
    lines: list[float] = []
    for change in changes:
        points.extend(change.before)
        lines.extend(change.before)
        lines.extend(change.after)
    return points, lines


def resym_preview_data(mesh: Mesh, plan: Optional[ResymPlan]) -> ResymPreviewData:
    """Leer, wenn keine Vorschau aktiv ist (`plan is None`)."""
    if plan is None:
        return ResymPreviewData([], [], [], [], [])
    move_points, move_lines = _points_and_lines(plan.moves)
    seam_points, seam_lines = _points_and_lines(plan.seam_moves)
    keep = sorted(plan.unmatched, key=int)
    return ResymPreviewData(
        move_points, move_lines, seam_points, seam_lines, highlight_data(mesh, keep)
    )


@dataclass(frozen=True)
class KnifePreviewData:
    """GL_POINTS-Positionen der Knife-Marker (E30); alle leer ohne Session."""

    #: Start-Vertex der Session und sein Spiegelpartner (nicht, wenn auf der Seam).
    start_points: list[float]
    start_mirror_points: list[float]
    #: Klickbares Hover-Ziel (Vertex oder interpolierter Edge-Punkt) und Spiegelpunkt.
    hover_points: list[float]
    hover_mirror_points: list[float]
    #: Hover-Ziel, das nicht klickbar ist (`KnifeHoverPreview.clickable` falsch).
    blocked_points: list[float]


def knife_preview_data(
    mesh: Mesh, knife: Optional[LabKnifeTool], hover: Optional[KnifeHoverPreview]
) -> KnifePreviewData:
    if knife is None:
        return KnifePreviewData([], [], [], [], [])
    start = knife.start
    start_points: list[float] = []
    start_mirror: list[float] = []
    if start is not None:
        start_points = highlight_data(mesh, [start])
        # Symmetrie aus: `partner` setzt eine Definition voraus (Seam-Abfrage).
        partner = knife.partner(start) if knife.mirrored else None
        if partner is not None and partner != start:
            start_mirror = highlight_data(mesh, [partner])
    hover_points: list[float] = []
    hover_mirror: list[float] = []
    blocked: list[float] = []
    if hover is not None:
        if hover.clickable:
            hover_points = list(hover.source_position)
            if hover.mirror_position is not None:
                hover_mirror = list(hover.mirror_position)
        else:
            blocked = list(hover.source_position)
    return KnifePreviewData(start_points, start_mirror, hover_points, hover_mirror, blocked)
