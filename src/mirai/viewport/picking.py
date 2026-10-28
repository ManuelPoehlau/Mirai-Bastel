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

WP-KNIFE-01 S3 (additive): the occlusion helpers are public
(`point_occluded`, `vertex_occluded`, `edge_point_occluded`; the private names
stay as aliases), and a face hit has a position (`face_hit_position`, H1 of
`KNIFE_FACE_CUT_DISCOVERY.md`) and a screen clearance from the face's edges
(`face_edge_distance_px`) — both moved from the Knife Face Lab, used by
`mirai.topology.knife_pick`. `pick_face` keeps its signature and result.

With both left at their defaults, every function below is behaviourally and
numerically identical to the pre-B8 implementation (same nearest element,
same distance/`t`) — the cache only changes *how* a screen position is
obtained (via a cached dict instead of a fresh `project_to_screen` call),
never *what* value it is, and `occlusion=False` never runs the extra
visibility test.

WP-VIEW-PERF-01 Slice 1 (no behaviour change, `tests/test_picking_equivalence.py`
compares against the pre-PERF code): the vertex/edge scans compare squared
distances (and screen bboxes for edges) and compute the exact `hypot` distance
only for the few candidates in range; occlusion is tested nearest-first and
stops at the first visible candidate (`_nearest_visible`); with a cache, a
vertex's incident faces come from `PickCache.vertex_faces` instead of the
O(E) `core.Mesh.vertex_edges` scan.

WP-VIEW-PERF-01 Slice 2 (no behaviour change, same tests): the occlusion test visits only
the faces of the point's cell in the cache's screen grid of face bboxes
(`PickCache.face_grid`, the "simple CPU spatial grid" of `VIEWPORT_V02` §4.6, camera-dependent,
no world index); `point_occlusion_test` runs many tests under one camera state (Box Select).
The vertex / edge scans stay linear.
"""

from __future__ import annotations

import math

from core import EdgeId, FaceId, Mesh, SelectionMode, VertexId
from viewport.derived import triangulate_mesh_face

from . import vecmath
from .camera import OrbitCamera
from .picking_cache import PickCache

# Depth tolerance (world units, PROVISIONAL / agent-set, B8) for the
# occlusion ray-vs-mesh test: a face intersection within this margin of the
# picked point's own distance from the eye does not count as "in front of
# it" - without this, floating-point noise on a point's own incident faces
# (excluded explicitly, see `point_occluded`) or a near-grazing silhouette
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
        get = cache.vertex_screen.get
    else:
        def get(vid):
            return camera.project_to_screen(mesh.vertex_position(vid), width, height)
    # WP-VIEW-PERF-01: squared distances in the scan (`math.hypot` costs ~7.5 us per call on
    # the reference PC), with a relative slack so no vertex the exact `hypot` test below keeps
    # is dropped by rounding.
    limit_sq = max_pixel_distance * max_pixel_distance * (1.0 + 1e-9)
    in_range = []
    for vid in mesh.all_vertex_ids():
        projected = get(vid)
        if projected is None:
            continue
        dx = projected[0] - sx
        dy = projected[1] - sy
        if dx * dx + dy * dy <= limit_sq:
            in_range.append((math.hypot(dx, dy), vid))
    return _nearest_visible(
        in_range,
        max_pixel_distance,
        (lambda vid: vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance))
        if occlusion else None,
    )


def _nearest_visible(candidates, max_pixel_distance, occluded):
    """The element of the nearest visible `(dist, element, ...)` candidate under
    `max_pixel_distance` (None if there is none), ties in mesh order.

    WP-VIEW-PERF-01: the pre-PERF scan tested occlusion in mesh order for every candidate
    closer than the best visible one so far, so every hidden element under the cursor cost
    one full test (16-277 per pick on a 20k-vertex mesh). Testing nearest-first and stopping
    at the first visible one returns the same element - the nearest visible one, the earliest
    in mesh order on a tie (the sort is stable) - with ~1 test. `occluded(element[, extra])`
    is called with the candidate's remaining fields; None = no occlusion test."""
    candidates = [c for c in candidates if c[0] < max_pixel_distance]
    candidates.sort(key=_by_distance)
    for candidate in candidates:
        if occluded is None or not occluded(*candidate[1:]):
            return candidate[1]
    return None


def _by_distance(candidate):
    return candidate[0]


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
        get = cache.vertex_screen.get
    else:
        def get(vid):
            return camera.project_to_screen(mesh.vertex_position(vid), width, height)
    # A segment whose screen bbox is farther than `reach` from the cursor on one axis is out
    # of range (its distance is at least that axis gap); the margin covers rounding, the exact
    # distance below decides.
    reach = max_pixel_distance + 1e-6
    in_range = []
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        a = get(va)
        b = get(vb)
        if a is None or b is None:
            continue
        ax, ay = a
        bx, by = b
        if ax < bx:
            if sx < ax - reach or sx > bx + reach:
                continue
        elif sx < bx - reach or sx > ax + reach:
            continue
        if ay < by:
            if sy < ay - reach or sy > by + reach:
                continue
        elif sy < by - reach or sy > ay + reach:
            continue
        dist, t = _point_segment_distance_t(sx, sy, ax, ay, bx, by)
        in_range.append((dist, eid, t))
    return _nearest_visible(
        in_range,
        max_pixel_distance,
        (lambda eid, t: edge_point_occluded(camera, mesh, cache, eid, t, width, height, depth_tolerance))
        if occlusion else None,
    )


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
    hidden_faces = cache.hidden_faces
    for fid in mesh.all_face_ids():
        if fid in hidden_faces:
            continue  # Hide / Isolate: a face the artist cannot see is not picked
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
        for i, tri in enumerate(triangulate_mesh_face(mesh, fid)):
            p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
            t = _ray_triangle_intersection(origin, direction, p0, p1, p2)
            if debug:
                print(f"[FACE DEBUG] face={fid} tri={i} p0={p0} p1={p1} p2={p2} t={t}")
            if t is not None and t < best_t:
                best_t = t
                best_id = fid

    if debug:
        print(f"[FACE DEBUG] result face={best_id} t={best_t}")
    return best_id


def face_hit_position(camera, mesh, face_id, sx, sy, width, height):
    """World position where the cursor ray hits `face_id` (nearest hit on its
    fan triangulation — the triangles `pick_face` tests, so a non-planar quad
    or a concave face is hit where `pick_face` hit it). None if the ray misses
    the face. Moved from the Knife Face Lab (`face_interior_hit`, WP-KNIFE-01
    S3) unchanged."""
    hit = face_hit(camera, mesh, face_id, sx, sy, width, height)
    return None if hit is None else hit[0]


def face_hit(camera, mesh, face_id, sx, sy, width, height):
    """`(position, origin)` of the cursor ray's nearest hit on `face_id`, or None: the position is
    `face_hit_position`'s, the origin the barycentric weights of the hit triangle over its three
    corners — corners of the face itself (AD-025 §4.1 Phase 5: a Knife interior point's value in every
    point layer, exactly on the target's drawn surface)."""
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    best_t = best_tri = None
    for tri in triangulate_mesh_face(mesh, face_id):
        p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
        t = _ray_triangle_intersection(origin, direction, p0, p1, p2)
        if t is not None and (best_t is None or t < best_t):
            best_t, best_tri = t, tri
    if best_t is None:
        return None
    position = (
        origin[0] + best_t * direction[0],
        origin[1] + best_t * direction[1],
        origin[2] + best_t * direction[2],
    )
    return position, triangle_origin(mesh, best_tri, position)


def triangle_origin(mesh, tri, position):
    """Barycentric weights of `position` in the triangle `tri` (three vertex ids), as a
    `VertexOrigin` `((a, wa), (b, wb), (c, wc))` with wa = 1 - wb - wc. `position` is expected in the
    triangle's plane (a ray hit); off the plane its projection counts. A degenerate triangle gives
    the copy of its first corner."""
    a, b, c = tri
    pa, pb, pc = (mesh.vertex_position(v) for v in tri)
    e1 = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
    e2 = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
    ep = (position[0] - pa[0], position[1] - pa[1], position[2] - pa[2])
    d11 = e1[0] * e1[0] + e1[1] * e1[1] + e1[2] * e1[2]
    d12 = e1[0] * e2[0] + e1[1] * e2[1] + e1[2] * e2[2]
    d22 = e2[0] * e2[0] + e2[1] * e2[1] + e2[2] * e2[2]
    dp1 = ep[0] * e1[0] + ep[1] * e1[1] + ep[2] * e1[2]
    dp2 = ep[0] * e2[0] + ep[1] * e2[1] + ep[2] * e2[2]
    denom = d11 * d22 - d12 * d12
    if denom <= 1e-300:
        return ((a, 1.0),)
    wb = (d22 * dp1 - d12 * dp2) / denom
    wc = (d11 * dp2 - d12 * dp1) / denom
    return ((a, 1.0 - wb - wc), (b, wb), (c, wc))


def face_point_origin(mesh, face_id, position):
    """The camera-free counterpart of `face_hit`'s origin for a face point that came without one (a
    host or a headless session): the barycentric weights in the triangle of the face's triangulation
    that holds `position` — the least outside, then the nearest to its plane (on a fold both are hit,
    and both give the same value on the shared diagonal)."""
    best = None
    for tri in triangulate_mesh_face(mesh, face_id):
        weights = triangle_origin(mesh, tri, position)
        if len(weights) == 1:
            continue
        outside = max(0.0, -min(w for _, w in weights))
        p = [mesh.vertex_position(v) for v in tri]
        back = tuple(sum(w * q[i] for (_, w), q in zip(weights, p)) for i in range(3))
        key = (outside, math.dist(back, position))
        if best is None or key < best[0]:
            best = (key, weights)
    if best is None:
        return ((mesh.face_vertices(face_id)[0], 1.0),)
    return best[1]


def face_edge_distance_px(camera, mesh, face_id, sx, sy, width, height, *, cache: PickCache | None = None):
    """Screen distance from the cursor to the nearest boundary edge of
    `face_id` (None if no edge projects) — the Knife's 9 px clearance for a
    face-interior point. The hit position lies under the cursor, so this is
    the cursor's own distance to each projected edge. Moved from the Knife
    Face Lab (`min_edge_distance_px`, WP-KNIFE-01 S3); `cache` only changes
    how the screen positions are obtained, not their values."""
    if cache is not None:
        cache.refresh(camera, mesh, width, height)
    boundary = mesh.face_vertices(face_id)
    n = len(boundary)
    best = None
    for i in range(n):
        if cache is not None:
            a = cache.vertex_screen.get(boundary[i])
            b = cache.vertex_screen.get(boundary[(i + 1) % n])
        else:
            a = camera.project_to_screen(mesh.vertex_position(boundary[i]), width, height)
            b = camera.project_to_screen(mesh.vertex_position(boundary[(i + 1) % n]), width, height)
        if a is None or b is None:
            continue
        d = _point_segment_distance(sx, sy, a[0], a[1], b[0], b[1])
        if best is None or d < best:
            best = d
    return best


# -- B8: occlusion (Shaded/Flat Shaded only - the caller decides via
# `occlusion=`, this module has no `DisplayState` dependency) ----------------


def point_occluded(camera, mesh, cache, point, width, height, exclude_faces, depth_tolerance=DEPTH_TOLERANCE):
    """True if some face other than `exclude_faces` lies strictly closer to
    the camera than `point` along the view ray through it (from the eye; in ortho the
    parallel ray, `_ray_origin`) (a small
    `depth_tolerance` keeps silhouette elements pickable, per the handoff's
    occlusion rule).

    WP-VIEW-PERF-01 Slice 2: with a cache refreshed for `mesh` and its `face_grid` built
    (after a few full scans in one camera state), only the faces of the point's grid cell are
    visited - every face whose bbox contains the point is among them, the others were skipped
    by the bbox check anyway - so the answer is the same as testing every face."""
    return _occluded(
        mesh, cache, _ray_origin(camera, point), point, camera.project_to_screen(point, width, height),
        exclude_faces, depth_tolerance, False,
    )


def _ray_origin(camera, point):
    """Where the view ray through `point` starts: the eye, or in ortho (parallel rays) the point
    moved back behind all geometry (`OrbitCamera.ray_origin_toward`)."""
    if getattr(camera, "ortho", False):
        return camera.ray_origin_toward(point)
    return camera.eye()


def point_occlusion_test(camera, mesh, cache, width, height, depth_tolerance=DEPTH_TOLERANCE):
    """`occluded(point, exclude_faces, screen=None)` = `point_occluded(camera, mesh, cache, point,
    width, height, exclude_faces, depth_tolerance)` for many points under one camera state
    (Box Select): eye and projection are set up once. `screen` may pass the point's projection
    when the caller has it (it must equal `camera.project_to_screen(point, width, height)`, as
    `PickCache.vertex_screen` does)."""
    ortho = getattr(camera, "ortho", False)
    eye = None if ortho else camera.eye()
    projector = getattr(camera, "screen_projector", None)
    if projector is not None:
        project = projector(width, height)
    else:
        def project(point):
            return camera.project_to_screen(point, width, height)

    def occluded(point, exclude_faces, screen=None):
        if screen is None:
            screen = project(point)
        origin = camera.ray_origin_toward(point) if ortho else eye
        return _occluded(mesh, cache, origin, point, screen, exclude_faces, depth_tolerance, True)

    return occluded


def _occluded(mesh, cache, eye, point, screen, exclude_faces, depth_tolerance, batch):
    to_point = vecmath.sub(point, eye)
    dist = vecmath.length(to_point)
    if dist <= 1e-9:
        return False
    direction = vecmath.scale(to_point, 1.0 / dist)

    faces = None
    if cache is not None and screen is not None:
        grid = cache.face_grid(mesh, batch=batch)
        if grid is not None:
            faces = grid.faces_at(screen[0], screen[1])
    if faces is None:
        faces = mesh.all_face_ids()
    hidden_faces = cache.hidden_faces if cache is not None else ()
    for fid in faces:
        if fid in exclude_faces or fid in hidden_faces:
            continue  # a hidden face occludes nothing
        bbox = cache.face_bbox.get(fid) if cache is not None else None
        if bbox is not None and screen is not None:
            minx, miny, maxx, maxy = bbox
            if screen[0] < minx or screen[0] > maxx or screen[1] < miny or screen[1] > maxy:
                continue
        for tri in triangulate_mesh_face(mesh, fid):
            p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
            t = _ray_triangle_intersection(eye, direction, p0, p1, p2)
            if t is not None and t < dist - depth_tolerance:
                return True
    return False


def _incident_faces_of_vertex(mesh, vid, cache=None):
    """Faces on the edges of `vid`. From the cache's vertex -> faces map when there is a
    cache (WP-VIEW-PERF-01: `core.Mesh.vertex_edges` is an O(E) scan, the frozen core keeps
    it); a vertex the map does not know falls back to the scan."""
    if cache is not None:
        faces = cache.vertex_faces(mesh).get(vid)
        if faces is not None:
            return faces
    faces = set()
    for eid in mesh.vertex_edges(vid):
        faces.update(mesh.edge_faces(eid))
    return faces


def vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance=DEPTH_TOLERANCE):
    """True if vertex `vid` is hidden behind a face not incident to it."""
    point = mesh.vertex_position(vid)
    exclude = _incident_faces_of_vertex(mesh, vid, cache)
    return point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


def edge_point_occluded(camera, mesh, cache, eid, t, width, height, depth_tolerance=DEPTH_TOLERANCE):
    """True if the point at `t` on edge `eid` is hidden behind a face not incident to the edge."""
    va, vb = mesh.edge_vertices(eid)
    pa, pb = mesh.vertex_position(va), mesh.vertex_position(vb)
    point = (
        pa[0] + (pb[0] - pa[0]) * t,
        pa[1] + (pb[1] - pa[1]) * t,
        pa[2] + (pb[2] - pa[2]) * t,
    )
    exclude = set(mesh.edge_faces(eid))
    return point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


# Pre-S3 private names (callers outside this module: the Knife Face Lab planner, tests).
_point_occluded = point_occluded
_vertex_occluded = vertex_occluded
_edge_point_occluded = edge_point_occluded


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


# -- AD-021 M1: object picking (mode `4`) --------------------------------------


def front_face_hit_t(camera, mesh, sx, sy, width, height, *, cache: PickCache | None = None):
    """Ray parameter `t` of the front-most face hit under the cursor (None = no hit). The
    same ray and triangles as `pick_face`, so `t` of two meshes is comparable along one ray."""
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    if cache is not None:
        cache.refresh(camera, mesh, width, height)
    best_t = None
    for fid in _face_boundaries_within_bbox(mesh, cache, sx, sy):
        for tri in triangulate_mesh_face(mesh, fid):
            p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
            t = _ray_triangle_intersection(origin, direction, p0, p1, p2)
            if t is not None and (best_t is None or t < best_t):
                best_t = t
    return best_t


def face_hits_t(camera, mesh, sx, sy, width, height, *, cache: PickCache | None = None) -> list[float]:
    """Every ray parameter `t` where the cursor ray crosses a face, ascending (front and back sides
    alike, hidden faces skipped like `pick_face`). The Working Pivot's "inside" point (`mirai.pivot`)
    reads where the ray enters and leaves the mesh from it."""
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    if cache is not None:
        cache.refresh(camera, mesh, width, height)
    hits = []
    for fid in _face_boundaries_within_bbox(mesh, cache, sx, sy):
        for tri in triangulate_mesh_face(mesh, fid):
            p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
            t = _ray_triangle_intersection(origin, direction, p0, p1, p2)
            if t is not None:
                hits.append(t)
    hits.sort()
    return hits


def pick_object(candidates, sx, sy, width, height):
    """AD-021 M1/M2-1: the key of the object whose surface is front-most under the cursor (or
    None). `candidates` are `(key, mesh, cache, camera, scale)` - every object that is not
    hidden, References included (RF-3); the key is opaque here. `camera` is the camera in
    that object's space (the `OrbitCamera` itself for an unplaced object, else its
    `ObjectSpaceCamera`), whose normalized ray gives `t` in object units; `t · scale` is the
    world distance that is compared across objects (E-10). A tie keeps the earlier candidate."""
    best_key = None
    best_t = None
    for key, mesh, cache, camera, scale in candidates:
        t = front_face_hit_t(camera, mesh, sx, sy, width, height, cache=cache)
        if t is None:
            continue
        t *= scale
        if best_t is None or t < best_t:
            best_key, best_t = key, t
    return best_key
