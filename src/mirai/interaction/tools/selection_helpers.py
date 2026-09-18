"""Shared selection and pivot helpers for all transform tools.

Consolidates _VertexSelectionView, resolve_selection_vertices(), and
selection_pivot() to eliminate duplication across Move/Rotate/Scale tools.
"""

from __future__ import annotations

from core import Mesh, Selection, SelectionMode, VertexId


class _VertexSelectionView:
    """Minimal selection view for Core operations.

    Core operations need only the set of vertex IDs to transform; the
    visible UI selection remains untouched. Same view for Move/Rotate/Scale.
    """

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = set(vertex_ids)


def resolve_selection_vertices(
    mesh: Mesh, selection: Selection, mode: SelectionMode
) -> set[VertexId]:
    """Resolve current sub-object selection to affected vertex IDs.

    Vertex mode  → selected vertices
    Edge mode    → endpoint vertices of all selected edges
    Face mode    → boundary vertices of all selected faces

    When multiple edges/faces are selected, the result is their union —
    a shared vertex is only moved once.
    """
    if mode == SelectionMode.VERTEX:
        return set(selection.vertices)
    if mode == SelectionMode.EDGE:
        result: set[VertexId] = set()
        for eid in selection.edges:
            result.update(mesh.edge_vertices(eid))
        return result
    if mode == SelectionMode.FACE:
        result = set()
        for fid in selection.faces:
            result.update(mesh.face_vertices(fid))
        return result
    return set()


def selection_pivot(mesh: Mesh, vertex_ids: set[VertexId]) -> tuple[float, float, float]:
    """Centroid of affected vertices (Selection Pivot / Center, V1_SPEC §4)."""
    positions = [mesh.vertex_position(vid) for vid in vertex_ids]
    if not positions:
        raise ValueError("selection_pivot() needs at least one vertex.")
    count = len(positions)
    return (
        sum(p[0] for p in positions) / count,
        sum(p[1] for p in positions) / count,
        sum(p[2] for p in positions) / count,
    )


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Normalize a vector."""
    x, y, z = v
    length = (x * x + y * y + z * z) ** 0.5
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (x / length, y / length, z / length)


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    """Add two vectors."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def selection_normal(derived_geometry, mesh: Mesh, selection: Selection, mode: SelectionMode) -> tuple[float, float, float]:
    """Derive normal from current selection (face/vertex/edge average).

    Face: average of face_normals for selected faces.
    Vertex: average of vertex_normals for selected vertices.
    Edge: average of face_normals of adjacent faces, then averaged across edges.

    Returns (0, 0, 0) if degenerate (opposing normals cancel out). The caller
    must validate this result if non-zero normal is required.
    """
    if mode == SelectionMode.FACE:
        if not selection.faces:
            return (0.0, 0.0, 0.0)
        acc = (0.0, 0.0, 0.0)
        for fid in selection.faces:
            acc = _add(acc, derived_geometry.face_normals.get(fid, (0.0, 0.0, 0.0)))
        count = len(selection.faces)
        avg = (acc[0] / count, acc[1] / count, acc[2] / count)
        return _normalize(avg)

    if mode == SelectionMode.VERTEX:
        if not selection.vertices:
            return (0.0, 0.0, 0.0)
        acc = (0.0, 0.0, 0.0)
        for vid in selection.vertices:
            acc = _add(acc, derived_geometry.vertex_normals.get(vid, (0.0, 0.0, 0.0)))
        count = len(selection.vertices)
        avg = (acc[0] / count, acc[1] / count, acc[2] / count)
        return _normalize(avg)

    if mode == SelectionMode.EDGE:
        if not selection.edges:
            return (0.0, 0.0, 0.0)
        edge_acc = (0.0, 0.0, 0.0)
        for eid in selection.edges:
            # Edge normal = average of face_normals of its (up to two) adjacent faces.
            face_ids = list(derived_geometry.vertex_to_faces.get(mesh.edge_vertices(eid)[0], set()) &
                          derived_geometry.vertex_to_faces.get(mesh.edge_vertices(eid)[1], set()))
            if face_ids:
                face_acc = (0.0, 0.0, 0.0)
                for fid in face_ids:
                    face_acc = _add(face_acc, derived_geometry.face_normals.get(fid, (0.0, 0.0, 0.0)))
                edge_normal = (face_acc[0] / len(face_ids), face_acc[1] / len(face_ids), face_acc[2] / len(face_ids))
            else:
                edge_normal = (0.0, 0.0, 0.0)
            edge_acc = _add(edge_acc, edge_normal)
        count = len(selection.edges)
        avg = (edge_acc[0] / count, edge_acc[1] / count, edge_acc[2] / count)
        return _normalize(avg)

    return (0.0, 0.0, 0.0)
