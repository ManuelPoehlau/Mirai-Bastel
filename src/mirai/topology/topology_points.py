"""Mode-agnostic point helpers for contextual C topology tools (AD-017).

These helpers have no knowledge of Selection, History, or any mode's
pairing/rejection logic. They are used by Split, Edge Connect, Vertex
Connect, and Knife — each mode owns its own pairing and residue semantics.

The one thing the face choice does know is geometry (F2, 2026-09-30): a chord
is only ever created through a face in which it lies entirely
(`chord_validity`). What a mode does when no face qualifies stays the mode's
own rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId, FaceId, VertexId

from .chord_validity import chord_faces


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
    """Connect two vertices through the lowest-id shared face in which the chord is valid.

    A face qualifies when a and b are non-adjacent in it and the straight chord
    lies entirely inside it (`chord_validity.chord_valid_in_face`: not along the
    boundary, not leaving a concave face).

    Returns the new EdgeId on success, or None if no valid face exists (no
    shared face, adjacent in all shared faces, or the chord is not inside any
    of them). The mesh is untouched in that case.

    Deterministic: when multiple qualifying faces exist, the one with the
    lowest integer FaceId is used.
    """
    for fid in chord_faces(mesh, a, b):
        try:
            new_edge, _, _ = mesh.connect_vertices(fid, a, b)
            return new_edge
        except Exception:
            continue
    return None
