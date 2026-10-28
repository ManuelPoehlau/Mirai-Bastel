"""OrbitCamera ortho mode and standard views (WP Ortho / Views, Manu V-1/V-2 2026-10-28; contract in
VIEWPORT_V02_ARCHITECTURE §4.1 "Addendum Ortho"): parallel rays, the same projection in `project_to_screen`,
`screen_projector` and the GL matrices, a regular basis at Top / Bottom, perspective unchanged."""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, ObjectTransform, SceneObject
from core.ids import ObjectId
from mirai.object_space import ObjectSpaceCamera
from mirai.viewport import vecmath as v
from mirai.viewport.camera import OrbitCamera, nearest_standard_view

W, H = 800, 600
QUARTER = math.pi / 2


def _cameras():
    """Ortho cameras in a free view, the six standard views and a far-out zoom."""
    out = [OrbitCamera(target=(0.3, -0.2, 0.5), distance=7.0, yaw=0.7, pitch=0.4, ortho=True)]
    for yaw, pitch in ((0.0, 0.0), (QUARTER, 0.0), (math.pi, 0.0), (-QUARTER, 0.0), (0.0, QUARTER), (QUARTER, -QUARTER)):
        out.append(OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=yaw, pitch=pitch, ortho=True))
    out.append(OrbitCamera(target=(1.0, 2.0, 3.0), distance=150.0, yaw=-2.0, pitch=-0.3, ortho=True))
    return out


def _mat_vec(m, p):
    x, y, z, w = p
    return tuple(m[i] * x + m[4 + i] * y + m[8 + i] * z + m[12 + i] * w for i in range(4))


@pytest.mark.parametrize("camera", _cameras())
def test_ortho_rays_are_parallel_and_round_trip_through_the_projection(camera):
    forward = camera.basis()[0]
    for sx, sy in ((0.0, 0.0), (W / 2, H / 2), (W, H), (123.4, 567.8), (799.0, 1.0)):
        origin, direction = camera.screen_to_ray(sx, sy, W, H)
        assert direction == forward
        for t in (1.0, camera.ortho_back, camera.ortho_back + 37.5):
            point = v.add(origin, v.scale(direction, t))
            px, py = camera.project_to_screen(point, W, H)
            assert px == pytest.approx(sx, abs=1e-6) and py == pytest.approx(sy, abs=1e-6)


@pytest.mark.parametrize("camera", _cameras())
def test_screen_projector_is_bit_identical_to_project_to_screen_in_ortho(camera):
    rng = random.Random(7)
    project = camera.screen_projector(W, H)
    points = [tuple(rng.uniform(-200.0, 200.0) for _ in range(3)) for _ in range(300)]
    points.append(camera.ray_origin_toward(camera.target))  # exactly on the origin plane: culled by both
    for point in points:
        assert project(point) == camera.project_to_screen(point, W, H)


@pytest.mark.parametrize("camera", _cameras())
def test_gl_matrices_match_the_ortho_projection_and_depth_range(camera):
    view, proj = camera.build_view_matrix(), camera.build_projection_matrix(W / H)
    assert proj[15] == 1.0 and proj[11] == 0.0  # what the fragment shader tests (`u_proj[3][3] == 1.0`)
    forward = camera.basis()[0]
    for offset in ((0.0, 0.0, 0.0), (1.5, -0.7, 2.0), (-3.0, 2.0, -40.0)):
        point = v.add(camera.target, offset)
        clip = _mat_vec(proj, _mat_vec(view, point + (1.0,)))
        assert clip[3] == pytest.approx(1.0)
        sx, sy = camera.project_to_screen(point, W, H)
        assert (clip[0] + 1.0) * 0.5 * W == pytest.approx(sx, abs=1e-6)
        assert (clip[1] + 1.0) * 0.5 * H == pytest.approx(sy, abs=1e-6)
        assert -1.0 < clip[2] < 1.0
    # The ray origins sit exactly on the near end of the depth range, the far plane at `far`.
    near = _mat_vec(proj, _mat_vec(view, camera.ray_origin_toward(camera.target) + (1.0,)))
    assert near[2] == pytest.approx(-1.0, abs=1e-9)
    far = _mat_vec(proj, _mat_vec(view, v.add(camera.eye(), v.scale(forward, camera.far)) + (1.0,)))
    assert far[2] == pytest.approx(1.0, abs=1e-9)


def test_geometry_behind_the_orbit_eye_stays_visible_and_pickable_in_ortho():
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=2.0, yaw=0.0, pitch=0.0, ortho=True)
    behind_eye = (0.1, 0.1, 5.0)  # eye at z = 2, looking down -z
    assert camera.project_to_screen(behind_eye, W, H) is not None
    assert OrbitCamera(target=(0.0, 0.0, 0.0), distance=2.0, yaw=0.0, pitch=0.0).project_to_screen(
        behind_eye, W, H
    ) is None
    origin = camera.ray_origin_toward(behind_eye)
    assert v.dot(v.sub(behind_eye, origin), camera.basis()[0]) > 0.0


def test_toggling_keeps_the_size_at_the_target_and_dolly_zooms():
    persp = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=0.3, pitch=0.2)
    ortho = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=0.3, pitch=0.2, ortho=True)
    _, right, up = persp.basis()
    for offset in (v.scale(right, 1.3), v.scale(up, -0.8)):
        point = v.add(persp.target, offset)
        a, b = persp.project_to_screen(point, W, H), ortho.project_to_screen(point, W, H)
        assert a == pytest.approx(b, abs=1e-9)
    edge = ortho.project_to_screen(v.scale(right, 1.0), W, H)[0]
    ortho.dolly(0.5)
    assert ortho.project_to_screen(v.scale(right, 1.0), W, H)[0] > edge


def test_pan_and_screen_delta_follow_the_pointer_in_ortho():
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=0.0, pitch=0.0, ortho=True)
    point = (0.4, -0.3, -2.5)
    sx, sy = camera.project_to_screen(point, W, H)
    moved = v.add(point, camera.screen_delta_to_world(point, 30.0, -12.0, W, H))
    mx, my = camera.project_to_screen(moved, W, H)
    assert (mx - sx, my - sy) == pytest.approx((30.0, -12.0), abs=1e-6)
    camera.pan(25.0, 10.0, W, H)  # the object follows the pointer
    px, py = camera.project_to_screen(point, W, H)
    assert (px - sx, py - sy) == pytest.approx((25.0, 10.0), abs=1e-6)


@pytest.mark.parametrize("pitch", [QUARTER, -QUARTER])
@pytest.mark.parametrize("k", [-1, 0, 1, 2, 5])
def test_top_and_bottom_basis_is_orthonormal_with_world_axes(pitch, k):
    camera = OrbitCamera(yaw=k * QUARTER, pitch=pitch)
    forward, right, up = camera.basis()
    for a in (forward, right, up):
        assert v.length(a) == pytest.approx(1.0)
    for a, b in ((forward, right), (forward, up), (right, up)):
        assert v.dot(a, b) == pytest.approx(0.0, abs=1e-12)
    assert forward == pytest.approx((0.0, -1.0 if pitch > 0 else 1.0, 0.0), abs=1e-12)
    # Screen right and up are world axes (no yaw remainder).
    for a in (right, up):
        assert sorted(abs(c) for c in a) == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)
    # Continuous with the free orbit next to the pole.
    near = OrbitCamera(yaw=k * QUARTER, pitch=pitch * (1 - 1e-7)).basis()
    for a, b in zip(near, (forward, right, up)):
        assert a == pytest.approx(b, abs=1e-5)


def test_perspective_basis_is_unchanged_away_from_the_pole():
    camera = OrbitCamera(yaw=0.9, pitch=-0.6)
    forward = v.normalize(v.sub(camera.target, camera.eye()))
    right = v.normalize(v.cross(forward, (0.0, 1.0, 0.0)))
    assert camera.basis() == (forward, right, v.normalize(v.cross(right, forward)))


@pytest.mark.parametrize(
    ("yaw", "pitch", "name", "snap_yaw", "snap_pitch"),
    [
        (0.2, 0.3, "Front", 0.0, 0.0),
        (1.4, -0.2, "Right", QUARTER, 0.0),
        (3.0, 0.1, "Back", math.pi, 0.0),
        (-1.7, 0.4, "Left", -QUARTER, 0.0),
        (4.6, 0.0, "Left", 3 * QUARTER, 0.0),
        (2 * math.pi + 0.1, 0.0, "Front", 2 * math.pi, 0.0),  # stays in the same turn
        (0.4, 1.2, "Top", 0.0, QUARTER),
        (1.2, -1.0, "Bottom", QUARTER, -QUARTER),
    ],
)
def test_nearest_standard_view(yaw, pitch, name, snap_yaw, snap_pitch):
    got = nearest_standard_view(yaw, pitch)
    assert got[0] == name and got[1:] == pytest.approx((snap_yaw, snap_pitch))


@pytest.mark.parametrize("name", ["Front", "Right", "Back", "Left", "Top", "Bottom"])
def test_each_standard_view_looks_along_its_world_axis(name):
    yaw, pitch = {
        "Front": (0.0, 0.0), "Right": (QUARTER, 0.0), "Back": (math.pi, 0.0),
        "Left": (-QUARTER, 0.0), "Top": (0.0, QUARTER), "Bottom": (0.0, -QUARTER),
    }[name]
    assert nearest_standard_view(yaw, pitch)[0] == name
    eye_dir = {
        "Front": (0, 0, 1), "Right": (1, 0, 0), "Back": (0, 0, -1),
        "Left": (-1, 0, 0), "Top": (0, 1, 0), "Bottom": (0, -1, 0),
    }[name]
    forward = OrbitCamera(yaw=yaw, pitch=pitch).basis()[0]
    assert forward == pytest.approx(tuple(-c for c in eye_dir), abs=1e-12)


def test_helpers_in_perspective_and_ortho():
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=0.3, pitch=0.2)
    point = (0.5, 0.2, -0.4)
    assert camera.ray_origin_toward(point) == camera.eye()
    assert camera.view_scale_at(point) == pytest.approx(v.distance(camera.eye(), point))
    camera.set_ortho(True)
    assert camera.view_scale_at(point) == camera.distance
    origin = camera.ray_origin_toward(point)
    forward = camera.basis()[0]
    # On the ray-origin plane, and the parallel ray from there passes through the point.
    assert v.dot(v.sub(origin, camera.eye()), forward) == pytest.approx(-camera.ortho_back)
    rel = v.sub(point, origin)
    assert v.length(v.cross(rel, forward)) == pytest.approx(0.0, abs=1e-9)


def test_revision_bumps_on_every_projection_or_view_change():
    camera = OrbitCamera()
    rev = camera.camera_revision
    assert camera.set_ortho(True) and camera.camera_revision == rev + 1
    assert not camera.set_ortho(True) and camera.camera_revision == rev + 1
    camera.set_view(0.0, QUARTER)
    assert camera.camera_revision == rev + 2 and camera.ortho
    camera.set_view(0.5, 0.1, ortho=False)
    assert camera.camera_revision == rev + 3 and not camera.ortho


def test_object_space_camera_carries_the_ortho_helpers():
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0, yaw=0.4, pitch=0.3, ortho=True)
    obj = SceneObject(ObjectId(0), Mesh(), transform=ObjectTransform(translation=(1.0, 0.5, -2.0), scale=2.0))
    adapter = ObjectSpaceCamera(camera, obj)
    assert adapter.ortho
    point = (0.2, -0.1, 0.3)
    origin = adapter.ray_origin_toward(point)
    ray_origin, direction = adapter.screen_to_ray(*adapter.project_to_screen(point, W, H), W, H)
    # Both on the same parallel ray through `point` (object space).
    rel = v.sub(point, origin)
    assert v.length(v.cross(rel, direction)) == pytest.approx(0.0, abs=1e-9)
    assert v.length(v.cross(v.sub(origin, ray_origin), direction)) == pytest.approx(0.0, abs=1e-9)
    assert adapter.view_scale_at(point) == pytest.approx(camera.distance / 2.0)
