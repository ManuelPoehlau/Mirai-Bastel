"""Knife picking — resolve screen cursor to knife target (AD-017 §1.8).

Moved (not copied) from `playground/topology_tools/knife_pick.py` in WP-06
Slice B7; `project_locked_edge` was extracted from `playground/window.py`
(`_knife_project_locked_edge`, F1 edge lock) in the same slice. Logic
unchanged.

Reuses src/mirai/viewport/picking.py without modification.

WP-KNIFE-01 S2: `snap_own_point` adds the session's own edge points (not
mesh vertices before commit) as targets, so a click on one reaches the very
point again — what the real-cut Knife got from the vertex it had split there.
WP-KNIFE-01 S3: a face hit carries the hit position and its screen clearance
from the face's edges (moved from the Knife Face Lab's `knife_face_pick`, H1 of
`KNIFE_FACE_CUT_DISCOVERY.md`); the session's own interior points snap too.
Priority order: vertex hit first; else edge hit with perspective-correct 3D t;
endpoint threshold → treat as vertex; else face hit → a face point (the Knife
refuses it closer than `EDGE_MARGIN_PX` to an edge: there the edge is the
target, which the 9 px edge pick already returns when it is visible);
else "outside mesh".

The 3D t is computed as the closest point between the view ray and the edge
segment in world space (not screen space).
"""

from __future__ import annotations

import math

from ..viewport.picking import (
    DEPTH_TOLERANCE,
    edge_point_occluded,
    face_edge_distance_px,
    face_hit_position,
    pick_face,
    pick_nearest_edge,
    pick_nearest_vertex,
    point_occluded,
)
from ..viewport.picking_cache import PickCache

# Same radius as the vertex pick (`pick_nearest_vertex`'s default; Q5's SNAP_PX).
OWN_POINT_SNAP_PX = 14.0

# H3 (KNIFE_FACE_CUT_DISCOVERY.md): the edge pick radius is 9 px — an interior point needs at least
# that much clearance from every edge of its face, or "on the edge" and "inside" cannot be told apart.
EDGE_MARGIN_PX = 9.0

ENDPOINT_THRESHOLD = 0.05  # t values within this threshold of 0 or 1 snap to vertex

_Vec3 = tuple[float, float, float]


def _dot3(a: _Vec3, b: _Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub3(a: _Vec3, b: _Vec3) -> _Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _edge_t_3d(origin: _Vec3, direction: _Vec3, p0: _Vec3, p1: _Vec3) -> float:
    """Perspective-correct t: closest point on edge segment to view ray.

    Returns t in [0, 1] where t=0 is p0, t=1 is p1.

    Convention (standard closest-point-of-two-lines, Ericson §5.1.8):
      ray     P(s) = origin + s * direction
      segment Q(t) = p0 + t * d
      w0 = origin - p0
      a = direction·direction, b = direction·d, c = d·d,
      d_val = d·w0, e = direction·w0, denom = a*c - b*b
      t = (a*e - b*d_val) / denom

    Note: in the variable names used below, `a` is the SEGMENT dot product and
    `c` is the RAY dot product, so the segment parameter reads
    `(c * d_val - b * e) / denom`. Using `(b * e - c * d_val)` instead returns
    the negated parameter, which clamps to 0.0 for every click and makes every
    edge hit snap to p0.
    """
    d = _sub3(p1, p0)
    w = _sub3(origin, p0)
    a = _dot3(d, d)
    b = _dot3(d, direction)
    c = _dot3(direction, direction)
    d_val = _dot3(d, w)
    e = _dot3(direction, w)
    denom = a * c - b * b
    if abs(denom) < 1e-10:
        return 0.0
    t = (c * d_val - b * e) / denom
    return max(0.0, min(1.0, t))


edge_t_3d = _edge_t_3d  # public name for the planner (`knife_planner`, WP-KNIFE-01 S4)


def knife_pick(
    camera,
    mesh,
    sx: float,
    sy: float,
    width: int,
    height: int,
    debug: bool = False,
    *,
    cache: PickCache | None = None,
    occlusion: bool = False,
) -> dict:
    """Resolve cursor position to a knife target.

    Returns one of:
      {"kind": "vertex", "vertex_id": vid}
      {"kind": "edge", "edge_id": eid, "t": float}  — t in (THRESHOLD, 1-THRESHOLD)
      {"kind": "face", "face_id": fid, "position": (x, y, z), "distance_px": float | None}
                                                     — the hit on the face, its clearance from the edges
      {"kind": "outside"}

    debug=True prints the temporary [KNIFE] pick trace (AD-017 diagnosis).
    Hover calls must pass debug=False to avoid flooding the console.

    `cache`/`occlusion` (WP-06 B8, PROVISIONAL): forwarded unchanged to the
    three `mirai.viewport.picking` calls below — see that module's docstring.
    Both default to `None`/`False`, reproducing the pre-B8 behaviour exactly
    (callers that pass neither are unaffected; the Playground window passes
    the shared `PlaygroundApp.pick_cache` with occlusion on while faces are shown).
    """
    if debug:
        print(f"[KNIFE] pick cursor=({sx:.1f},{sy:.1f})")

    # Vertex hit first
    vid = pick_nearest_vertex(camera, mesh, sx, sy, width, height, cache=cache, occlusion=occlusion)
    if debug:
        print(f"[KNIFE] pick_nearest_vertex -> vertex:{int(vid)}" if vid is not None
              else "[KNIFE] pick_nearest_vertex -> None")
    if vid is not None:
        return {"kind": "vertex", "vertex_id": vid}

    # Edge hit with perspective-correct t
    eid = pick_nearest_edge(camera, mesh, sx, sy, width, height, cache=cache, occlusion=occlusion)
    if debug:
        print(f"[KNIFE] pick_nearest_edge -> edge:{int(eid)}" if eid is not None
              else "[KNIFE] pick_nearest_edge -> None")
    if eid is not None:
        origin, direction = camera.screen_to_ray(sx, sy, width, height)
        va, vb = mesh.edge_vertices(eid)
        p0 = mesh.vertex_position(va)
        p1 = mesh.vertex_position(vb)
        t = _edge_t_3d(origin, direction, p0, p1)
        if debug:
            print(f"[KNIFE] EdgePoint t={t:.6f} on edge:{int(eid)} "
                  f"({int(va)}-{int(vb)}), snap thresholds {ENDPOINT_THRESHOLD}/{1.0 - ENDPOINT_THRESHOLD}")
        if t <= ENDPOINT_THRESHOLD:
            if debug:
                print(f"[KNIFE] t<=threshold -> snap to vertex:{int(va)}")
            return {"kind": "vertex", "vertex_id": va}
        if t >= 1.0 - ENDPOINT_THRESHOLD:
            if debug:
                print(f"[KNIFE] t>=1-threshold -> snap to vertex:{int(vb)}")
            return {"kind": "vertex", "vertex_id": vb}
        return {"kind": "edge", "edge_id": eid, "t": t}

    # Face hit → a face point: where the ray hits it, and how far the cursor is from its edges.
    # The face is the nearest one along the ray, so it needs no occlusion pass of its own.
    fid = pick_face(camera, mesh, sx, sy, width, height, cache=cache)
    if debug:
        print(f"[KNIFE] pick_face -> face:{int(fid)}" if fid is not None
              else "[KNIFE] pick_face -> None")
    if fid is not None:
        pos = face_hit_position(camera, mesh, fid, sx, sy, width, height)
        if pos is None:  # numerically degenerate: the face was hit a moment ago
            return {"kind": "outside"}
        dist = face_edge_distance_px(camera, mesh, fid, sx, sy, width, height, cache=cache)
        if debug:
            print(f"[KNIFE] face point clearance={dist}px (margin {EDGE_MARGIN_PX})")
        return {"kind": "face", "face_id": fid, "position": pos, "distance_px": dist}

    if debug:
        print("[KNIFE] pick -> outside")
    return {"kind": "outside"}


def project_locked_edge(camera, mesh, x, y, width, height, locked_eid) -> dict:
    """Project cursor ray onto a locked edge, applying endpoint-threshold snap.

    Returns a target dict identical to knife_pick() output but always referencing
    the locked edge — the cursor may be anywhere on screen (F1 edge lock, F2
    vertex-kind release: near an endpoint the target becomes that vertex).
    """
    origin, direction = camera.screen_to_ray(x, y, width, height)
    va, vb = mesh.edge_vertices(locked_eid)
    p0 = mesh.vertex_position(va)
    p1 = mesh.vertex_position(vb)
    t = _edge_t_3d(origin, direction, p0, p1)
    if t <= ENDPOINT_THRESHOLD:
        return {"kind": "vertex", "vertex_id": va}
    if t >= 1.0 - ENDPOINT_THRESHOLD:
        return {"kind": "vertex", "vertex_id": vb}
    return {"kind": "edge", "edge_id": locked_eid, "t": t}


def snap_own_point(
    camera,
    mesh,
    sx: float,
    sy: float,
    width: int,
    height: int,
    points,
    target: dict,
    *,
    cache: PickCache | None = None,
    occlusion: bool = False,
) -> dict:
    """`target` (a `knife_pick` result), or `{"kind": "point", "pid": ...}` when the
    cursor is within the vertex pick radius of one of the session's own edge or
    interior points (`points`: `KnifeTool.points`). Own points behave like the
    vertices they become at commit: they beat an edge or face hit, a mesh vertex
    wins only when it is at least as near on screen (same nearest-wins rule), a
    hidden one is skipped when `occlusion` is on. Vertex points need nothing here —
    they are mesh vertices and `knife_pick` returns them already."""
    best = None
    for p in points:
        if p["kind"] == "edge":
            if not mesh.is_valid_edge(p["edge_id"]):
                continue
            va, vb = mesh.edge_vertices(p["edge_id"])
            p0, p1 = mesh.vertex_position(va), mesh.vertex_position(vb)
            pos = tuple(p0[i] + p["t"] * (p1[i] - p0[i]) for i in range(3))
        elif p["kind"] == "face":
            if not mesh.is_valid_face(p["face_id"]):
                continue
            pos = p["position"]
        else:
            continue
        projected = camera.project_to_screen(pos, width, height)
        if projected is None:
            continue
        dist = math.hypot(projected[0] - sx, projected[1] - sy)
        if dist >= OWN_POINT_SNAP_PX or (best is not None and dist >= best[0]):
            continue
        if occlusion and _own_point_hidden(camera, mesh, cache, p, pos, width, height):
            continue
        best = (dist, p)
    if best is None:
        return target
    if target.get("kind") == "vertex":
        projected = camera.project_to_screen(mesh.vertex_position(target["vertex_id"]), width, height)
        if projected is not None and math.hypot(projected[0] - sx, projected[1] - sy) <= best[0]:
            return target
    return {"kind": "point", "pid": best[1]["pid"]}


def _own_point_hidden(camera, mesh, cache, p: dict, pos, width: int, height: int) -> bool:
    """The picks' occlusion rule for an own point: hidden behind a face that does not hold it."""
    if p["kind"] == "edge":
        return edge_point_occluded(camera, mesh, cache, p["edge_id"], p["t"], width, height, DEPTH_TOLERANCE)
    return point_occluded(camera, mesh, cache, pos, width, height, {p["face_id"]}, DEPTH_TOLERANCE)
