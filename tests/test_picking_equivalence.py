"""WP-VIEW-PERF-01 Slice 1: the faster pickers pick exactly what the pre-PERF ones picked.

Headless, no pyglet/GL. `_Old*` / `_old_*` below are the pre-PERF implementation, copied
verbatim from `mirai/viewport/picking.py` / `picking_cache.py` at 65e30ae (mesh-order scan with
`math.hypot`, an occlusion test for every closer candidate, incident faces through
`core.Mesh.vertex_edges`, `project_to_screen` per vertex). Both sides use the same unchanged
`point_occluded`, so the comparison isolates the four Slice-1 changes:

1. nearest-first occlusion + squared-distance scan (`pick_nearest_vertex`, `pick_nearest_edge`),
2. `PickCache.refresh` through `screen_projector` (bit-identical screen positions),
3. the cache's vertex -> incident-faces map (rebuilt per mesh state, not per camera),
compared on head and body over a grid of cursor positions plus points on and next to the
projected vertices, in Shaded (occlusion on) and Wireframe (off), from the front and the back,
and on a seeded sample of `gollum_20k.obj`. Item 4 (lazy bounds) is in `test_render_mesh.py`.
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
from mirai.viewport import picking
from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import (
    DEPTH_TOLERANCE,
    _point_segment_distance_t,
    pick_nearest_edge,
    pick_nearest_vertex,
    point_occluded,
)
from mirai.viewport.picking_cache import PickCache

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


def _old_incident_faces_of_vertex(mesh, vid):
    faces = set()
    for eid in mesh.vertex_edges(vid):
        faces.update(mesh.edge_faces(eid))
    return faces


def _old_vertex_occluded(camera, mesh, cache, vid, width, height, depth_tolerance=DEPTH_TOLERANCE):
    point = mesh.vertex_position(vid)
    exclude = _old_incident_faces_of_vertex(mesh, vid)
    return point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


def _old_edge_point_occluded(camera, mesh, cache, eid, t, width, height, depth_tolerance=DEPTH_TOLERANCE):
    va, vb = mesh.edge_vertices(eid)
    pa, pb = mesh.vertex_position(va), mesh.vertex_position(vb)
    point = (
        pa[0] + (pb[0] - pa[0]) * t,
        pa[1] + (pb[1] - pa[1]) * t,
        pa[2] + (pb[2] - pa[2]) * t,
    )
    exclude = set(mesh.edge_faces(eid))
    return point_occluded(camera, mesh, cache, point, width, height, exclude, depth_tolerance)


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


# -- fixtures ---------------------------------------------------------------------------


def _load(path: Path) -> Mesh:
    from mirai.scene_factory import build_core_scene_from_obj

    return build_core_scene_from_obj(path).mesh


def _framed_cameras(mesh) -> list[OrbitCamera]:
    """Front (default yaw/pitch) and back (yaw + 180 deg, pitch down), framed on the mesh."""
    center, radius = mesh_center_and_radius(mesh)
    cameras = []
    for yaw, pitch in ((math.radians(30), math.radians(15)), (math.radians(210), math.radians(-20))):
        camera = OrbitCamera(yaw=yaw, pitch=pitch)
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
    rebuilt = cache.vertex_faces(mesh)
    assert rebuilt is not faces and rebuilt == faces  # a mesh change rebuilds it


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


# -- 5. Box Select reaches the same occlusion helpers: same selection --------------------


@pytest.mark.skipif(not _BODY.is_file(), reason="body asset not found")
def test_box_select_same_elements_as_with_the_old_helpers(monkeypatch):
    from core import SelectionMode
    from mirai.viewport import box_select

    mesh = _load(_BODY)
    for camera in _framed_cameras(mesh):
        rects = [(cx - 75.0, cy - 75.0, cx + 75.0, cy + 75.0) for cx, cy in ((400.0, 300.0), (380.0, 150.0))]
        for mode in (SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE):
            for rect in rects:
                new = box_select.elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                                  cache=PickCache(), occlusion=True)
                with monkeypatch.context() as m:
                    m.setattr(box_select, "vertex_occluded", _old_vertex_occluded)
                    old = box_select.elements_in_rect(camera, mesh, mode, rect, WIDTH, HEIGHT,
                                                      cache=_OldPickCache(), occlusion=True)
                assert new == old and new, (mode, rect)
