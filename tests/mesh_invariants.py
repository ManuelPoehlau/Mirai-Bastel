"""Phase A: Katalog und Prüfhilfe für dokumentierte Mesh-Invarianten.

Quellen (keine erfundenen Regeln):
- src/core/mesh.py (Architekturvertrag, Mutations-ID-Kontinuität)
- docs/V1_SPEC.md §7, §8
- docs/architecture/V1_CORE_REVIEW_CLAUDE_003.md (AD-002 Query-API)

Geprüft wird ausschließlich über die öffentliche Query-API.
"""

from __future__ import annotations

from core.ids import EdgeId, FaceId, VertexId
from core.mesh import Mesh


def assert_mesh_invariants(mesh: Mesh, *, context: str = "") -> None:
    """Strukturelle Invarianten, die jede Mutation einhalten muss.

    Verletzungen deuten auf einen Core-Bug hin — nicht auf fehlende Spezifikation.
    """
    prefix = f"{context}: " if context else ""

    valid_vertices = set(mesh.all_vertex_ids())
    valid_edges = set(mesh.all_edge_ids())
    valid_faces = set(mesh.all_face_ids())

    for vid in valid_vertices:
        if not mesh.is_valid_vertex(vid):
            raise AssertionError(f"{prefix}Vertex {vid!r} in all_vertex_ids(), aber is_valid_vertex() ist False")

    for eid in valid_edges:
        if not mesh.is_valid_edge(eid):
            raise AssertionError(f"{prefix}Edge {eid!r} in all_edge_ids(), aber is_valid_edge() ist False")
        v0, v1 = mesh.edge_vertices(eid)
        if v0 not in valid_vertices or v1 not in valid_vertices:
            raise AssertionError(
                f"{prefix}Edge {eid!r} referenziert ungültige Endpunkte {v0!r}, {v1!r}"
            )
        if v0 == v1:
            raise AssertionError(f"{prefix}Edge {eid!r} ist ein Self-Loop ({v0!r})")

    for fid in valid_faces:
        if not mesh.is_valid_face(fid):
            raise AssertionError(f"{prefix}Face {fid!r} in all_face_ids(), aber is_valid_face() ist False")
        boundary = mesh.face_vertices(fid)
        if len(boundary) < 3:
            raise AssertionError(f"{prefix}Face {fid!r} hat weniger als 3 Boundary-Vertices")
        if len(boundary) != len(set(boundary)):
            raise AssertionError(
                f"{prefix}Face {fid!r} enthält doppelte Vertex-Referenzen in der Boundary"
            )
        for v in boundary:
            if v not in valid_vertices:
                raise AssertionError(f"{prefix}Face {fid!r} referenziert ungültiges Vertex {v!r}")

        edges = mesh.face_edges(fid)
        if len(edges) != len(boundary):
            raise AssertionError(
                f"{prefix}Face {fid!r}: face_edges() Länge {len(edges)} != Boundary {len(boundary)}"
            )
        for eid in edges:
            if eid not in valid_edges:
                raise AssertionError(f"{prefix}Face {fid!r} referenziert unbekannte Edge {eid!r}")
            if fid not in mesh.edge_faces(eid):
                raise AssertionError(
                    f"{prefix}Edge {eid!r} listet Face {fid!r} nicht in edge_faces()"
                )

    for eid in valid_edges:
        adjacent = mesh.edge_faces(eid)
        if len(adjacent) > 2:
            raise AssertionError(
                f"{prefix}Edge {eid!r} ist an mehr als 2 Faces angehängt ({len(adjacent)})"
            )
        for fid in adjacent:
            if fid not in valid_faces:
                raise AssertionError(f"{prefix}Edge {eid!r} referenziert ungültige Face {fid!r}")
            if eid not in mesh.face_edges(fid):
                raise AssertionError(
                    f"{prefix}Face {fid!r} listet Edge {eid!r} nicht in face_edges()"
                )

    # Keine Edge darf einen Vertex referenzieren, der nicht in all_vertex_ids() ist.
    for eid in valid_edges:
        v0, v1 = mesh.edge_vertices(eid)
        for v in (v0, v1):
            if not mesh.is_valid_vertex(v):
                raise AssertionError(
                    f"{prefix}Verbleibende Edge {eid!r} referenziert ungültiges Vertex {v!r} "
                    "(collapse_edge-Invariante verletzt)"
                )


def assert_id_monotonic(new_id: VertexId | EdgeId | FaceId, previous: VertexId | EdgeId | FaceId) -> None:
    """AD-001: neu vergebene IDs sind strikt größer als die zuvor höchste."""
    if int(new_id) <= int(previous):
        raise AssertionError(f"ID nicht monoton: {new_id!r} folgt auf {previous!r}")


def build_quad_mesh() -> tuple[Mesh, tuple[VertexId, VertexId, VertexId, VertexId], FaceId]:
    """Einzelnes Quad in der XY-Ebene — Standard-Fixture für Mutations-Tests."""
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    face = mesh.add_face([v0, v1, v2, v3])
    assert_mesh_invariants(mesh, context="build_quad_mesh")
    return mesh, (v0, v1, v2, v3), face
