"""OrbitCamera.orbit_about / set_view_about (Dynamic Orbit Focus): a rigid rotation of the camera about a
point - the point keeps its pixel in persp and ortho, `distance` stays, `eye = target + distance·dir`."""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from mirai.viewport import vecmath as v
from mirai.viewport.camera import OrbitCamera

W, H = 800, 600
QUARTER = math.pi / 2
MAX_PITCH = math.radians(85)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@pytest.mark.parametrize("ortho", [False, True])
def test_anchor_keeps_its_pixel_over_many_random_steps(ortho):
    rng = random.Random(7)
    camera = OrbitCamera(target=(0.3, 0.1, -0.2), distance=5.0, ortho=ortho)
    anchor = (1.2, 0.7, 0.4)
    start = camera.project_to_screen(anchor, W, H)
    for _ in range(10000):
        camera.orbit_about(anchor, rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05))
        assert abs(camera.pitch) <= MAX_PITCH + 1e-12
    assert _dist(camera.project_to_screen(anchor, W, H), start) < 1e-6
    assert camera.distance == 5.0


@pytest.mark.parametrize("ortho", [False, True])
@pytest.mark.parametrize("yaw,pitch", [(0.0, QUARTER), (QUARTER, -QUARTER), (0.0, 0.0), (math.pi, 0.0)])
def test_snapped_standard_views_keep_the_anchor(ortho, yaw, pitch):
    camera = OrbitCamera(target=(0.0, 0.5, 0.0), distance=6.0, yaw=0.7, pitch=0.4, ortho=ortho)
    anchor = (0.8, -0.3, 0.6)
    start = camera.project_to_screen(anchor, W, H)
    camera.set_view_about(anchor, yaw, pitch)
    assert (camera.yaw, camera.pitch) == (yaw, pitch)
    assert _dist(camera.project_to_screen(anchor, W, H), start) < 1e-6


def test_eye_stays_target_plus_distance_along_the_view():
    camera = OrbitCamera(target=(0.2, 0.0, 0.1), distance=4.0)
    camera.orbit_about((1.0, 1.0, 1.0), 0.6, -0.3)
    forward = camera.basis()[0]
    expected = v.sub(camera.target, v.scale(forward, camera.distance))
    assert all(abs(a - b) < 1e-9 for a, b in zip(camera.eye(), expected))


def test_anchor_on_the_target_is_a_plain_orbit():
    a = OrbitCamera(target=(0.1, 0.2, 0.3))
    b = OrbitCamera(target=(0.1, 0.2, 0.3))
    a.orbit(0.4, 0.2)
    b.orbit_about((0.1, 0.2, 0.3), 0.4, 0.2)
    assert (a.yaw, a.pitch) == (b.yaw, b.pitch)
    assert all(abs(x - y) < 1e-12 for x, y in zip(a.target, b.target))


def test_pitch_is_clamped_before_the_rotation():
    camera = OrbitCamera(pitch=math.radians(84))
    anchor = (1.0, 0.0, 0.0)
    start = camera.project_to_screen(anchor, W, H)
    camera.orbit_about(anchor, 0.0, 0.5)
    assert camera.pitch == pytest.approx(MAX_PITCH)
    assert _dist(camera.project_to_screen(anchor, W, H), start) < 1e-6


def test_ortho_depth_slide_moves_no_point_on_screen():
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0, yaw=0.3, pitch=0.2, ortho=True)
    anchor = (2.0, 1.0, -1.5)
    camera.orbit_about(anchor, 0.8, 0.1)
    # The target lies at the anchor's depth ...
    forward = camera.basis()[0]
    assert abs(v.dot(v.sub(anchor, camera.target), forward)) < 1e-9
    # ... and sliding it along the view axis changes no projection.
    points = [(0.0, 0.0, 0.0), (1.0, -2.0, 0.5), anchor]
    before = [camera.project_to_screen(p, W, H) for p in points]
    camera.target = v.add(camera.target, v.scale(forward, 3.0))
    after = [camera.project_to_screen(p, W, H) for p in points]
    assert all(_dist(a, b) < 1e-9 for a, b in zip(before, after))


def test_each_call_bumps_the_revision_once():
    camera = OrbitCamera()
    rev = camera.camera_revision
    camera.orbit_about((1.0, 0.0, 0.0), 0.1, 0.1)
    assert camera.camera_revision == rev + 1
    camera.set_view_about((1.0, 0.0, 0.0), 0.0, QUARTER, ortho=True)
    assert camera.camera_revision == rev + 2
    assert camera.ortho is True
