"""Derived Geometry für den Viewport v0.2: Adjazenz, Normalen, Bounds.

Adaptiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/derived.py`) auf die reale
`src.core.Mesh`-API:

- Faces sind n-gonale, geordnete Vertex-Boundaries (`mesh.face_vertices`),
  nicht fest triangulierte 3-Tupel wie im Experiment. Für Normalen/Rendering
  wird hier per Ear Clipping trianguliert (siehe `triangulate_face`).
- Vertex-/Face-IDs sind opake `VertexId`/`FaceId`-Objekte (siehe
  `src.core.ids`), keine Array-Indizes — die Adjazenz-Struktur ist deshalb
  ein Dict, kein `list`.

Bounds/Normalen sind KEINE Topology (VIEWPORT_V02_ARCHITECTURE.md §4.4).
Sie werden bei einer Vertex-Positionsänderung lokal aktualisiert, ohne
strukturellen Rebuild.

Normalen-Definition (wie im Experiment gewählt und im Proof verifiziert):

- Face-Normale: rechtshändige, normalisierte Normale aus dem ersten
  Dreieck der Triangulierung einer Face-Boundary.
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
from collections.abc import Mapping

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


_EAR_EPS = 1e-12


def _polygon_plane_axes(pts: list[Vec3]) -> tuple[int, int, float]:
    """(u-Achse, v-Achse, Vorzeichen) der Projektion entlang der dominanten
    Newell-Normalen. Das Vorzeichen spiegelt die Projektion so, dass die
    Boundary in 2D immer gegen den Uhrzeigersinn (positive Fläche) läuft —
    unabhängig davon, von welcher Seite die Face betrachtet wird."""
    nx = ny = nz = 0.0
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    ax, ay, az = abs(nx), abs(ny), abs(nz)
    if az >= ax and az >= ay:
        return 0, 1, 1.0 if nz >= 0 else -1.0
    if ax >= ay:
        return 1, 2, 1.0 if nx >= 0 else -1.0
    return 2, 0, 1.0 if ny >= 0 else -1.0


def _cross2(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def triangulate_face(
    vertex_ids: list[VertexId],
    positions: Mapping[VertexId, Vec3] | None = None,
) -> list[tuple[VertexId, VertexId, VertexId]]:
    """Triangulierung einer geordneten Face-Boundary (Ear Clipping).

    Mit `positions` (VertexId -> Position) korrekt für einfache
    (nicht selbstschneidende) konkave n-Gons: die Dreiecke überdecken das
    Polygon genau einmal und behalten die Boundary-Orientierung. Die Face wird
    dafür in ihre beste Ebene (dominante Newell-Normale) projiziert; nicht-
    planare Faces werden dort nur approximiert (keine allgemeine
    Nicht-Planar-Triangulierung).

    Konvexe Faces (und alles ohne `positions`) ergeben unverändert den Fan von
    `vertex_ids[0]` — Dreiecke/Quads/konvexe n-Gons ändern sich dadurch nicht.
    Immer n-2 Dreiecke (für n >= 3); leere Liste bei < 3 Vertices.
    """
    n = len(vertex_ids)
    if n < 3:
        return []
    v0 = vertex_ids[0]
    fan = [(v0, vertex_ids[i], vertex_ids[i + 1]) for i in range(1, n - 1)]
    if positions is None or n == 3:
        return fan

    pts3 = [positions[v] for v in vertex_ids]
    u, w, sign = _polygon_plane_axes(pts3)
    # sign < 0 negiert die u-Achse (Spiegelung) -> Orientierung wird positiv.
    pts = [(sign * p[u], p[w]) for p in pts3]

    def cross_at(ring: list[int], k: int) -> float:
        m = len(ring)
        return _cross2(pts[ring[k - 1]], pts[ring[k]], pts[ring[(k + 1) % m]])

    ring = list(range(n))
    if all(cross_at(ring, k) >= -_EAR_EPS for k in range(n)):
        return fan  # konvex (Kollineare erlaubt) -> bisheriges Verhalten

    def is_ear(ring: list[int], k: int) -> bool:
        m = len(ring)
        ia, ib, ic = ring[k - 1], ring[k], ring[(k + 1) % m]
        a, b, c = pts[ia], pts[ib], pts[ic]
        if _cross2(a, b, c) <= _EAR_EPS:
            return False
        for j in ring:
            if j in (ia, ib, ic):
                continue
            p = pts[j]
            if p in (a, b, c):
                continue  # koinzidente Vertices (Bridges) blockieren nicht
            if (
                _cross2(a, b, p) >= -_EAR_EPS
                and _cross2(b, c, p) >= -_EAR_EPS
                and _cross2(c, a, p) >= -_EAR_EPS
            ):
                return False
        return True

    tris: list[tuple[VertexId, VertexId, VertexId]] = []
    while len(ring) > 3:
        m = len(ring)
        k = next((k for k in range(m) if is_ear(ring, k)), None)
        if k is None:
            # Degeneriert / selbstschneidend: kollinearen Vertex abtrennen,
            # sonst den flachsten — terminiert immer, n-2 Dreiecke bleiben.
            k = min(range(m), key=lambda k: abs(cross_at(ring, k)))
        tris.append((vertex_ids[ring[k - 1]], vertex_ids[ring[k]], vertex_ids[ring[(k + 1) % m]]))
        del ring[k]
    tris.append(tuple(vertex_ids[i] for i in ring))  # type: ignore[arg-type]
    return tris


def triangulate_mesh_face(
    mesh: Mesh, face_id: FaceId
) -> list[tuple[VertexId, VertexId, VertexId]]:
    """`triangulate_face` für eine Mesh-Face inkl. Positions-Lookup — der eine
    Ort, an dem Render, Overlay, Normalen und Picking ihre Dreiecke beziehen."""
    boundary = mesh.face_vertices(face_id)
    return triangulate_face(boundary, {v: mesh.vertex_position(v) for v in boundary})


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
            tris = triangulate_face(boundary, positions)
            if not tris:
                self.face_normals[face_id] = (0.0, 0.0, 0.0)
                continue
            # Face-Normale = Normale des ersten Dreiecks (planare Faces
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
            positions = {v: mesh.vertex_position(v) for v in boundary}
            tris = triangulate_face(boundary, positions)
            if not tris:
                self.face_normals[face_id] = (0.0, 0.0, 0.0)
                continue
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
