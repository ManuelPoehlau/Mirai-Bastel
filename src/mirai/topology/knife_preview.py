"""Knife session render data (WP-06 Slice B7; WP-KNIFE-01 S2) — headless, no GPU.

What a running Knife session shows, as plain world positions. Since S2 the
mesh is not cut while clicking (`KnifeTool` keeps a virtual path, resolved at
commit), so the session is drawn from its path:

- `placed_points`: every point placed so far, once each (vertex, edge point
  or — S3 — interior point; an earlier point clicked again, or a closed
  chain's start continuing the next one, is not drawn twice);
- `path_segments`: the segments commit will cut, between their points'
  positions (a skip along an existing edge is not drawn — it cuts nothing;
  a chain closed by clicking its start draws its closing segment);
- `start_point`: the last placed point, where the next segment starts (F3);
- `prospective_point`: the hovered target — the vertex, the point at `t` on
  the hovered edge (G1, also before the first click), the point inside the
  hovered face (S3, the Lab's face-hover marker), or an own point (the snap:
  own points and vertices look the same);
- `target_edge`: the hovered edge;
- `line_preview`: from the start point to the prospective point.

`Application` builds it from `KnifeTool.path` and hands it to the viewport's
tool layers; tests read it directly. Invalid targets never reach this module
as a prospective target — the caller passes `target=None` for them, so there
is no preview point and no line (`PROVISIONAL`, mirrors the Playground's
"invalid → hover cleared").
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId

Vec3 = tuple[float, float, float]
Segment = tuple[Vec3, Vec3]


@dataclass(frozen=True)
class KnifeRenderData:
    start_point: Vec3 | None
    prospective_point: Vec3 | None
    target_edge: Segment | None
    line_preview: Segment | None
    path_segments: tuple[Segment, ...]
    placed_points: tuple[Vec3, ...] = ()


def target_position(mesh, target: dict) -> Vec3 | None:
    """World position of a knife target or path record: the vertex itself, the
    point at `t` along the edge (same lerp the Playground preview uses), or a
    face point's own position (S3). None for other kinds and for handles the
    mesh no longer knows."""
    kind = target.get("kind")
    if kind == "face" and target.get("position") is not None and mesh.is_valid_face(target["face_id"]):
        return tuple(target["position"])
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
    path,
    target: dict | None,
    highlight_edge: EdgeId | None,
) -> KnifeRenderData:
    """`path` = `KnifeTool.path` (records incl. skip breaks); `target` = the
    valid prospective target or None (an own-point target `{"kind": "point",
    "pid"}` is looked up in `path`); `highlight_edge` = the hovered edge.
    Handles the mesh no longer knows are skipped, like the selection overlays
    (AD-001)."""
    positions: dict = {}
    placed: list[Vec3] = []
    segments: list[Segment] = []
    prev = first = None
    for p in path:
        if p["kind"] == "break":
            if p.get("reason") == "closed":
                if p.get("cyclic") and prev is not None and first is not None and prev != first:
                    segments.append((prev, first))
                first = None
            prev = None
            continue
        pos = target_position(mesh, p)
        if pos is None:
            prev = None
            continue
        if p["pid"] not in positions:
            positions[p["pid"]] = pos
            placed.append(pos)
        if prev is not None:
            segments.append((prev, pos))
        if first is None:
            first = pos
        prev = pos
    last = next((p for p in reversed(path) if p["kind"] != "break"), None)
    start_point = positions.get(last["pid"]) if last is not None else None
    if target is None:
        prospective = None
    elif target.get("kind") == "point":
        prospective = positions.get(target.get("pid"))
    else:
        prospective = target_position(mesh, target)
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
    return KnifeRenderData(start_point, prospective, target_edge, line, tuple(segments), tuple(placed))
