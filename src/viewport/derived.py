"""Derived Geometry für den Viewport v0.2: Adjazenz, Normalen, Bounds.

Adaptiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/derived.py`) auf die reale
`src.core.Mesh`-API:

- Faces sind n-gonale, geordnete Vertex-Boundaries (`mesh.face_vertices`),
  nicht fest triangulierte 3-Tupel wie im Experiment. Für Normalen/Rendering
  wird hier per Fan-Triangulierung trianguliert (siehe `triangulate_face`).
- Vertex-/Face-IDs sind opake `VertexId`/`FaceId`-Objekte (siehe
  `src.core.ids`), keine Array-Indizes — die Adjazenz-Struktur ist deshalb
  ein Dict, kein `list`.

Bounds/Normalen sind KEINE Topology (VIEWPORT_V02_ARCHITECTURE.md §4.4).
Sie werden bei einer Vertex-Positionsänderung lokal aktualisiert, ohne
strukturellen Rebuild.

Normalen-Definition (wie im Experiment gewählt und im Proof verifiziert):

- Face-Normale: rechtshändige, normalisierte Normale aus dem ersten
  Dreieck der Fan-Triangulierung einer Face-Boundary.
- Vertex-Normale: flächengewichteter Durchschnitt der Normalen aller
  incident Faces.

Minimale betroffene Nachbarschaft bei einem Vertex-Move V (siehe
`affected_neighborhood`):
    incident faces(V) -> deren Face-Normale neu
    -> alle Vertices dieser Faces (1-Ring) -> deren Vertex-Normale neu
"""

from __future__ import annotations

import math
from collections import defaultdict

from core import FaceId, Mesh, VertexId

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------------
# Reine Vektor-Hilfsfunktionen (bewusst ohne externe Abhängigkeit)
# ---------------------------------------------------------------------


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _normalize(a: Vec3) -> Vec3:
    length = _length(a)
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def triangulate_face(vertex_ids: list[VertexId]) -> list[tuple[VertexId, VertexId, VertexId]]:
    """Fan-Triangulierung einer geordneten (konvexen) Face-Boundary.

    Für Dreiecke/Quads (der V1-Regelfall) korrekt; für allgemeine konkave
    n-Gons eine bewusste Vereinfachung (siehe VIEWPORT_V02_ARCHITECTURE.md
    Non-Goals: kein allgemeiner Polygon-Trianguliator).
    """
    if len(vertex_ids) < 3:
        return []
    v0 = vertex_ids[0]
    return [
        (v0, vertex_ids[i], vertex_ids[i + 1])
        for i in range(1, len(vertex_ids) - 1)
    ]


def triangle_normal(positions: dict[VertexId, Vec3], tri: tuple[VertexId, VertexId, VertexId]) -> Vec3:
    a, b, c = (positions[v] for v in tri)
    return _normalize(_cross(_sub(b, a), _sub(c, a)))


def compute_bounds(positions: list[Vec3]) -> tuple[Vec3, Vec3]:
    """(min, max) AABB über eine Liste von Positionen."""
    if not positions:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    mins = list(positions[0])
    maxs = list(positions[0])
    for p in positions:
        for i in range(3):
            if p[i] < mins[i]:
                mins[i] = p[i]
            if p[i] > maxs[i]:
                maxs[i] = p[i]
    return (mins[0], mins[1], mins[2]), (maxs[0], maxs[1], maxs[2])


class DerivedGeometry:
    """Adjazenz (`vertex_to_faces`) + Face-/Vertex-Normalen + Bounds.

    `vertex_to_faces` ist bewusst hier (nicht im Core) angesiedelt: reine
    Render-/Derived-Data, nicht Teil der Topologie-Domäne (§7 der
    Core-Spezifikation - Topologie-Grenze).
    """

    def __init__(self, mesh: Mesh) -> None:
        self.vertex_to_faces: dict[VertexId, set[FaceId]] = {}
        self.face_normals: dict[FaceId, Vec3] = {}
        self.vertex_normals: dict[VertexId, Vec3] = {}
        self.bounds_min: Vec3 = (0.0, 0.0, 0.0)
        self.bounds_max: Vec3 = (0.0, 0.0, 0.0)
        self.full_recompute(mesh)

    # -- Adjazenz ----------------------------------------------------------

    def rebuild_adjacency(self, mesh: Mesh) -> None:
        """Baut `vertex_to_faces` komplett neu auf (nur bei Topology-Change nötig)."""
        adjacency: dict[VertexId, set[FaceId]] = defaultdict(set)
        for face_id in mesh.all_face_ids():
            for vertex_id in mesh.face_vertices(face_id):
                adjacency[vertex_id].add(face_id)
        self.vertex_to_faces = dict(adjacency)

    # -- Voller Rebuild (Topology-Change oder initial) ----------------------

    def full_recompute(self, mesh: Mesh) -> None:
        self.rebuild_adjacency(mesh)

        positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}

        self.face_normals = {}
        for face_id in mesh.all_face_ids():
            boundary = mesh.face_vertices(face_id)
            tris = triangulate_face(boundary)
            if not tris:
                self.face_normals[face_id] = (0.0, 0.0, 0.0)
                continue
            # Face-Normale = Normale des ersten Fan-Dreiecks (planare Faces
            # in V1 - siehe scene_factory.create_cube).
            self.face_normals[face_id] = triangle_normal(positions, tris[0])

        sums: dict[VertexId, Vec3] = {v: (0.0, 0.0, 0.0) for v in mesh.all_vertex_ids()}
        for vertex_id, face_ids in self.vertex_to_faces.items():
            acc = sums[vertex_id]
            for face_id in face_ids:
                fn = self.face_normals[face_id]
                acc = (acc[0] + fn[0], acc[1] + fn[1], acc[2] + fn[2])
            sums[vertex_id] = acc
        self.vertex_normals = {v: _normalize(s) for v, s in sums.items()}

        self.bounds_min, self.bounds_max = compute_bounds(list(positions.values()))

    # -- Inkrementelle Updates (Position-Change, keine Topology) -------------

    def affected_neighborhood(
        self, mesh: Mesh, moved_vertices: set[VertexId]
    ) -> tuple[set[FaceId], set[VertexId]]:
        """(betroffene Face-IDs, betroffene Vertex-IDs) für eine Menge bewegter
        Vertices — der minimale 1-Ring, der neu berechnet werden muss."""
        affected_faces: set[FaceId] = set()
        for vertex_id in moved_vertices:
            affected_faces.update(self.vertex_to_faces.get(vertex_id, ()))
        affected_vertices: set[VertexId] = set()
        for face_id in affected_faces:
            affected_vertices.update(mesh.face_vertices(face_id))
        return affected_faces, affected_vertices

    def update_face_normals(self, mesh: Mesh, face_ids: set[FaceId]) -> None:
        """Berechnet die Normale jeder betroffenen Face neu (aus aktueller Position)."""
        for face_id in face_ids:
            boundary = mesh.face_vertices(face_id)
            tris = triangulate_face(boundary)
            if not tris:
                self.face_normals[face_id] = (0.0, 0.0, 0.0)
                continue
            positions = {v: mesh.vertex_position(v) for v in boundary}
            self.face_normals[face_id] = triangle_normal(positions, tris[0])

    def update_vertex_normals(self, mesh: Mesh, vertex_ids: set[VertexId]) -> None:
        """Berechnet die Vertex-Normale für die gegebenen Vertices neu.

        Verwendet die (bereits aktualisierten) Face-Normalen der incident
        Faces jedes Vertex (flächengewichteter Durchschnitt) — es werden
        KEINE Faces außerhalb `vertex_ids` neu besucht.
        """
        for vertex_id in vertex_ids:
            acc: Vec3 = (0.0, 0.0, 0.0)
            for face_id in self.vertex_to_faces.get(vertex_id, ()):
                fn = self.face_normals[face_id]
                acc = (acc[0] + fn[0], acc[1] + fn[1], acc[2] + fn[2])
            self.vertex_normals[vertex_id] = _normalize(acc)

    def recompute_bounds(self, mesh: Mesh) -> None:
        positions = [mesh.vertex_position(v) for v in mesh.all_vertex_ids()]
        self.bounds_min, self.bounds_max = compute_bounds(positions)
