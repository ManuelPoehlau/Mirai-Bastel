"""Working Pivot placement (`mirai.pivot.place_pivot`, 2026-10-28, Manu U-2): a click on the mesh lands in the middle
of the volume under the cursor, Shift snaps to the vertex / edge point, a click off the mesh keeps the given depth."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from mirai.pivot import (
    PIVOT_PLANE_SNAP_PX,
    WorkingPivot,
    inside_point,
    place_pivot,
    snap_point,
    snap_to_plane,
    view_plane_point,
)
from mirai.scene_factory import create_sphere
from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import face_hits_t
from mirai.viewport.picking_cache import PickCache
from tests.subdivision_meshes import cube_mesh, single_quad_mesh

WIDTH, HEIGHT = 800, 600
CENTRE = (WIDTH / 2.0, HEIGHT / 2.0)


def _front_camera(target=(0.0, 0.0, 0.0), distance=6.0) -> OrbitCamera:
    """Looking down -Z at `target` (eye on +Z)."""
    return OrbitCamera(target=target, distance=distance, yaw=0.0, pitch=0.0)


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_ray_hits_every_face_it_crosses_in_order():
    hits = face_hits_t(_front_camera(), cube_mesh(), *CENTRE, WIDTH, HEIGHT)
    # Enters the front face (z = 1) at t = 5 and leaves through the back (z = -1) at t = 7; the centre ray passes
    # the quads' diagonals, so a face can count twice at the same t.
    distinct = sorted({round(t, 9) for t in hits})
    assert distinct == [5.0, 7.0]


def test_inside_is_the_middle_of_the_volume_under_the_cursor():
    point = inside_point(_front_camera(), cube_mesh(), *CENTRE, WIDTH, HEIGHT)
    assert _close(point, (0.0, 0.0, 0.0))


def test_inside_off_centre_keeps_the_ray_and_halves_the_depth():
    camera = _front_camera()
    sx, sy = CENTRE[0] + 40.0, CENTRE[1] + 25.0
    point = inside_point(camera, cube_mesh(), sx, sy, WIDTH, HEIGHT)
    origin, direction = camera.screen_to_ray(sx, sy, WIDTH, HEIGHT)
    # Middle between z = 1 and z = -1 along the ray.
    assert abs(point[2]) < 1e-9
    t = (point[0] - origin[0]) / direction[0]
    assert _close(point, tuple(origin[i] + t * direction[i] for i in range(3)))


def test_inside_on_an_open_sheet_is_the_surface_point():
    mesh = single_quad_mesh()  # z = 0, x/y in [0, 1]
    camera = _front_camera(target=(0.5, 0.5, 0.0))
    point = inside_point(camera, mesh, *CENTRE, WIDTH, HEIGHT)
    assert _close(point, (0.5, 0.5, 0.0))


def test_inside_misses_off_the_mesh():
    assert inside_point(_front_camera(), cube_mesh(), 5.0, 5.0, WIDTH, HEIGHT) is None


def test_inside_skips_hidden_faces():
    camera, mesh = _front_camera(), cube_mesh()
    cache = PickCache()
    # Hide / Isolate hides faces through their corners: hiding the +Z corners hides every face that touches z = 1.
    cache.set_hidden(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[2] == 1.0)
    point = inside_point(camera, mesh, *CENTRE, WIDTH, HEIGHT, cache=cache)
    # Only the back face is left under the cursor: the surface point there.
    assert _close(point, (0.0, 0.0, -1.0))


def test_snap_takes_the_vertex_under_the_cursor():
    camera, mesh = _front_camera(), cube_mesh()
    sx, sy = camera.project_to_screen((1.0, 1.0, 1.0), WIDTH, HEIGHT)
    assert _close(snap_point(camera, mesh, sx + 2.0, sy - 1.0, WIDTH, HEIGHT), (1.0, 1.0, 1.0))


def test_snap_takes_the_edge_point_under_the_cursor():
    camera, mesh = _front_camera(), cube_mesh()
    sx, sy = camera.project_to_screen((1.0, 0.3, 1.0), WIDTH, HEIGHT)
    point = snap_point(camera, mesh, sx, sy, WIDTH, HEIGHT)
    assert point is not None and abs(point[0] - 1.0) < 1e-9 and abs(point[2] - 1.0) < 1e-9
    assert abs(point[1] - 0.3) < 1e-3


def test_snap_on_a_face_falls_back_to_inside():
    camera, mesh = _front_camera(), cube_mesh()
    assert snap_point(camera, mesh, *CENTRE, WIDTH, HEIGHT) is None
    assert _close(place_pivot(camera, mesh, *CENTRE, WIDTH, HEIGHT, snap=True), (0.0, 0.0, 0.0))


def test_off_the_mesh_keeps_the_anchor_depth():
    camera, mesh = _front_camera(), cube_mesh()
    anchor = (0.0, 0.0, -0.5)
    point = place_pivot(camera, mesh, 30.0, 40.0, WIDTH, HEIGHT, anchor=anchor)
    assert abs(point[2] - anchor[2]) < 1e-9
    expected = camera.screen_to_ray(30.0, 40.0, WIDTH, HEIGHT)
    assert point == view_plane_point(camera, 30.0, 40.0, WIDTH, HEIGHT, anchor)
    assert expected is not None


def test_off_the_mesh_without_anchor_uses_the_camera_target_depth():
    camera = _front_camera(target=(0.0, 0.0, 0.25))
    point = place_pivot(camera, cube_mesh(), 30.0, 40.0, WIDTH, HEIGHT)
    assert abs(point[2] - 0.25) < 1e-9


def test_side_view_click_through_a_symmetric_volume_lands_on_the_centre_plane():
    """The jaw case: from the side, a click through the head lands between both cheeks - on the symmetry plane."""
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=math.radians(90), pitch=0.0)
    sx, sy = camera.project_to_screen((0.0, -0.4, 0.6), WIDTH, HEIGHT)
    point = inside_point(camera, cube_mesh(), sx, sy, WIDTH, HEIGHT)
    assert abs(point[0]) < 1e-9


def test_working_pivot_toggle_keeps_the_position():
    pivot = WorkingPivot(object_id=1, position=(1.0, 2.0, 3.0))
    off = pivot.toggled()
    assert not off.enabled and off.position == pivot.position and off.toggled() == pivot


@pytest.mark.parametrize("snap", [False, True])
def test_place_pivot_is_deterministic(snap):
    camera, mesh = _front_camera(), cube_mesh()
    a = place_pivot(camera, mesh, 410.0, 290.0, WIDTH, HEIGHT, snap=snap)
    b = place_pivot(camera, mesh, 410.0, 290.0, WIDTH, HEIGHT, snap=snap)
    assert a == b


# -- WP Ortho / Views: ortho side view and the symmetry plane snap (V-3) ----------------------------------------


def _side_camera(ortho: bool) -> OrbitCamera:
    """Right view: the eye on +X, every ortho ray runs along -X."""
    return OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=math.pi / 2, pitch=0.0, ortho=ortho)


def test_ortho_side_view_puts_the_inside_point_of_a_round_head_on_the_plane():
    """Manu 2026-10-28: in perspective the slanted ray's midpoint drifts off x = 0 on a curved head; in ortho it
    does not (rays along X, entry and exit mirror each other)."""
    mesh = create_sphere()
    for target in ((0.0, 0.5, 0.4), (0.0, -0.3, -0.6), (0.0, 0.8, 0.1)):
        persp, ortho = _side_camera(False), _side_camera(True)
        drift = inside_point(persp, mesh, *persp.project_to_screen(target, WIDTH, HEIGHT), WIDTH, HEIGHT)
        assert abs(drift[0]) > 1e-3
        point = inside_point(ortho, mesh, *ortho.project_to_screen(target, WIDTH, HEIGHT), WIDTH, HEIGHT)
        assert abs(point[0]) < 1e-12
        assert _close(point[1:], target[1:], 1e-9)


def test_plane_snap_within_the_threshold_lands_exactly_on_the_plane():
    camera = _front_camera()
    plane = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    world_per_px = 2.0 * 6.0 * math.tan(math.radians(25.0)) / HEIGHT  # at the target depth
    near = (0.7 * PIVOT_PLANE_SNAP_PX * world_per_px, 0.3, 0.0)
    snapped, on_plane = snap_to_plane(camera, near, *plane, WIDTH, HEIGHT)
    assert on_plane and snapped == (0.0, 0.3, 0.0)
    far = (1.5 * PIVOT_PLANE_SNAP_PX * world_per_px, 0.3, 0.0)
    assert snap_to_plane(camera, far, *plane, WIDTH, HEIGHT) == (far, False)
    assert snap_to_plane(camera, (0.0, 0.2, 0.1), *plane, WIDTH, HEIGHT) == ((0.0, 0.2, 0.1), True)


def test_plane_snap_works_in_perspective_and_ortho_and_for_any_axis():
    for ortho in (False, True):
        camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=0.4, pitch=0.3, ortho=ortho)
        point = (0.2, 0.004, -0.1)
        snapped, on_plane = snap_to_plane(camera, point, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), WIDTH, HEIGHT)
        assert on_plane and snapped == (0.2, 0.0, -0.1)
