"""Gate 7 — Production Camera Verification & Integration.

Verifiziert, dass die bestehende ``OrbitCamera`` korrekt als einzige
autoritative Kamera in den V0.2-Viewport-Pfad eingebunden ist — uber den
tatsachlichen Produktionspfad::

    Application
        |
        +-- OrbitCamera          (self.camera)
        |       |
        |       +-- camera state / matrices
        |
        +-- Viewport              (self.viewport)
                |
                +-- RenderMesh
                        |
                        +-- camera_uniforms

Die Tests gehen NICHT isoliert ``RenderMesh._sync_camera()`` auf, sondern
ausgehend von ``Application.camera`` durch den echten Produktionspfad
(``init_scene`` -> ``bind_camera`` -> ``on_camera_changed`` -> ``sync``).

Referenz-Vertrag: WP-04 Gate 7 Specification, Abschnitt 7 Akzeptanzkriterien.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.application import Application


class ApplicationViewportWiringTests(unittest.TestCase):
    """Task 7.1 — Produktionsintegration: Application <-> Viewport <-> Camera."""

    def setUp(self) -> None:
        self.app = Application()
        self.app.init_scene("cube")

    def test_viewport_exists_after_init_scene(self) -> None:
        """``init_scene()`` erzeugt den V0.2-Viewport."""
        self.assertIsNotNone(self.app.viewport)

    def test_viewport_uses_scene_mesh(self) -> None:
        self.assertIs(self.app.viewport.mesh, self.app.scene.mesh)

    def test_viewport_uses_scene_selection(self) -> None:
        self.assertIs(self.app.viewport.selection, self.app.scene.selection)

    def test_single_authoritative_camera_instance(self) -> None:
        """Application.camera und Viewport.RenderMesh.camera sind dieselbe Instanz."""
        self.assertIs(
            self.app.viewport.render_mesh.camera,
            self.app.camera,
        )

    def test_viewport_is_none_before_init_scene(self) -> None:
        """Kein Viewport vor init_scene() — Application bleibt window-frei."""
        app = Application()
        self.assertIsNone(app.viewport)

    def test_update_viewport_syncs_after_init_scene(self) -> None:
        """``update_viewport()`` ruft ``sync()`` auf, wenn Viewport gebunden ist."""
        self.app.update_viewport(0.016)
        # Sync wurde ausgefuehrt — camera_uniforms sollte existieren.
        self.assertIn("camera_uniforms", self.app.viewport.resource_ids())

    def test_update_viewport_is_noop_without_viewport(self) -> None:
        """``update_viewport()`` darf nicht fehlschlagen, wenn kein Viewport existiert."""
        app = Application()
        app.update_viewport(0.016)  # darf nichts werfen


class CameraLifecycleThroughProductionPathTests(unittest.TestCase):
    """Task 7.2 — Kamera-Lifecycle uber den gesamten Produktionspfad.

    Jede Kameraoperation (orbit/pan/dolly) vergroessert ``camera_revision``
    und loest uber ``on_camera_changed()`` + ``sync()`` eine Aktualisierung
    der ``camera_uniforms`` aus — ohne Geometrie-Invalidierung.
    """

    def setUp(self) -> None:
        self.app = Application()
        self.app.init_scene("cube")
        self.cam = self.app.camera
        self.viewport = self.app.viewport
        # Initial sync: camera_uniforms-Ressource anlegen.
        self.viewport.sync()

    def test_orbit_propagates_to_camera_uniforms(self) -> None:
        rev_before = self.cam.camera_revision
        uniforms_before = list(self.viewport.render_mesh.store.data("camera_uniforms"))

        self.cam.orbit(0.1, 0.05)
        self.assertEqual(self.cam.camera_revision, rev_before + 1)

        self.viewport.on_camera_changed()
        self.viewport.sync()

        uniforms_after = list(self.viewport.render_mesh.store.data("camera_uniforms"))
        self.assertNotEqual(uniforms_before, uniforms_after)

    def test_pan_propagates_to_camera_uniforms(self) -> None:
        rev_before = self.cam.camera_revision
        self.cam.pan(20.0, -10.0, 800, 600)
        self.assertEqual(self.cam.camera_revision, rev_before + 1)

        self.viewport.on_camera_changed()
        self.viewport.sync()

        counters = self.viewport.benchmark_counters
        self.assertGreater(counters["camera_updates"], 0)

    def test_dolly_propagates_to_camera_uniforms(self) -> None:
        rev_before = self.cam.camera_revision
        self.cam.dolly(1.15)
        self.assertEqual(self.cam.camera_revision, rev_before + 1)

        self.viewport.on_camera_changed()
        self.viewport.sync()

        counters = self.viewport.benchmark_counters
        self.assertGreater(counters["camera_updates"], 0)

    def test_camera_revision_accumulates(self) -> None:
        rev_start = self.cam.camera_revision
        self.cam.orbit(0.1, 0.0)
        self.cam.dolly(1.1)
        self.cam.pan(1.0, 1.0, 800, 600)
        self.assertEqual(self.cam.camera_revision, rev_start + 3)

    def test_view_projection_matrices_match_camera_state(self) -> None:
        """Die in camera_uniforms abgelegten Matrizen entsprechen dem aktuellen Kamerazustand."""
        self.cam.orbit(0.3, 0.2)
        self.viewport.on_camera_changed()
        self.viewport.sync()

        uniforms = self.viewport.render_mesh.store.data("camera_uniforms")
        rm = self.viewport.render_mesh

        # _camera_uniforms() baut aus build_view_matrix() + build_projection_matrix(aspect).
        expected_view = list(self.cam.build_view_matrix())
        expected_proj = list(self.cam.build_projection_matrix(rm.aspect))
        expected = expected_view + expected_proj

        self.assertEqual(len(uniforms), len(expected))
        for i, exp_val in enumerate(expected):
            self.assertAlmostEqual(uniforms[i], exp_val, places=6)

    def test_multiple_camera_changes_each_inc_camera_update_counter(self) -> None:
        """Jede Kamera-Aenderung erhoeht camera_updates um genau 1 pro Sync."""
        self.viewport.sync()  # initial allocation
        camera_updates_start = self.viewport.benchmark_counters["camera_updates"]

        for _ in range(5):
            self.cam.orbit(0.01, 0.0)
            self.viewport.on_camera_changed()
            self.viewport.sync()

        camera_updates_end = self.viewport.benchmark_counters["camera_updates"]
        self.assertEqual(camera_updates_end - camera_updates_start, 5)


class CameraGeometryIsolationTests(unittest.TestCase):
    """Task 7.3 — V0.2-Isolation: Kameraaenderungen duerfen Geometrie nicht beruehren.

    Vertrag (VIEWPORT_V02_ARCHITECTURE.md §3):
        Camera change != Geometry change
    """

    def setUp(self) -> None:
        self.app = Application()
        self.app.init_scene("cube")
        self.cam = self.app.camera
        self.viewport = self.app.viewport
        self.rm = self.viewport.render_mesh
        # Initial sync: alle Ressourcen anlegen, camera_uniforms verbindlich.
        self.viewport.sync()

    def test_no_geometry_uploads_on_camera_change(self) -> None:
        before = self.rm.benchmark_counters.get("geometry_uploads", 0)
        self.cam.orbit(0.1, 0.0)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        after = self.rm.benchmark_counters.get("geometry_uploads", 0)
        self.assertEqual(after, before)

    def test_no_structural_rebuilds_on_camera_change(self) -> None:
        before = self.rm.benchmark_counters.get("structural_rebuilds", 0)
        self.cam.orbit(0.1, 0.0)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        after = self.rm.benchmark_counters.get("structural_rebuilds", 0)
        self.assertEqual(after, before)

    def test_no_mesh_rebuilds_on_camera_change(self) -> None:
        before = self.rm.benchmark_counters.get("mesh_rebuilds", 0)
        self.cam.orbit(0.1, 0.0)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        after = self.rm.benchmark_counters.get("mesh_rebuilds", 0)
        self.assertEqual(after, before)

    def test_resource_ids_stable_on_camera_change(self) -> None:
        before_ids = self.viewport.resource_ids()
        self.cam.orbit(0.1, 0.0)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        after_ids = self.viewport.resource_ids()
        self.assertEqual(before_ids, after_ids)

    def test_positions_unchanged_after_camera_change(self) -> None:
        positions_before = list(self.rm.store.data("positions"))
        self.cam.orbit(0.2, 0.1)
        self.cam.dolly(0.9)
        self.cam.pan(5.0, 3.0, 800, 600)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        positions_after = list(self.rm.store.data("positions"))
        self.assertEqual(positions_after, positions_before)

    def test_normals_unchanged_after_camera_change(self) -> None:
        normals_before = list(self.rm.store.data("normals"))
        self.cam.orbit(0.2, 0.1)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        normals_after = list(self.rm.store.data("normals"))
        self.assertEqual(normals_after, normals_before)

    def test_indices_unchanged_after_camera_change(self) -> None:
        indices_before = list(self.rm.store.data("indices"))
        self.cam.orbit(0.2, 0.1)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        indices_after = list(self.rm.store.data("indices"))
        self.assertEqual(indices_after, indices_before)

    def test_no_gpu_resource_creation_on_camera_change(self) -> None:
        creations_before = self.rm.benchmark_counters.get("gpu_resource_creations", 0)
        self.cam.orbit(0.1, 0.0)
        self.viewport.on_camera_changed()
        self.viewport.sync()
        creations_after = self.rm.benchmark_counters.get("gpu_resource_creations", 0)
        self.assertEqual(creations_after, creations_before)

    def test_stress_camera_changes_preserve_all_invariants(self) -> None:
        """100 Orbit/Dolly/Pan-Zyklen: Geometrie bleibt persistent."""
        before_ids = self.viewport.resource_ids()
        positions_before = list(self.rm.store.data("positions"))
        normals_before = list(self.rm.store.data("normals"))
        indices_before = list(self.rm.store.data("indices"))

        struct_before = self.rm.benchmark_counters.get("structural_rebuilds", 0)
        mesh_rebuilds_before = self.rm.benchmark_counters.get("mesh_rebuilds", 0)
        geo_uploads_before = self.rm.benchmark_counters.get("geometry_uploads", 0)
        camera_updates_before = self.rm.benchmark_counters.get("camera_updates", 0)

        for _ in range(100):
            self.cam.orbit(0.01, 0.005)
            self.cam.dolly(1.001)
            self.cam.pan(1.0, 0.5, 800, 600)
            self.viewport.on_camera_changed()
            self.viewport.sync()

        after = self.rm.benchmark_counters
        self.assertEqual(self.viewport.resource_ids(), before_ids)
        self.assertEqual(self.rm.store.data("positions"), positions_before)
        self.assertEqual(self.rm.store.data("normals"), normals_before)
        self.assertEqual(self.rm.store.data("indices"), indices_before)
        self.assertEqual(after.get("structural_rebuilds", 0), struct_before)
        self.assertEqual(after.get("mesh_rebuilds", 0), mesh_rebuilds_before)
        self.assertEqual(after.get("geometry_uploads", 0), geo_uploads_before)
        self.assertGreater(after.get("camera_updates", 0), camera_updates_before)


class CameraUniformsContentTests(unittest.TestCase):
    """Task 7.2 + V0.2-Integration: camera_uniforms enthaelt View und Projection."""

    def setUp(self) -> None:
        self.app = Application()
        self.app.init_scene("cube")
        self.cam = self.app.camera
        self.viewport = self.app.viewport
        self.rm = self.viewport.render_mesh
        self.viewport.sync()  # initial allocation

    def test_camera_uniforms_allocated_after_sync(self) -> None:
        self.assertIn("camera_uniforms", self.viewport.resource_ids())

    def test_camera_uniforms_contain_32_floats(self) -> None:
        """16 (view) + 16 (projection) = 32 floats."""
        uniforms = self.rm.store.data("camera_uniforms")
        self.assertEqual(len(uniforms), 32)

    def test_camera_uniforms_update_only_camera_resource(self) -> None:
        """Nur camera_uniforms wird aktualisiert — nicht positions/normals/indices."""
        before_ids = self.viewport.resource_ids()

        camera_uniforms_id = before_ids["camera_uniforms"]
        positions_id = before_ids["positions"]
        normals_id = before_ids["normals"]
        indices_id = before_ids["indices"]

        self.cam.orbit(0.5, 0.3)
        self.viewport.on_camera_changed()
        self.viewport.sync()

        after_ids = self.viewport.resource_ids()
        self.assertEqual(after_ids["camera_uniforms"], camera_uniforms_id)
        self.assertEqual(after_ids["positions"], positions_id)
        self.assertEqual(after_ids["normals"], normals_id)
        self.assertEqual(after_ids["indices"], indices_id)


if __name__ == "__main__":
    unittest.main()