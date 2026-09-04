"""Derived Data für das V0.2 Experiment: Bounds/AABB + lokale Normalen.

Bounds/Normalen sind KEINE Topology. Sie werden aktualisiert, wenn sich
an einem relevanten Vertex die Position ändert (Derived-Data-Update), ohne
strukturellen Rebuild.

Normalen-Definition (im Experiment gewählt):
- Face-Normale eines Triangles: rechtshändig normalisierte Flächennormale
  (a-b) x (c-b).
- Vertex-Normale: flächengewichteter Durchschnitt der Normalen aller
  incident Triangle-Faces.

Minimale betroffene Nachbarschaft bei einem Vertex-Move V:
  incident faces(F) von V -> deren Normale neu
  dann alle Vertices, die an mindestens einer betroffenen Face beteiligt
  sind -> deren Vertex-Normalen neu (einfacher 1-Ring der betroffenen Faces).
"""
from __future__ import annotations

import math

try:
    from .mesh import Mesh
except ImportError:  # direkter Skript-Aufruf
    from mesh import Mesh

Vec3 = tuple[float, float, float]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _len(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _normalize(a: Vec3) -> Vec3:
    l = _len(a)
    if l < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / l, a[1] / l, a[2] / l)


def triangle_normal(positions: Vec3, tri: tuple[int, int, int]) -> Vec3:
    a, b, c = (positions[i] for i in tri)
    return _normalize(_cross(_sub(b, a), _sub(c, a)))


def compute_bounds(positions: list[Vec3]) -> tuple[Vec3, Vec3]:
    """(min, max) AABB über alle Vertex-Positionen."""
    if not positions:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    mins = [positions[0][0], positions[0][1], positions[0][2]]
    maxs = list(mins)
    for p in positions:
        for i in range(3):
            if p[i] < mins[i]:
                mins[i] = p[i]
            if p[i] > maxs[i]:
                maxs[i] = p[i]
    return (mins[0], mins[1], mins[2]), (maxs[0], maxs[1], maxs[2])


class DerivedData:
    """Hält Face-/Vertex-Normalen und Bounds; erlaubt lokale Updates."""

    def __init__(self, mesh: Mesh) -> None:
        self.face_normals: list[Vec3] = []
        self.vertex_normals: list[Vec3] = []
        self.bounds_min: Vec3 = (0.0, 0.0, 0.0)
        self.bounds_max: Vec3 = (0.0, 0.0, 0.0)
        self.full_recompute(mesh)

    def full_recompute(self, mesh: Mesh) -> None:
        """Voller Rebuild (bei Topology-Änderung oder Initial)."""
        self.face_normals = [
            triangle_normal(mesh.positions, tri) for tri in mesh.triangles
        ]
        n_verts = len(mesh.positions)
        self.vertex_normals = [(0.0, 0.0, 0.0)] * n_verts
        # flächengewichteter Durchschnitt pro Vertex
        sums: list[Vec3] = [(0.0, 0.0, 0.0)] * n_verts
        for f, tri in enumerate(mesh.triangles):
            fn = self.face_normals[f]
            for v in tri:
                sums[v] = (sums[v][0] + fn[0], sums[v][1] + fn[1], sums[v][2] + fn[2])
        for v in range(n_verts):
            self.vertex_normals[v] = _normalize(sums[v])
        self.bounds_min, self.bounds_max = compute_bounds(mesh.positions)

    def update_face_normals(self, mesh: Mesh, face_ids: list[int]) -> None:
        """Berechnet die Normale aller betroffenen Faces neu."""
        for f in face_ids:
            self.face_normals[f] = triangle_normal(mesh.positions, mesh.triangles[f])

    def update_vertex_normals(self, mesh: Mesh, vertex_ids: set[int]) -> None:
        """Berechnet die Vertex-Normalen für die gegebenen Vertices neu.

        Verwendet die (bereits aktualisierten) Face-Normalen der incident
        Faces jedes Vertices (flächengewichteter Durchschnitt).
        """
        sums: dict[int, Vec3] = {}
        for v in vertex_ids:
            sums[v] = (0.0, 0.0, 0.0)
        for v in vertex_ids:
            for f in mesh.vertex_to_faces[v]:
                fn = self.face_normals[f]
                for u in mesh.triangles[f]:
                    if u in sums:
                        s = sums[u]
                        sums[u] = (s[0] + fn[0], s[1] + fn[1], s[2] + fn[2])
        for v, s in sums.items():
            self.vertex_normals[v] = _normalize(s)

    def recompute_bounds(self, positions: list[Vec3]) -> None:
        self.bounds_min, self.bounds_max = compute_bounds(positions)

    def affected_neighborhood(
        self, mesh: Mesh, moved_vertices: set[int]
    ) -> tuple[list[int], set[int]]:
        """Gibt (betroffene Face-IDs, betroffene Vertex-IDs) für Moves zurück.

        - Face-IDs: alle incident Faces der verschobenen Vertices.
        - Vertex-IDs: alle Vertices dieser Faces (der 1-Ring der Faces).
        """
        affected_faces: set[int] = set()
        for v in moved_vertices:
            affected_faces.update(mesh.vertex_to_faces.get(v, ()))
        affected_vertices: set[int] = set()
        for f in affected_faces:
            affected_vertices.update(mesh.triangles[f])
        return sorted(affected_faces), affected_vertices
