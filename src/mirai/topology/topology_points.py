"""Mode-agnostic point helpers for contextual C topology tools (AD-017).

These helpers have no knowledge of Selection, History, or any mode's
pairing/rejection logic. They are used by Split, Edge Connect, Vertex
Connect, and Knife — each mode owns its own pairing and residue semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId, FaceId, VertexId


@dataclass(frozen=True)
class VertexPoint:
    vertex_id: VertexId


@dataclass(frozen=True)
class EdgePoint:
    edge_id: EdgeId
    t: float


def resolve_point(mesh, point: VertexPoint | EdgePoint) -> VertexId:
    """Resolve a CutPoint to a VertexId, splitting the edge if necessary.

    For VertexPoint: returns the vertex id directly.
    For EdgePoint: calls mesh.split_edge(edge_id, t) and returns the new vertex.
    """
    if isinstance(point, VertexPoint):
        return point.vertex_id
    mid, _, _ = mesh.split_edge(point.edge_id, point.t)
    return mid


def connect_in_shared_face(mesh, a: VertexId, b: VertexId) -> EdgeId | None:
    """Connect two vertices through the lowest-id shared face where they are non-adjacent.

    Returns the new EdgeId on success, or None if no valid face exists
    (vertices adjacent in all shared faces, or no shared face at all).

    Deterministic: when multiple qualifying faces exist, the one with the
    lowest integer FaceId is used.
    """
    for fid in sorted(mesh.all_face_ids(), key=int):
        boundary = mesh.face_vertices(fid)
        if a not in boundary or b not in boundary:
            continue
        n = len(boundary)
        ia = boundary.index(a)
        ib = boundary.index(b)
        dist = (ib - ia) % n
        if dist == 1 or dist == n - 1:
            continue  # adjacent
        try:
            new_edge, _, _ = mesh.connect_vertices(fid, a, b)
            return new_edge
        except Exception:
            continue
    return None
