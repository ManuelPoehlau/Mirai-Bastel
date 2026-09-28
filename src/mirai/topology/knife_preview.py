"""Knife session render data (WP-06 Slice B7) — headless, no GPU.

What a running Knife session shows, as plain world positions: the start
vertex (F3), the prospective point (hover or press-slide, Variant A/B), the
hovered or locked edge (F1), the line preview from the start to the
prospective point (new in B7, Blender-knife style) and the session's
connecting edges so far. `Application` builds it from `KnifeTool` state and
hands it to the viewport's tool layers; tests read it directly.

Invalid targets never reach this module as a prospective target — the caller
passes `target=None` for them, so there is no preview point and no line
(`PROVISIONAL`, mirrors the Playground's "invalid → hover cleared").
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId, VertexId

Vec3 = tuple[float, float, float]
Segment = tuple[Vec3, Vec3]


@dataclass(frozen=True)
class KnifeRenderData:
    start_point: Vec3 | None
    prospective_point: Vec3 | None
    target_edge: Segment | None
    line_preview: Segment | None
    path_segments: tuple[Segment, ...]


def target_position(mesh, target: dict) -> Vec3 | None:
    """World position of a knife target: the vertex itself, or the point at
    `t` along the edge (same lerp the Playground preview uses). None for other
    kinds and for handles the mesh no longer knows."""
    kind = target.get("kind")
    if kind == "vertex" and mesh.is_valid_vertex(target["vertex_id"]):
        return tuple(mesh.vertex_position(target["vertex_id"]))
    if kind == "edge" and mesh.is_valid_edge(target["edge_id"]):
        va, vb = mesh.edge_vertices(target["edge_id"])
        p0 = mesh.vertex_position(va)
        p1 = mesh.vertex_position(vb)
        t = target["t"]
        return tuple(p0[i] + t * (p1[i] - p0[i]) for i in range(3))
    return None


def _segment(mesh, edge_id: EdgeId) -> Segment:
    va, vb = mesh.edge_vertices(edge_id)
    return (tuple(mesh.vertex_position(va)), tuple(mesh.vertex_position(vb)))


def build_knife_render_data(
    mesh,
    start: VertexId | None,
    target: dict | None,
    highlight_edge: EdgeId | None,
    path_edges,
) -> KnifeRenderData:
    """`target` = the valid prospective target or None; `highlight_edge` =
    hovered (valid) or locked edge. Handles the mesh no longer knows are
    skipped, like the selection overlays (AD-001)."""
    start_point = (
        tuple(mesh.vertex_position(start))
        if start is not None and mesh.is_valid_vertex(start)
        else None
    )
    prospective = target_position(mesh, target) if target is not None else None
    target_edge = (
        _segment(mesh, highlight_edge)
        if highlight_edge is not None and mesh.is_valid_edge(highlight_edge)
        else None
    )
    line = (
        (start_point, prospective)
        if start_point is not None and prospective is not None
        else None
    )
    path = tuple(_segment(mesh, e) for e in path_edges if mesh.is_valid_edge(e))
    return KnifeRenderData(start_point, prospective, target_edge, line, path)
