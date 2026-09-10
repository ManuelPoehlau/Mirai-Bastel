"""OrbitCamera Gate-5-Erweiterung: GL-Matrizen + camera_revision.

Ergänzt tests/test_camera.py (Gate 3/4 Picking-Tests bleiben unverändert)
um die additiv hinzugefügten Methoden für die RenderMesh-Integration.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.viewport.camera import OrbitCamera


class CameraMatrixTests(unittest.TestCase):
    def test_view_matrix_has_16_components(self):
        cam = OrbitCamera()
        self.assertEqual(len(cam.build_view_matrix()), 16)

    def test_projection_matrix_has_16_components(self):
        cam = OrbitCamera()
        self.assertEqual(len(cam.build_projection_matrix(1.777)), 16)

    def test_view_matrix_translation_component_reflects_eye(self):
        cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=10.0)
        view = cam.build_view_matrix()
        # Spalten-Hauptreihenfolge: Translations-Komponenten an Indizes 12-14.
        # Bei distance=10 darf die Kamera nicht im Ursprung sitzen.
        self.assertTrue(any(abs(view[i]) > 1e-6 for i in (12, 13, 14)))

    def test_projection_matrix_changes_with_aspect(self):
        cam = OrbitCamera()
        p1 = cam.build_projection_matrix(1.0)
        p2 = cam.build_projection_matrix(2.0)
        self.assertNotEqual(p1[0], p2[0])


class CameraRevisionTests(unittest.TestCase):
    def test_starts_at_zero(self):
        cam = OrbitCamera()
        self.assertEqual(cam.camera_revision, 0)

    def test_orbit_increments_revision(self):
        cam = OrbitCamera()
        cam.orbit(0.1, 0.0)
        self.assertEqual(cam.camera_revision, 1)

    def test_dolly_increments_revision(self):
        cam = OrbitCamera()
        cam.dolly(1.1)
        self.assertEqual(cam.camera_revision, 1)

    def test_pan_increments_revision(self):
        cam = OrbitCamera()
        cam.pan(1.0, 1.0, 800, 600)
        self.assertEqual(cam.camera_revision, 1)

    def test_multiple_operations_accumulate(self):
        cam = OrbitCamera()
        cam.orbit(0.1, 0.0)
        cam.dolly(1.1)
        cam.pan(1.0, 0.0, 800, 600)
        self.assertEqual(cam.camera_revision, 3)

    def test_picking_calls_do_not_increment_revision(self):
        cam = OrbitCamera()
        cam.project_to_screen((0.0, 0.0, 0.0), 800, 600)
        cam.screen_to_ray(400, 300, 800, 600)
        self.assertEqual(cam.camera_revision, 0)


if __name__ == "__main__":
    unittest.main()
