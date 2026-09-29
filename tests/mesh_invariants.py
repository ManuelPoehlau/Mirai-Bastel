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


def assert_face_triangulations_sound(mesh: Mesh, *, context: str = "", samples: int = 24) -> None:
    """Geometrische Invariante der Render-/Pick-Triangulierung (planare Faces).

    Für jede Face liefert `viewport.derived.triangulate_mesh_face` Dreiecke, die
    (a) die Boundary-Orientierung behalten (kein geflipptes Dreieck),
    (b) zusammen genau die Polygonfläche haben und
    (c) sich nirgends überlappen und nicht über das Polygon hinausragen
    (Sample-Raster: pro Punkt höchstens ein Dreieck, und genau dann eines,
    wenn der Punkt im Polygon liegt).

    Fängt konkave/gebridgte Konstruktionen ab, deren Triangulierung sonst nur in
    einer Probe (`experiments/topology/face_holes_probe.py`) auffiele. Prüft die
    Triangulierung gegen das Polygon der Face selbst, nicht Face gegen Face.
    """
    from viewport.derived import triangulate_mesh_face

    prefix = f"{context}: " if context else ""

    def area2(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def in_tri(p, tri):
        s = [area2(tri[i], tri[(i + 1) % 3], p) for i in range(3)]
        return all(x > 0 for x in s) or all(x < 0 for x in s)

    def in_poly(p, poly):
        inside = False
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        return inside

    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        pts3 = [mesh.vertex_position(v) for v in boundary]
        n = [0.0, 0.0, 0.0]  # Newell-Normale -> Projektionsebene
        for i, a in enumerate(pts3):
            b = pts3[(i + 1) % len(pts3)]
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        drop = max(range(3), key=lambda k: abs(n[k]))
        u, w = [(1, 2), (2, 0), (0, 1)][drop]
        flip = 1.0 if n[drop] >= 0 else -1.0  # Polygon wird in 2D CCW
        proj = {v: (flip * p[u], p[w]) for v, p in zip(boundary, pts3)}
        poly = [proj[v] for v in boundary]
        poly_area = 0.5 * sum(area2((0.0, 0.0), poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))

        tris = [[proj[v] for v in t] for t in triangulate_mesh_face(mesh, fid)]
        if len(tris) != len(boundary) - 2:
            raise AssertionError(f"{prefix}Face {fid!r}: {len(tris)} Dreiecke für {len(boundary)}-Gon")
        flipped = [t for t in tris if area2(*t) < -1e-12]
        if flipped:
            raise AssertionError(f"{prefix}Face {fid!r}: {len(flipped)} Dreieck(e) gegen die Boundary-Orientierung")
        tri_area = sum(0.5 * area2(*t) for t in tris)
        if abs(tri_area - poly_area) > 1e-9 * max(1.0, abs(poly_area)):
            raise AssertionError(
                f"{prefix}Face {fid!r}: Dreiecksfläche {tri_area:.6f} != Polygonfläche {poly_area:.6f} "
                "(Überlappung oder Überstand)"
            )
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        for i in range(samples):
            for j in range(samples):
                p = (
                    min(xs) + (max(xs) - min(xs)) * (i + 0.437) / samples,
                    min(ys) + (max(ys) - min(ys)) * (j + 0.291) / samples,
                )
                covering = sum(1 for t in tris if in_tri(p, t))
                if covering > 1 or covering != (1 if in_poly(p, poly) else 0):
                    raise AssertionError(
                        f"{prefix}Face {fid!r}: Punkt {p} von {covering} Dreiecken überdeckt "
                        f"(im Polygon: {in_poly(p, poly)})"
                    )
