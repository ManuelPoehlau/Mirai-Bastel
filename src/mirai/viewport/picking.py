"""Screen-space Picking für die Produktions-Application (Cursor → Element).

Pyglet-/GPU-frei und rein über die öffentliche Core-Query-API implementiert
(lineare Suche, bewusst kein räumlicher Index — siehe VIEWPORT_V02-Scope).

WP-06 B8 (picking speed + occlusion, PROVISIONAL): every picker below takes
two new keyword-only parameters, both opt-in and both defaulting to today's
exact behaviour:

- `cache` (`PickingCache | None`, default `None`): when given, projected
  screen positions and face bboxes come from the cache (`picking_cache.py`,
  refreshed once per camera/mesh state) instead of being recomputed for
  every element on every call. Passing `None` keeps the original per-call
  `camera.project_to_screen(...)` scan unchanged — the Playground's call
  sites all pass no `cache` and are therefore unaffected.
- `occlusion` (`bool`, default `False`): when `True` (and only when
  `display.show_faces` — Shaded/Flat Shaded, decided by the caller, not
  here), a vertex/edge whose picked point is hidden behind a nearer face is
  skipped, exactly as if it weren't under the cursor. `False` reproduces the
  pre-B8 behaviour (no visibility test, only 2D screen distance) — Wireframe
  callers pass `False`.

With both left at their defaults, every function below is behaviourally and
numerically identical to the pre-B8 implementation (same nearest element,
same distance/`t`) — the cache only changes *how* a screen position is
obtained (via a cached dict instead of a fresh `project_to_screen` call),
never *what* value it is, and `occlusion=False` never runs the extra
visibility test.
"""

from __future__ import annotations

import math

from core import EdgeId, FaceId, Mesh, SelectionMode, VertexId

from . import vecmath
from .camera import OrbitCamera
from .picking_cache import PickCache

# Depth tolerance (world units, PROVISIONAL / agent-set, B8) for the
# occlusion ray-vs-mesh test: a face intersection within this margin of the
# picked point's own distance from the eye does not count as "in front of
# it" - without this, floating-point noise on a point's own incident faces
# (excluded explicitly, see `_point_occluded`) or a near-grazing silhouette
# face could otherwise flip a barely-visible element to "occluded".
DEPTH_TOLERANCE = 1e-3


def pick_nearest_vertex(
    camera,
    mesh,
    sx,
    sy,
    width,
    height,
    max_pixel_distance=14.0,
    *,
    cache: PickCache | None = None,
    occlusion: bool = False,
    depth_tolerance: float = DEPTH_TOLERANCE,
):
    if cache is not None:
        cache.refresh(camera, mesh, width, height)
    best_id = None
    best_dist = max_pixel_distance
    for vid in mesh.all_vertex_ids():
        if cache is not None:
            projected = cache.vertex_screen.get(vid)
        else:
            projected = camera.project_to_screen(mesh.vertex_position(vid), width, height)
        if projected is None:
            continue
        px, py = projected
        dist = math.hypot(px - sx, py - sy)
        if dist >= best_dist:
            continue
        if occlusion and _vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance):
            continue
        best_dist = dist
        best_id = vid
    return best_id


def _point_segment_distance(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    qx, qy = ax + t * abx, ay + t * aby
    return math.hypot(px - qx, py - qy)


def _point_segment_distance_t(px, py, ax, ay, bx, by):
    """Like `_point_segment_distance`, also returning `t` (0..1, the closest
    point's position between `a` and `b`) - needed only for the occlusion
    test (B8), which judges edge visibility at that point (handoff scope)."""
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    qx, qy = ax + t * abx, ay + t * aby
    return math.hypot(px - qx, py - qy), t


def pick_nearest_edge(
    camera,
    mesh,
    sx,
    sy,
    width,
    height,
    max_pixel_distance=9.0,
    *,
    cache: PickCache | None = None,
    occlusion: bool = False,
    depth_tolerance: float = DEPTH_TOLERANCE,
):
    if cache is not None:
        cache.refresh(camera, mesh, width, height)
    best_id = None
    best_dist = max_pixel_distance
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        if cache is not None:
            a = cache.vertex_screen.get(va)
            b = cache.vertex_screen.get(vb)
        else:
            a = camera.project_to_screen(mesh.vertex_position(va), width, height)
            b = camera.project_to_screen(mesh.vertex_position(vb), width, height)
        if a is None or b is None:
            continue
        dist, t = _point_segment_distance_t(sx, sy, a[0], a[1], b[0], b[1])
        if dist >= best_dist:
            continue
        if occlusion and _edge_point_occluded(
            camera, mesh, cache, eid, t, width, height, depth_tolerance
        ):
            continue
        best_dist = dist
        best_id = eid
    return best_id


def _ray_triangle_intersection(origin, direction, a, b, c, debug=False):
    eps = 1e-9
    edge1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    edge2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    h = (
        direction[1] * edge2[2] - direction[2] * edge2[1],
        direction[2] * edge2[0] - direction[0] * edge2[2],
        direction[0] * edge2[1] - direction[1] * edge2[0],
    )
    det = edge1[0] * h[0] + edge1[1] * h[1] + edge1[2] * h[2]
    if abs(det) < eps:
        return None
    inv_det = 1.0 / det
    s = (origin[0] - a[0], origin[1] - a[1], origin[2] - a[2])
    u = inv_det * (s[0] * h[0] + s[1] * h[1] + s[2] * h[2])
    if u < -eps or u > 1.0 + eps:
        return None
    q = (
        s[1] * edge1[2] - s[2] * edge1[1],
        s[2] * edge1[0] - s[0] * edge1[2],
        s[0] * edge1[1] - s[1] * edge1[0],
    )
    v = inv_det * (direction[0] * q[0] + direction[1] * q[1] + direction[2] * q[2])
    if v < -eps or u + v > 1.0 + eps:
        return None
    t = inv_det * (edge2[0] * q[0] + edge2[1] * q[1] + edge2[2] * q[2])
    return t if t > eps else None


def _face_boundaries_within_bbox(mesh, cache, sx, sy):
    """Face IDs whose cached screen bbox contains `(sx, sy)`, plus every face
    without a cached bbox (no cache, or an unprojectable boundary vertex -
    B8: always tested exactly, never pre-filtered away)."""
    if cache is None:
        return mesh.all_face_ids()
    candidates = []
    for fid in mesh.all_face_ids():
        bbox = cache.face_bbox.get(fid)
        if bbox is None:
            candidates.append(fid)
            continue
        minx, miny, maxx, maxy = bbox
        if minx <= sx <= maxx and miny <= sy <= maxy:
            candidates.append(fid)
    return candidates


def pick_face(camera, mesh, sx, sy, width, height, debug=False, *, cache: PickCache | None = None):
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    if debug:
        print(f"[FACE DEBUG] cursor=({sx:.1f}, {sy:.1f})")
        print(f"[FACE DEBUG] ray origin={origin}")
        print(f"[FACE DEBUG] ray direction={direction}")

    if cache is not None:
        cache.refresh(camera, mesh, width, height)
    face_ids = _face_boundaries_within_bbox(mesh, cache, sx, sy)

    best_id = None
    best_t = float("inf")
    for fid in face_ids:
        boundary = mesh.face_vertices(fid)
        if len(boundary) < 3:
            continue
        p0 = mesh.vertex_position(boundary[0])
        for i in range(1, len(boundary) - 1):
            p1 = mesh.vertex_position(boundary[i])
            p2 = mesh.vertex_position(boundary[i + 1])
            t = _ray_triangle_intersection(origin, direction, p0, p1, p2)
            if debug:
                print(f"[FACE DEBUG] face={fid} tri={i-1} p0={p0} p1={p1} p2={p2} t={t}")
            if t is not None and t < best_t:
                best_t = t
                best_id = fid

    if debug:
        print(f"[FACE DEBUG] result face={best_id} t={best_t}")
    return best_id


# -- B8: occlusion (Shaded/Flat Shaded only - the caller decides via
# `occlusion=`, this module has no `DisplayState` dependency) ----------------


def _point_occluded(camera, mesh, cache, point, width, height, exclude_faces, depth_tolerance):
    """True if some face other than `exclude_faces` lies strictly closer to
    the camera than `point` along the ray from the eye through it (a small
    `depth_tolerance` keeps silhouette elements pickable, per the handoff's
    occlusion rule)."""
    eye = camera.eye()
    to_point = vecmath.sub(point, eye)
    dist = vecmath.length(to_point)
    if dist <= 1e-9:
        return False
    direction = vecmath.scale(to_point, 1.0 / dist)
    screen = camera.project_to_screen(point, width, height)

    for fid in mesh.all_face_ids():
        if fid in exclude_faces:
            continue
        bbox = cache.face_bbox.get(fid) if cache is not None else None
        if bbox is not None and screen is not None:
            minx, miny, maxx, maxy = bbox
            if screen[0] < minx or screen[0] > maxx or screen[1] < miny or screen[1] > maxy:
                continue
        boundary = mesh.face_vertices(fid)
        if len(boundary) < 3:
            continue
        p0 = mesh.vertex_position(boundary[0])
        for i in range(1, len(boundary) - 1):
            p1 = mesh.vertex_position(boundary[i])
            p2 = mesh.vertex_position(boundary[i + 1])
            t = _ray_triangle_intersection(eye, direction, p0, p1, p2)
            if t is not None and t < dist - depth_tolerance:
                return True
    return False


def _incident_faces_of_vertex(mesh, vid):
    faces = set()
    for eid in mesh.vertex_edges(vid):
        faces.update(mesh.edge_faces(eid))
    return faces


def _vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance):
    point = mesh.vertex_position(vid)
    exclude = _incident_faces_of_vertex(mesh, vid)
    return _point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


def _edge_point_occluded(camera, mesh, cache, eid, t, width, height, depth_tolerance):
    va, vb = mesh.edge_vertices(eid)
    pa, pb = mesh.vertex_position(va), mesh.vertex_position(vb)
    point = (
        pa[0] + (pb[0] - pa[0]) * t,
        pa[1] + (pb[1] - pa[1]) * t,
        pa[2] + (pb[2] - pa[2]) * t,
    )
    exclude = set(mesh.edge_faces(eid))
    return _point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


def pick_component(
    camera,
    mesh,
    mode,
    sx,
    sy,
    width,
    height,
    *,
    cache: PickCache | None = None,
    occlusion: bool = False,
    depth_tolerance: float = DEPTH_TOLERANCE,
):
    """Picker nach Selection-Modus (WP-06 B5b, E43): nächster Vertex, nächste
    Edge oder vorderste Face unter dem Cursor (Playground `selector.
    pick_component`, dort mit der ganzen Selection statt nur dem Modus).
    `cache`/`occlusion` siehe Moduldocstring (WP-06 B8)."""
    if mode is SelectionMode.VERTEX:
        return pick_nearest_vertex(
            camera, mesh, sx, sy, width, height,
            cache=cache, occlusion=occlusion, depth_tolerance=depth_tolerance,
        )
    if mode is SelectionMode.EDGE:
        return pick_nearest_edge(
            camera, mesh, sx, sy, width, height,
            cache=cache, occlusion=occlusion, depth_tolerance=depth_tolerance,
        )
    return pick_face(camera, mesh, sx, sy, width, height, cache=cache)
