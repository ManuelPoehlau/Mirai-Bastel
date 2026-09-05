"""OrbitCamera: Mathematik-/Zustands-Tests (window- und GPU-frei).

Migriert aus `experiments/mirai_bastel_viewport_V1/tests/test_camera_picking.py`
für den Produktions-Viewport-State (src/mirai/viewport/camera.py).
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from mirai.viewport import vecmath as v
from mirai.viewport.camera import OrbitCamera


def _close(a: float, b: float, eps: float = 1e-4) -> bool:
    return abs(a - b) < eps


class OrbitCameraTests(unittest.TestCase):
    def test_eye_distance_matches_configured_distance(self):
        cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0)
        self.assertTrue(_close(v.distance(cam.eye(), cam.target), 5.0))

    def test_target_projects_to_screen_center(self):
        cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0)
        w, h = 800, 600
        projected = cam.project_to_screen(cam.target, w, h)
        self.assertIsNotNone(projected)
        sx, sy = projected
        self.assertTrue(_close(sx, w / 2, eps=1e-2))
        self.assertTrue(_close(sy, h / 2, eps=1e-2))

    def test_screen_to_ray_center_points_toward_target(self):
        cam = OrbitCamera(target=(1.0, 2.0, 3.0), distance=6.0)
        w, h = 800, 600
        _origin, direction = cam.screen_to_ray(w / 2, h / 2, w, h)
        forward, _right, _up = cam.basis()
        self.assertTrue(_close(v.dot(direction, forward), 1.0, eps=1e-3))

    def test_project_and_unproject_roundtrip(self):
        cam = OrbitCamera(
            target=(0.0, 0.0, 0.0),
            distance=8.0,
            yaw=math.radians(30),
            pitch=math.radians(15),
        )
        w, h = 1024, 768
        point = (0.7, -0.4, 0.2)
        projected = cam.project_to_screen(point, w, h)
        self.assertIsNotNone(projected)
        sx, sy = projected
        origin, direction = cam.screen_to_ray(sx, sy, w, h)
        forward, _, _ = cam.basis()
        t = v.dot(v.sub(point, origin), forward) / v.dot(direction, forward)
        hit = v.add(origin, v.scale(direction, t))
        self.assertTrue(v.distance(hit, point) < 1e-3)

    def test_orbit_clamps_pitch(self):
        cam = OrbitCamera()
        cam.orbit(0.0, math.radians(200))
        self.assertLessEqual(cam.pitch, math.radians(85))
        cam.orbit(0.0, -math.radians(200))
        self.assertGreaterEqual(cam.pitch, -math.radians(85))

    def test_dolly_clamps_distance(self):
        cam = OrbitCamera(distance=6.0)
        cam.dolly(0.001)
        self.assertGreaterEqual(cam.distance, 0.5)
        cam.dolly(1e6)
        self.assertLessEqual(cam.distance, 200.0)

    def test_screen_delta_to_world_moves_along_view_plane(self):
        cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0)
        w, h = 800, 600
        point = (0.0, 0.0, 0.0)
        delta = cam.screen_delta_to_world(point, dx=40, dy=0, width=w, height=h)
        self.assertGreater(v.length(delta), 1e-3)
        zero_delta = cam.screen_delta_to_world(point, dx=0, dy=0, width=w, height=h)
        self.assertLess(v.length(zero_delta), 1e-6)

    def test_pan_moves_target_on_view_plane(self):
        cam = OrbitCamera(
            target=(0.0, 0.0, 0.0),
            distance=6.0,
            yaw=math.radians(30),
            pitch=math.radians(15),
        )
        _fwd, right, up = cam.basis()
        before = cam.target
        cam.pan(dx_px=50, dy_px=-30, width=800, height=600)
        delta = v.sub(cam.target, before)
        self.assertGreater(v.length(delta), 1e-6)
        self.assertTrue(_close(v.distance(cam.eye(), cam.target), 6.0, eps=1e-6))
        fwd_after, _r, _u = cam.basis()
        self.assertLess(abs(v.dot(delta, fwd_after)), 1e-6)
        self.assertLess(v.dot(delta, right), 0)
        self.assertGreater(v.dot(delta, up), 0)

    def test_pan_zero_is_noop(self):
        cam = OrbitCamera(target=(1.0, -2.0, 3.0), distance=6.0)
        before = cam.target
        cam.pan(dx_px=0, dy_px=0, width=800, height=600)
        self.assertLess(v.distance(cam.target, before), 1e-12)

    def test_pan_scales_with_distance(self):
        cam_near = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.0)
        cam_far = OrbitCamera(target=(0.0, 0.0, 0.0), distance=12.0)
        cam_near.pan(dx_px=10, dy_px=0, width=800, height=600)
        cam_far.pan(dx_px=10, dy_px=0, width=800, height=600)
        d_near = v.distance(cam_near.target, (0.0, 0.0, 0.0))
        d_far = v.distance(cam_far.target, (0.0, 0.0, 0.0))
        self.assertGreater(d_far, d_near)


if __name__ == "__main__":
    unittest.main()