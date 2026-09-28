"""`mirai.viewport.picking`/`picking_cache`: cache identity + occlusion (WP-06 B8).

Headless, no pyglet/GL. Three concerns:

1. Identity: with a `PickCache` and `occlusion=False`, every picker returns
   exactly what the pre-B8 exhaustive per-call implementation returns, for a
   grid of cursor positions on the cube and (if available) the head basemesh.
2. Occlusion: a synthetic mesh (one occluder quad + free-floating probe
   vertices/edge, camera looking straight down -Z) makes the expected
   occluded/visible result obvious by construction; the cube then gives a
   second, coarser sanity check (its one fully hidden corner vs. its
   camera-facing corner).
3. `PickCache` mechanics: `refresh()` is a no-op until the signature changes
   (camera revision, mesh identity, viewport size or an explicit
   `invalidate()`), and a stale cache would otherwise return a stale vertex
   position - `invalidate()` is what `Application` calls at every mutation
   point (WP-06 B8 handoff scope; covered end-to-end for `Application` in
   `tests/test_application_picking_cache.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, SelectionMode
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import (
    DEPTH_TOLERANCE,
    _edge_point_occluded,
    _vertex_occluded,
    pick_component,
    pick_face,
    pick_nearest_edge,
    pick_nearest_vertex,
)
from mirai.viewport.picking_cache import PickCache

WIDTH, HEIGHT = 800, 600

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))
_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


def _default_camera() -> OrbitCamera:
    return OrbitCamera()  # yaw=45°, pitch=25°, distance=6, target=origin


def _load_head_mesh() -> Mesh:
    from mirai.scene_factory import build_core_scene_from_obj  # examples/ on sys.path, WP-06 B1 pattern

    return build_core_scene_from_obj(_HEAD_ASSET).mesh


# -- 1. identity: cache must never change the result ---------------------------


def _assert_identity_grid(mesh, camera, step=47):
    cache = PickCache()
    for sx in range(10, WIDTH, step):
        for sy in range(10, HEIGHT, step):
            for max_dist in (14.0, 9.0):
                expected_v = pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, max_dist)
                got_v = pick_nearest_vertex(
                    camera, mesh, sx, sy, WIDTH, HEIGHT, max_dist, cache=cache
                )
                assert got_v == expected_v, (sx, sy, "vertex")

                expected_e = pick_nearest_edge(camera, mesh, sx, sy, WIDTH, HEIGHT, max_dist)
                got_e = pick_nearest_edge(
                    camera, mesh, sx, sy, WIDTH, HEIGHT, max_dist, cache=cache
                )
                assert got_e == expected_e, (sx, sy, "edge")

            expected_f = pick_face(camera, mesh, sx, sy, WIDTH, HEIGHT)
            got_f = pick_face(camera, mesh, sx, sy, WIDTH, HEIGHT, cache=cache)
            assert got_f == expected_f, (sx, sy, "face")


def test_cache_identical_to_uncached_on_cube_grid():
    mesh = create_cube()
    camera = _default_camera()
    _assert_identity_grid(mesh, camera)


@pytest.mark.skipif(not _HEAD_ASSET.is_file(), reason="head basemesh asset not found")
def test_cache_identical_to_uncached_on_head_mesh_grid():
    mesh = _load_head_mesh()
    camera = OrbitCamera(target=(0.0, 1.5, 0.0), distance=4.0)
    _assert_identity_grid(mesh, camera, step=61)


def test_pick_component_identity_across_modes():
    mesh = create_cube()
    camera = _default_camera()
    cache = PickCache()
    for mode in (SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE):
        for sx in range(20, WIDTH, 83):
            for sy in range(20, HEIGHT, 83):
                expected = pick_component(camera, mesh, mode, sx, sy, WIDTH, HEIGHT)
                got = pick_component(camera, mesh, mode, sx, sy, WIDTH, HEIGHT, cache=cache)
                assert got == expected, (mode, sx, sy)


# -- 2. occlusion: synthetic mesh (exact, hand-verifiable geometry) ------------


def _straight_on_camera() -> OrbitCamera:
    # eye=(0,0,5), forward=(0,0,-1), right=(1,0,0), up=(0,1,0).
    return OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0, yaw=0.0, pitch=0.0)


def _occluder_mesh():
    """One quad occluder at z=2 (between the eye at z=5 and the origin),
    spanning x,y in [-1, 1]; `va`=(0,0,0) is dead behind it, `vb`=(3,3,0) is
    well outside its footprint (unoccluded), joined by a free edge (`Mesh.
    add_edge`, no incident face) so edge-occlusion can be judged at either
    end. Returns (mesh, va, vb, edge_id, occluder_face_id)."""
    mesh = Mesh()
    va = mesh.add_vertex((0.0, 0.0, 0.0))
    vb = mesh.add_vertex((3.0, 3.0, 0.0))
    eid = mesh.add_edge(va, vb)
    o0 = mesh.add_vertex((-1.0, -1.0, 2.0))
    o1 = mesh.add_vertex((1.0, -1.0, 2.0))
    o2 = mesh.add_vertex((1.0, 1.0, 2.0))
    o3 = mesh.add_vertex((-1.0, 1.0, 2.0))
    fid = mesh.add_face([o0, o1, o2, o3])
    return mesh, va, vb, eid, fid


def test_vertex_directly_behind_occluder_is_occluded():
    mesh, va, vb, _eid, _fid = _occluder_mesh()
    camera = _straight_on_camera()
    assert _vertex_occluded(camera, mesh, None, va, WIDTH, HEIGHT, DEPTH_TOLERANCE) is True


def test_vertex_outside_occluder_footprint_is_visible():
    mesh, va, vb, _eid, _fid = _occluder_mesh()
    camera = _straight_on_camera()
    assert _vertex_occluded(camera, mesh, None, vb, WIDTH, HEIGHT, DEPTH_TOLERANCE) is False


def test_edge_occlusion_is_judged_at_the_picked_point_not_the_whole_edge():
    """The handoff's occlusion rule: visibility for an edge is judged at the
    point the cursor is nearest to, not the edge as a whole - one end of this
    edge sits behind the occluder, the other is clear."""
    mesh, va, vb, eid, _fid = _occluder_mesh()
    camera = _straight_on_camera()
    assert _edge_point_occluded(camera, mesh, None, eid, 0.0, WIDTH, HEIGHT, DEPTH_TOLERANCE) is True
    assert _edge_point_occluded(camera, mesh, None, eid, 1.0, WIDTH, HEIGHT, DEPTH_TOLERANCE) is False


def test_pick_nearest_vertex_skips_occluded_candidate_through_public_api():
    mesh, va, vb, _eid, _fid = _occluder_mesh()
    camera = _straight_on_camera()
    sx, sy = camera.project_to_screen((0.0, 0.0, 0.0), WIDTH, HEIGHT)
    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=False) == va
    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) is None


def test_depth_tolerance_keeps_a_grazing_point_on_the_occluders_own_plane_visible():
    """B8 depth tolerance (PROVISIONAL): a probe sitting exactly on the
    occluder's own plane (not part of its face - a genuine silhouette-style
    tangency) must not flip to occluded from floating-point noise alone."""
    mesh, _va, _vb, _eid, _fid = _occluder_mesh()
    grazing = mesh.add_vertex((-1.0, -1.0, 2.0))  # coincides with the occluder's own corner
    camera = _straight_on_camera()
    assert _vertex_occluded(camera, mesh, None, grazing, WIDTH, HEIGHT, DEPTH_TOLERANCE) is False


# -- 2b. occlusion on the cube (coarser end-to-end sanity, no hand geometry) ---


def _cube_front_and_hidden_vertices(mesh):
    """Per the default camera (yaw 45°, pitch 25°): faces 1 (+Z), 3 (+X), 4
    (+Y) face the camera (documented fixture fact, `tests/test_application_
    knife.py`); vertex 0 (index 0, `-s,-s,-s`) is the only corner touching
    none of them - the sole fully hidden vertex. Vertex 6 (`s,s,s`) touches
    all three - always visible."""
    ids = sorted(mesh.all_vertex_ids(), key=int)
    return ids[6], ids[0]  # (front, hidden)


def test_cube_hidden_corner_not_pickable_with_occlusion_visible_without():
    mesh = create_cube()
    camera = _default_camera()
    _front, hidden = _cube_front_and_hidden_vertices(mesh)
    sx, sy = camera.project_to_screen(mesh.vertex_position(hidden), WIDTH, HEIGHT)

    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=False) == hidden
    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) is None


def test_cube_front_corner_stays_pickable_with_occlusion():
    mesh = create_cube()
    camera = _default_camera()
    front, _hidden = _cube_front_and_hidden_vertices(mesh)
    sx, sy = camera.project_to_screen(mesh.vertex_position(front), WIDTH, HEIGHT)

    assert pick_nearest_vertex(camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == front


# -- 3. PickCache mechanics -----------------------------------------------------


def test_refresh_is_a_no_op_until_the_signature_changes():
    mesh = create_cube()
    camera = _default_camera()
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    signature_after_first = cache._signature
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    assert cache._signature == signature_after_first
    assert cache.vertex_screen  # populated


def test_stale_cache_without_invalidate_returns_the_old_position():
    mesh = create_cube()
    camera = _default_camera()
    cache = PickCache()
    vid = next(iter(mesh.all_vertex_ids()))
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    old_screen = cache.vertex_screen[vid]

    mesh.set_vertex_position(vid, (old_screen[0] + 500.0, 0.0, 0.0))  # nonsense but harmless move
    cache.refresh(camera, mesh, WIDTH, HEIGHT)  # same signature - stays stale on purpose

    assert cache.vertex_screen[vid] == old_screen


def test_invalidate_forces_a_fresh_projection():
    mesh = create_cube()
    camera = _default_camera()
    cache = PickCache()
    vid = next(iter(mesh.all_vertex_ids()))
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    old_screen = cache.vertex_screen[vid]

    mesh.set_vertex_position(vid, (10.0, 10.0, 10.0))
    cache.invalidate()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)

    assert cache.vertex_screen[vid] != old_screen
    assert cache.vertex_screen[vid] == camera.project_to_screen((10.0, 10.0, 10.0), WIDTH, HEIGHT)


def test_camera_revision_change_invalidates_without_an_explicit_call():
    mesh = create_cube()
    camera = _default_camera()
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    signature_before = cache._signature

    camera.orbit(0.3, 0.0)  # bumps camera.camera_revision
    cache.refresh(camera, mesh, WIDTH, HEIGHT)

    assert cache._signature != signature_before


def test_viewport_resize_invalidates_without_an_explicit_call():
    mesh = create_cube()
    camera = _default_camera()
    cache = PickCache()
    cache.refresh(camera, mesh, WIDTH, HEIGHT)
    vid = next(iter(mesh.all_vertex_ids()))
    at_800 = cache.vertex_screen[vid]

    cache.refresh(camera, mesh, WIDTH * 2, HEIGHT * 2)

    assert cache.vertex_screen[vid] != at_800
