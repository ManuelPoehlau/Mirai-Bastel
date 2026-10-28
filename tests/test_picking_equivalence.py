"""WP-VIEW-PERF-01 Slices 1 + 2: the faster pickers pick exactly what the pre-PERF ones picked.

Headless, no pyglet/GL. `_Old*` / `_old_*` below are the pre-PERF implementation, copied
verbatim from `mirai/viewport/picking.py` / `picking_cache.py` at 65e30ae (mesh-order scan with
`math.hypot`, an occlusion test for every closer candidate, incident faces through
`core.Mesh.vertex_edges`, `project_to_screen` per vertex, `point_occluded` over every face) and
`box_select.elements_in_rect` at aa1f10b (one full occlusion test per element). The comparison
covers the Slice-1 changes:

1. nearest-first occlusion + squared-distance scan (`pick_nearest_vertex`, `pick_nearest_edge`),
2. `PickCache.refresh` through `screen_projector` (bit-identical screen positions),
3. the cache's vertex -> incident-faces map (rebuilt per mesh state, not per camera),

and Slice 2 (`PickCache.face_grid`: the occlusion test visits the faces of the point's screen
cell; Box Select sets eye and projection up once per box), compared on head and body over a
grid of cursor positions plus points on and next to the projected vertices, in Shaded
(occlusion on) and Wireframe (off), from the front and the back, and on a seeded sample of
`gollum_20k.obj`. Item 4 (lazy bounds) is in `test_render_mesh.py`.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.object_space import ObjectSpaceCamera
from core import EdgeId, FaceId, SelectionMode, VertexId
from mirai.viewport import box_select, picking, picking_cache
from mirai.viewport import vecmath
from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import (
    DEPTH_TOLERANCE,
    _point_segment_distance_t,
    _ray_triangle_intersection,
    pick_nearest_edge,
    pick_nearest_vertex,
    point_occluded,
)
from mirai.viewport.picking_cache import FaceGrid, PickCache
from viewport.derived import triangulate_mesh_face

WIDTH, HEIGHT = 800, 600

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))
_MESHES = _EXAMPLES_DIR / "meshes"
_HEAD = _MESHES / "head_basemesh.obj"
_BODY = _MESHES / "Man_With_Shoes_basemesh.obj"
_GOLLUM_20K = _MESHES / "gollum_20k.obj"


# -- the pre-PERF implementation (65e30ae), verbatim -----------------------------------


class _OldPickCache(PickCache):
    def refresh(self, camera, mesh, width, height):
        signature = (id(mesh), id(camera), camera.camera_revision, width, height, self._generation)
        if signature == self._signature:
            return
        self._signature = signature
        vertex_screen = {
            vid: camera.project_to_screen(mesh.vertex_position(vid), width, height)
            for vid in mesh.all_vertex_ids()
        }
        self.vertex_screen = vertex_screen
        face_bbox = {}
        for fid in mesh.all_face_ids():
            points = [vertex_screen.get(vid) for vid in mesh.face_vertices(fid)]
            if not points or any(p is None for p in points):
                face_bbox[fid] = None
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            face_bbox[fid] = (min(xs), min(ys), max(xs), max(ys))
        self.face_bbox = face_bbox


def _old_point_occluded(camera, mesh, cache, point, width, height, exclude_faces, depth_tolerance=DEPTH_TOLERANCE):
    # The full-scan reference; in ortho (WP Ortho / Views) its ray is the parallel one through the point.
    eye = camera.ray_origin_toward(point) if getattr(camera, "ortho", False) else camera.eye()
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
        for tri in triangulate_mesh_face(mesh, fid):
            p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
            t = _ray_triangle_intersection(eye, direction, p0, p1, p2)
            if t is not None and t < dist - depth_tolerance:
                return True
    return False


def _old_incident_faces_of_vertex(mesh, vid):
    faces = set()
    for eid in mesh.vertex_edges(vid):
        faces.update(mesh.edge_faces(eid))
    return faces


def _old_vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance=DEPTH_TOLERANCE):
    point = mesh.vertex_position(vid)
    exclude = _old_incident_faces_of_vertex(mesh, vid)
    return _old_point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


def _old_edge_point_occluded(camera, mesh, cache, eid, t, width, height, depth_tolerance=DEPTH_TOLERANCE):
    va, vb = mesh.edge_vertices(eid)
    pa, pb = mesh.vertex_position(va), mesh.vertex_position(vb)
    point = (
        pa[0] + (pb[0] - pa[0]) * t,
        pa[1] + (pb[1] - pa[1]) * t,
        pa[2] + (pb[2] - pa[2]) * t,
    )
    exclude = set(mesh.edge_faces(eid))
    return _old_point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


def _old_pick_nearest_vertex(camera, mesh, sx, sy, width, height, max_pixel_distance=14.0, *,
                             cache=None, occlusion=False, depth_tolerance=DEPTH_TOLERANCE):
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
        if occlusion and _old_vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance):
            continue
        best_dist = dist
        best_id = vid
    return best_id


def _old_pick_nearest_edge(camera, mesh, sx, sy, width, height, max_pixel_distance=9.0, *,
                           cache=None, occlusion=False, depth_tolerance=DEPTH_TOLERANCE):
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
        if occlusion and _old_edge_point_occluded(camera, mesh, cache, eid, t, width, height, depth_tolerance):
            continue
        best_dist = dist
        best_id = eid
    return best_id


def _old_elements_in_rect(camera, mesh, mode, rect, width, height, *, cache, occlusion):
    """`box_select.elements_in_rect` at aa1f10b, on the pre-PERF occlusion helpers."""
    _inside = box_select._inside
    cache.refresh(camera, mesh, width, height)
    screen = cache.vertex_screen
    inside_vertices = {vid for vid, point in screen.items() if _inside(point, rect)}

    if mode is SelectionMode.VERTEX:
        found: set = set(inside_vertices)
        if occlusion:
            found = {
                vid for vid in found if not _old_vertex_occluded(camera, mesh, cache, vid, width, height)
            }
        return {VertexId(v) for v in found}

    if mode is SelectionMode.EDGE:
        edges = set()
        for eid in mesh.all_edge_ids():
            a, b = mesh.edge_vertices(eid)
            if a in inside_vertices and b in inside_vertices:
                if occlusion and _old_edge_point_occluded(camera, mesh, cache, eid, 0.5, width, height):
                    continue
                edges.add(EdgeId(eid))
        return edges

    faces = set()
    for fid in mesh.all_face_ids():
        corners = mesh.face_vertices(fid)
        if not all(v in inside_vertices for v in corners):
            continue
        if occlusion:
            positions = [mesh.vertex_position(v) for v in corners]
            centroid = tuple(sum(p[i] for p in positions) / len(positions) for i in range(3))
            if _old_point_occluded(camera, mesh, cache, centroid, width, height, {fid}):
                continue
        faces.add(FaceId(fid))
    return faces


# -- fixtures ---------------------------------------------------------------------------


def _load(path: Path) -> Mesh:
    from mirai.scene_factory import build_core_scene_from_obj

    return build_core_scene_from_obj(path).mesh


def _framed_cameras(mesh, ortho: bool = False) -> list[OrbitCamera]:
    """Front (default yaw/pitch) and back (yaw + 180 deg, pitch down), framed on the mesh."""
    center, radius = mesh_center_and_radius(mesh)
    cameras = []
    for yaw, pitch in ((math.radians(30), math.radians(15)), (math.radians(210), math.radians(-20))):
        camera = OrbitCamera(yaw=yaw, pitch=pitch, ortho=ortho)
        camera.frame_on_bounds(center, radius)
        cameras.append(camera)
    return cameras


def _cursors(camera, mesh, grid_step: int, vertex_sample: int, seed: int):
    """A screen grid plus points on and 2-7 px next to `vertex_sample` projected vertices
    (seeded): the grid covers empty space and silhouettes, the vertex points the dense
    part where hidden candidates crowd the cursor."""
    points = [(float(x), float(y)) for x in range(5, WIDTH, grid_step) for y in range(5, HEIGHT, grid_step)]
    rng = random.Random(seed)
    ids = mesh.all_vertex_ids()
    for vid in rng.sample(ids, min(vertex_sample, len(ids))):
        s = camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        if s is None:
            continue
        points.append(s)
        points.append((s[0] + rng.uniform(2.0, 7.0), s[1] - rng.uniform(2.0, 7.0)))
    return points


def _assert_equivalent(mesh, camera, cursors, *, check_edges=True):
    """Old and new pickers agree on every cursor, Shaded and Wireframe; also returns how
    many cursors hit something (so a test can assert it was not vacuous)."""
    new_cache, old_cache = PickCache(), _OldPickCache()
    hits = 0
    for sx, sy in cursors:
        for occlusion in (True, False):
            old_v = _old_pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT,
                                             cache=old_cache, occlusion=occlusion)
            new_v = pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT,
                                        cache=new_cache, occlusion=occlusion)
            assert new_v == old_v, ("vertex", sx, sy, occlusion)
            hits += old_v is not None
            if check_edges:
                old_e = _old_pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT,
                                               cache=old_cache, occlusion=occlusion)
                new_e = pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT,
                                          cache=new_cache, occlusion=occlusion)
                assert new_e == old_e, ("edge", sx, sy, occlusion)
                hits += old_e is not None
    # Same screen positions and bboxes, bit for bit (item 2).
    assert new_cache.vertex_screen == old_cache.vertex_screen
    assert new_cache.face_bbox == old_cache.face_bbox
    return hits


# -- 1. equivalence on head and body ----------------------------------------------------


@pytest.mark.parametrize("path", [_HEAD, _BODY], ids=["head", "body"])
def test_same_picks_as_the_old_pickers_on_a_cursor_grid(path):
    if not path.is_file():
        pytest.skip(f"asset {path.name} not found")
    mesh = _load(path)
    for i, camera in enumerate(_framed_cameras(mesh)):
        hits = _assert_equivalent(mesh, camera, _cursors(camera, mesh, 37, 60, seed=i))
        assert hits > 50


def test_same_picks_as_the_old_pickers_in_ortho():
    """WP Ortho / Views: the cached, grid-accelerated pickers equal the full-scan reference with parallel rays."""
    mesh = _load(_HEAD) if _HEAD.is_file() else pytest.skip("head asset not found")
    for i, camera in enumerate(_framed_cameras(mesh, ortho=True)):
        assert _assert_equivalent(mesh, camera, _cursors(camera, mesh, 37, 60, seed=i)) > 50


def test_same_picks_without_a_cache():
    mesh = _load(_HEAD) if _HEAD.is_file() else pytest.skip("head asset not found")
    camera = _framed_cameras(mesh)[0]
    for sx, sy in _cursors(camera, mesh, 113, 15, seed=7):
        for occlusion in (True, False):
            assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=occlusion) == \
                _old_pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=occlusion)
            assert pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=occlusion) == \
                _old_pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=occlusion)


def test_same_picks_through_an_object_space_camera():
    """A placed edit object picks through `ObjectSpaceCamera` (AD-021 M2-1): its projector
    must equal its `project_to_screen` too."""
    from core import ObjectTransform, SceneObject
    from core.ids import ObjectId
    from mirai.object_space import axis_angle_rotation

    if not _HEAD.is_file():
        pytest.skip("head asset not found")
    mesh = _load(_HEAD)
    placement = ObjectTransform(
        translation=(0.3, -0.2, 0.1), rotation=axis_angle_rotation((0.0, 1.0, 0.0), 0.7), scale=1.3
    )
    obj = SceneObject(ObjectId(0), mesh, transform=placement, pivot=(0.1, 0.4, -0.2))
    world_camera = _framed_cameras(mesh)[0]
    camera = ObjectSpaceCamera(world_camera, obj)
    project = camera.screen_projector(WIDTH, HEIGHT)
    for vid in mesh.all_vertex_ids():
        p = mesh.vertex_position(vid)
        assert project(p) == camera.project_to_screen(p, WIDTH, HEIGHT)
    hits = _assert_equivalent(mesh, camera, _cursors(world_camera, mesh, 61, 30, seed=3))
    assert hits > 10


# -- 2. a hidden element earlier in mesh order than the visible nearest one ------------


def _straight_on_camera() -> OrbitCamera:
    # eye=(0,0,5), forward=(0,0,-1).
    return OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0, yaw=0.0, pitch=0.0)


def _hidden_first_mesh():
    """In mesh order: a hidden vertex `h` (behind the occluder quad at z=2, right under the
    cursor) and a hidden edge through it, then the occluder, then a visible vertex `v` and a
    visible edge, both in front of the occluder and a few px from the cursor. The old scan
    meets the hidden ones first; both pickers must return the visible ones."""
    mesh = Mesh()
    h = mesh.add_vertex((0.0, 0.0, 0.0))
    h2 = mesh.add_vertex((0.0, 0.2, 0.0))
    hidden_edge = mesh.add_edge(h, h2)
    corners = [mesh.add_vertex(p) for p in ((-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, 1.0, 2.0), (-1.0, 1.0, 2.0))]
    mesh.add_face(corners)
    v = mesh.add_vertex((0.02, 0.0, 3.0))
    v2 = mesh.add_vertex((0.02, 0.2, 3.0))
    visible_edge = mesh.add_edge(v, v2)
    return mesh, h, hidden_edge, v, visible_edge


def test_hidden_vertex_and_edge_earlier_in_mesh_order_lose_to_the_visible_nearest(monkeypatch):
    mesh, h, hidden_edge, v, visible_edge = _hidden_first_mesh()
    camera = _straight_on_camera()
    sx, sy = camera.project_to_screen(mesh.vertex_position(h), WIDTH, HEIGHT)
    vs = camera.project_to_screen(mesh.vertex_position(v), WIDTH, HEIGHT)
    assert 0.0 < math.hypot(vs[0] - sx, vs[1] - sy) < 9.0  # the visible one is farther, in range

    tests = []
    original = picking.vertex_occluded
    monkeypatch.setattr(picking, "vertex_occluded",
                        lambda *a, **k: tests.append(a[3]) or original(*a, **k))
    for cache in (None, PickCache()):
        assert _old_pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True) == v
        tests.clear()
        assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True) == v
        assert tests == [h, v]  # nearest first: the hidden one, then the visible one, stop
        assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=False) == h

        assert _old_pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True) == visible_edge
        assert pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True) == visible_edge
        assert pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=False) == hidden_edge


def test_equal_distance_tie_keeps_mesh_order():
    mesh = Mesh()
    first = mesh.add_vertex((0.1, 0.0, 0.0))
    mesh.add_vertex((-0.1, 0.0, 0.0))  # mirror image: the same screen distance from the centre
    camera = _straight_on_camera()
    cx, cy = camera.project_to_screen((0.0, 0.0, 0.0), WIDTH, HEIGHT)
    for occlusion in (True, False):
        assert pick_nearest_vertex(camera, mesh, cx, cy, WIDTH, HEIGHT, 40.0, occlusion=occlusion) == first
        assert _old_pick_nearest_vertex(camera, mesh, cx, cy, WIDTH, HEIGHT, 40.0, occlusion=occlusion) == first


# -- 3. the incident-faces map: per mesh state, not per camera --------------------------


def test_vertex_faces_map_matches_vertex_edges_and_survives_a_camera_change():
    if not _HEAD.is_file():
        pytest.skip("head asset not found")
    mesh = _load(_HEAD)
    camera = _framed_cameras(mesh)[0]
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    faces = cache.vertex_faces(mesh)
    for vid in mesh.all_vertex_ids():
        assert faces[vid] == _old_incident_faces_of_vertex(mesh, vid)

    camera.orbit(0.3, 0.1)
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    assert cache.vertex_faces(mesh) is faces  # a camera change keeps the map

    cache.invalidate()
    # 2026-10-21: the map follows the mesh's change journal; an `invalidate()` without a mesh change
    # keeps it (a real change patches it, see the next test).
    assert cache.vertex_faces(mesh) is faces


def test_vertex_faces_map_follows_a_topology_change_after_invalidate():
    mesh, va, _vb, _eid, _fid = _occluder_and_free_edge()
    cache = PickCache()
    assert cache.vertex_faces(mesh)[va] == set()
    new_face = mesh.add_face([va, mesh.add_vertex((1.0, 0.0, 0.0)), mesh.add_vertex((0.0, 1.0, 0.0))])
    cache.invalidate()
    assert cache.vertex_faces(mesh)[va] == {new_face} == _old_incident_faces_of_vertex(mesh, va)


def test_unknown_vertex_falls_back_to_the_scan():
    mesh, va, _vb, _eid, _fid = _occluder_and_free_edge()
    cache = PickCache()
    cache.vertex_faces(mesh)
    late = mesh.add_vertex((5.0, 5.0, 5.0))  # added without invalidate(): not in the map
    assert picking._incident_faces_of_vertex(mesh, late, cache) == set()


def _occluder_and_free_edge():
    mesh = Mesh()
    va = mesh.add_vertex((0.0, 0.0, 0.0))
    vb = mesh.add_vertex((3.0, 3.0, 0.0))
    eid = mesh.add_edge(va, vb)
    corners = [mesh.add_vertex(p) for p in ((-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, 1.0, 2.0), (-1.0, 1.0, 2.0))]
    fid = mesh.add_face(corners)
    return mesh, va, vb, eid, fid


# -- 4. seeded sample on gollum_20k (the reference-PC mesh) -----------------------------


@pytest.mark.skipif(not _GOLLUM_20K.is_file(), reason="gollum_20k.obj not found")
def test_same_picks_on_a_seeded_gollum_20k_sample():
    """The audit's what-if was 11/11 identical picks; here 24 cursors (on and next to seeded
    vertices, front and back camera) with occlusion on and off. Edges only from the front
    camera: the old edge picker is ~0.5 s per occluded pick on this mesh."""
    mesh = _load(_GOLLUM_20K)
    for i, camera in enumerate(_framed_cameras(mesh)):
        cursors = _cursors(camera, mesh, 10_000, 6, seed=100 + i)
        hits = _assert_equivalent(mesh, camera, cursors, check_edges=(i == 0))
        assert hits > 0


# -- 5. Slice 2: Box Select and the face grid -------------------------------------------


def _rects(camera, mesh):
    """A 150 px box on the mesh centre, a 60 px one on a projected vertex, one over the whole
    view and one that sticks out of the window (the grid covers only the viewport)."""
    center, _radius = mesh_center_and_radius(mesh)
    cx, cy = camera.project_to_screen(center, WIDTH, HEIGHT)
    vid = mesh.all_vertex_ids()[len(mesh.all_vertex_ids()) // 3]
    vx, vy = camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
    return [
        (cx - 75.0, cy - 75.0, cx + 75.0, cy + 75.0),
        (vx - 30.0, vy - 30.0, vx + 30.0, vy + 30.0),
        (0.0, 0.0, float(WIDTH), float(HEIGHT)),
        (cx - 40.0, -50.0, cx + 60.0, cy),
    ]


def _assert_box_equivalent(mesh, camera, rects, modes=(SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE),
                           occlusions=(True, False)):
    hidden = 0
    for mode in modes:
        for rect in rects:
            for occlusion in occlusions:
                new = box_select.elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                                  cache=PickCache(), occlusion=occlusion)
                old = _old_elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                            cache=_OldPickCache(), occlusion=occlusion)
                assert new == old, (mode, rect, occlusion)
                if occlusion:
                    unoccluded = _old_elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                                       cache=_OldPickCache(), occlusion=False)
                    hidden += len(unoccluded) - len(old)
    return hidden


@pytest.mark.parametrize("path", [_HEAD, _BODY], ids=["head", "body"])
def test_box_select_same_elements_as_the_old_box_in_every_mode(path):
    """Shaded (occlusion) and Wireframe, vertex / edge / face, front and back camera; the
    occlusion must hide something (not vacuous)."""
    if not path.is_file():
        pytest.skip(f"asset {path.name} not found")
    mesh = _load(path)
    hidden = 0
    for camera in _framed_cameras(mesh):
        hidden += _assert_box_equivalent(mesh, camera, _rects(camera, mesh))
    assert hidden > 100


@pytest.mark.skipif(not _GOLLUM_20K.is_file(), reason="gollum_20k.obj not found")
def test_box_select_same_elements_on_a_gollum_20k_sample():
    """One 60 px box on a seeded vertex of the front view, all three modes, Shaded (the old
    box costs ~1-2 s per mode here)."""
    mesh = _load(_GOLLUM_20K)
    camera = _framed_cameras(mesh)[0]
    vid = random.Random(5).choice(mesh.all_vertex_ids())
    vx, vy = camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
    rect = (vx - 30.0, vy - 30.0, vx + 30.0, vy + 30.0)
    for mode in (SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE):
        new = box_select.elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                          cache=PickCache(), occlusion=True)
        old = _old_elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                    cache=_OldPickCache(), occlusion=True)
        assert new == old and new, mode


@pytest.mark.parametrize("ortho", [False, True], ids=["persp", "ortho"])
@pytest.mark.parametrize("path", [_HEAD, _BODY], ids=["head", "body"])
def test_point_occluded_through_the_grid_matches_the_full_scan(path, ortho):
    """Every vertex, edge midpoint and face centroid (the points hover, click and Box test),
    with the grid built, against the old full scan - from the front and the back (also in ortho,
    WP Ortho / Views: the reference casts the parallel ray)."""
    if not path.is_file():
        pytest.skip(f"asset {path.name} not found")
    mesh = _load(path)
    for camera in _framed_cameras(mesh, ortho):
        cache, old_cache = PickCache(), _OldPickCache()
        cache.refresh(camera, mesh, WIDTH, HEIGHT)
        old_cache.refresh(camera, mesh, WIDTH, HEIGHT)
        assert cache.face_grid(mesh) is not None  # a batch request builds it at once
        hidden = 0
        for vid in mesh.all_vertex_ids():
            new = picking.vertex_occluded(camera, mesh, cache, vid, WIDTH, HEIGHT)
            assert new == _old_vertex_occluded(camera, mesh, old_cache, vid, WIDTH, HEIGHT), vid
            hidden += new
        for eid in mesh.all_edge_ids()[::3]:
            assert picking.edge_point_occluded(camera, mesh, cache, eid, 0.5, WIDTH, HEIGHT) == \
                _old_edge_point_occluded(camera, mesh, old_cache, eid, 0.5, WIDTH, HEIGHT), eid
        for fid in mesh.all_face_ids()[::3]:
            positions = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
            centroid = tuple(sum(p[i] for p in positions) / len(positions) for i in range(3))
            assert point_occluded(camera, mesh, cache, centroid, WIDTH, HEIGHT, {fid}) == \
                _old_point_occluded(camera, mesh, old_cache, centroid, WIDTH, HEIGHT, {fid}), fid
        assert hidden > 20


def _occluder_far_from_its_first_cell():
    """A big occluder quad (z = 2) in front of a hidden vertex `h` (z = 0) that projects far
    from the quad's bbox corner - into a grid cell other than the one holding that corner -
    plus a strip of small decoy faces elsewhere, so a cell does not simply hold every face."""
    mesh = Mesh()
    corners = [mesh.add_vertex(p) for p in ((-1.5, -1.5, 2.0), (1.5, -1.5, 2.0), (1.5, 1.5, 2.0), (-1.5, 1.5, 2.0))]
    occluder = mesh.add_face(corners)
    h = mesh.add_vertex((0.5, 0.6, 0.0))
    for i in range(12):
        x = -3.0 + 0.5 * i
        quad = [mesh.add_vertex(p) for p in ((x, -3.0, 0.0), (x + 0.4, -3.0, 0.0), (x + 0.4, -2.6, 0.0), (x, -2.6, 0.0))]
        mesh.add_face(quad)
    return mesh, occluder, h


def test_hidden_vertex_behind_a_face_whose_corner_lies_in_another_cell():
    """A grid that listed a face only in the cell of its bbox corner (or of its first vertex)
    would let the occlusion test skip the occluder here and pick a hidden vertex."""
    mesh, occluder, h = _occluder_far_from_its_first_cell()
    camera = _straight_on_camera()
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    grid = cache.face_grid(mesh)
    hx, hy = camera.project_to_screen(mesh.vertex_position(h), WIDTH, HEIGHT)
    minx, miny, _maxx, _maxy = cache.face_bbox[occluder]
    cell = picking_cache.FACE_GRID_CELL_PX
    assert (math.floor(hx / cell), math.floor(hy / cell)) != (math.floor(minx / cell), math.floor(miny / cell))
    faces = grid.faces_at(hx, hy)
    assert occluder in faces and len(faces) < len(mesh.all_face_ids())
    assert picking.vertex_occluded(camera, mesh, cache, h, WIDTH, HEIGHT)
    assert _old_vertex_occluded(camera, mesh, _OldPickCache(), h, WIDTH, HEIGHT)
    assert pick_nearest_vertex(camera, mesh, hx, hy, WIDTH, HEIGHT, cache=cache, occlusion=True) != h
    assert box_select.elements_in_rect(camera, mesh, SelectionMode.VERTEX, (hx - 3, hy - 3, hx + 3, hy + 3),
                                       WIDTH, HEIGHT, cache=cache, occlusion=True) == set()
    assert box_select.elements_in_rect(camera, mesh, SelectionMode.VERTEX, (hx - 3, hy - 3, hx + 3, hy + 3),
                                       WIDTH, HEIGHT, cache=cache, occlusion=False) == {h}


def test_face_grid_cells_bounds_and_unbounded_faces():
    grid = FaceGrid({1: (10.0, 10.0, 32.0, 20.0), 2: (-500.0, -500.0, 900.0, 900.0), 3: None,
                     4: (2000.0, 10.0, 2100.0, 20.0)}, 100, 100, 16.0)
    assert 1 in grid.faces_at(32.0, 15.0)  # on a cell border: the bbox reaches into that cell
    assert 1 in grid.faces_at(10.0, 10.0) and 1 not in grid.faces_at(48.0, 15.0)
    assert all(2 in grid.faces_at(x, y) for x in (0.0, 50.0, 99.9) for y in (0.0, 99.9))  # clamped
    assert all(3 in grid.faces_at(x, y) for x in (0.0, 70.0) for y in (5.0, 90.0))  # no bbox: always
    assert not any(4 in grid.faces_at(x, 15.0) for x in (0.0, 50.0, 99.0))  # off the viewport
    assert grid.faces_at(-0.1, 5.0) is None and grid.faces_at(5.0, 112.0) is None  # outside: scan all


def test_face_grid_is_built_lazily_per_camera_state():
    mesh, _occluder, h = _occluder_far_from_its_first_cell()
    camera = _straight_on_camera()
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    for _ in range(picking_cache.GRID_AFTER_SCANS):
        assert cache.face_grid(mesh, batch=False) is None  # single tests scan first
    grid = cache.face_grid(mesh, batch=False)
    assert grid is not None and cache.face_grid(mesh) is grid
    camera.orbit(0.2, 0.0)
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    assert cache.face_grid(mesh, batch=False) is None  # a new camera state counts again
    assert cache.face_grid(mesh) is not grid  # a batch builds it at once
    assert cache.face_grid(Mesh()) is None  # the bboxes are not this mesh's
    cache.invalidate()
    assert cache.face_grid(mesh) is not None  # stale signature: still the last refresh's grid
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    # 2026-10-21: the journal shows the mesh unchanged, so the grid of this camera state is kept.
    assert cache.face_grid(mesh, batch=False) is not None


@pytest.mark.skipif(not _BODY.is_file(), reason="body asset not found")
def test_pickers_with_the_grid_built_pick_as_before():
    """The Slice-1 cursor sweep with the grid built up front (the sweep itself builds it after
    `GRID_AFTER_SCANS` scans; here every test goes through it)."""
    mesh = _load(_BODY)
    camera = _framed_cameras(mesh)[0]
    cache, old_cache = PickCache(), _OldPickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    cache.face_grid(mesh)
    for sx, sy in _cursors(camera, mesh, 53, 40, seed=11):
        assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True) == \
            _old_pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=old_cache, occlusion=True)
        assert pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True) == \
            _old_pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=old_cache, occlusion=True)
