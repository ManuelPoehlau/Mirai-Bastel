"""VBO-Daten-Builder für AP-02.5 — reine, GL-freie Funktionen.

Extrahiert aus PlaygroundWindow._rebuild_vbo() damit die Geometrie-Logik
headless testbar ist (kein GL-Kontext, kein pyglet).

Aufgerufen von PlaygroundWindow._rebuild_vbo(); direkt testbar in
playground/tests/test_presentation.py.
"""

from __future__ import annotations

from playground._paths import ensure_paths

ensure_paths()

from core import Mesh  # noqa: E402
from viewport.derived import DerivedGeometry, triangulate_face  # noqa: E402


def build_face_data(
    mesh: Mesh, derived: DerivedGeometry
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Expanded (non-indexed) Face-VBO-Daten für Smooth- und Flat-Shading.

    Gibt (positions, smooth_normals, flat_normals, colors) zurück.
    Je drei Einträge (je 3 Floats) pro Dreieck, jedes Dreieck eigenständig
    (kein shared-vertex-Indexing), damit Flat-Normals per Face eindeutig sind.
    """
    positions: list[float] = []
    smooth_normals: list[float] = []
    flat_normals: list[float] = []
    colors: list[float] = []

    for fid in mesh.all_face_ids():
        face_normal = derived.face_normals.get(fid, (0.0, 1.0, 0.0))
        boundary = mesh.face_vertices(fid)
        for a, b, c in triangulate_face(boundary):
            for vid in (a, b, c):
                positions.extend(mesh.vertex_position(vid))
                smooth_normals.extend(
                    derived.vertex_normals.get(vid, (0.0, 1.0, 0.0))
                )
                flat_normals.extend(face_normal)
                colors.extend((1.0, 1.0, 1.0))

    return positions, smooth_normals, flat_normals, colors


def build_edge_data(mesh: Mesh) -> list[float]:
    """Positionen für Edge-VBO (GL_LINES): zwei Positionen pro Edge."""
    edge_positions: list[float] = []
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        edge_positions.extend(mesh.vertex_position(va))
        edge_positions.extend(mesh.vertex_position(vb))
    return edge_positions


def build_vertex_data(mesh: Mesh) -> list[float]:
    """Positionen für Vertex-VBO (GL_POINTS): eine Position pro Vertex."""
    vert_positions: list[float] = []
    for vid in mesh.all_vertex_ids():
        vert_positions.extend(mesh.vertex_position(vid))
    return vert_positions
