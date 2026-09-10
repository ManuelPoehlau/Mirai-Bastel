"""Benchmark-Szenarien aus VIEWPORT_V02_ARCHITECTURE.md §8 / §13.

Gate 5 (Viewport Production). Diese Tests verifizieren die geforderten
Zähler-Erwartungen pro Szenario (Camera/Vertex/Selection/Topology/Stress).
Timing wird zusätzlich diagnostisch erfasst, ist aber KEIN Performance-
Claim (siehe VIEWPORT_V02_ARCHITECTURE.md §8 "Explicit Non-Claims") -
insbesondere weil hier `create_cube()` (8V) statt des in der Spec
referenzierten 326V-Meshes läuft (kein OBJ-Importer in `src/core`
vorhanden; siehe Gate 5 Completion Report, Abschnitt "Bekannte
Abweichungen von der Spec").
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import Selection, SelectionMode
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport import Viewport


class BenchmarkScenario1InitialBuild(unittest.TestCase):
    """Szenario 1: Initial Build — Ressourcen/Rebuild erlaubt."""

    def test_initial_build_allocates_all_resources(self):
        vp = Viewport(create_cube())
        ids = vp.resource_ids()
        self.assertEqual(
            set(ids.keys()), {"positions", "normals", "indices", "highlight_flags"}
        )
        self.assertEqual(vp.benchmark_counters["structural_rebuilds"], 1)


class BenchmarkScenario2CameraOrbit(unittest.TestCase):
    """Szenario 2: Camera Orbit/Pan/Zoom (100 Frames) — keine Mesh-Rebuilds."""

    def test_camera_orbit_100_frames_zero_geometry_uploads(self):
        vp = Viewport(create_cube())
        cam = OrbitCamera()
        vp.bind_camera(cam)
        vp.sync()

        before_ids = vp.resource_ids()
        vp.benchmark_counters  # touch (no-op, documents intent)

        for _ in range(100):
            cam.orbit(0.02, 0.01)
            vp.on_camera_changed()
            vp.sync()

        self.assertEqual(vp.resource_ids(), before_ids)
        self.assertEqual(vp.benchmark_counters.get("geometry_uploads", 0), 0)
        self.assertEqual(vp.benchmark_counters.get("mesh_rebuilds"), 1)


class BenchmarkScenario3VertexMove(unittest.TestCase):
    """Szenario 3: Vertex Position Update (10 Vertices) — Partial-Update."""

    def test_ten_vertex_updates_no_structural_rebuild(self):
        mesh = create_cube()
        vp = Viewport(mesh)
        struct_before = vp.benchmark_counters["structural_rebuilds"]

        ids = mesh.all_vertex_ids()
        for i in range(min(10, len(ids))):
            vid = ids[i]
            old = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (old[0] + 0.05, old[1], old[2]))
            vp.on_vertices_moved({vid})
        vp.sync()

        self.assertEqual(vp.benchmark_counters["structural_rebuilds"], struct_before)
        self.assertEqual(
            vp.benchmark_counters["vertex_updates"], min(10, len(ids))
        )


class BenchmarkScenario4Selection(unittest.TestCase):
    """Szenario 4: Selection/Hover — Base-Mesh unverändert."""

    def test_selection_and_hover_leave_base_mesh_untouched(self):
        mesh = create_cube()
        selection = Selection()
        vp = Viewport(mesh, selection=selection)
        before_ids = vp.resource_ids()

        ids = mesh.all_vertex_ids()
        selection.mode = SelectionMode.VERTEX
        selection.set({ids[0]})
        selection.hovered = ids[1]
        vp.on_selection_changed()
        vp.sync()

        self.assertEqual(vp.resource_ids(), before_ids)
        self.assertEqual(vp.benchmark_counters.get("geometry_uploads", 0), 0)


class BenchmarkScenario5Topology(unittest.TestCase):
    """Szenario 5: Topology Change (Edge Split) — Structural Rebuild erlaubt."""

    def test_edge_split_triggers_structural_rebuild(self):
        mesh = create_cube()
        vp = Viewport(mesh)
        before_ids = vp.resource_ids()

        eid = mesh.all_edge_ids()[0]
        mesh.split_edge(eid)
        vp.on_topology_changed()
        vp.sync()

        self.assertNotEqual(vp.resource_ids(), before_ids)
        self.assertGreaterEqual(vp.benchmark_counters["topology_updates"], 1)


class BenchmarkScenario6Stress(unittest.TestCase):
    """Szenario 6: Stress Test (1000 Vertex Moves) — keine Resource-Leaks."""

    def test_1000_moves_no_resource_leak(self):
        mesh = create_cube()
        vp = Viewport(mesh)
        creations_before = vp.benchmark_counters["gpu_resource_creations"]
        ids = mesh.all_vertex_ids()

        for i in range(1000):
            vid = ids[i % len(ids)]
            old = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (old[0], old[1], old[2] + 0.0001))
            vp.on_vertices_moved({vid})
            vp.sync()

        self.assertEqual(
            vp.benchmark_counters["gpu_resource_creations"], creations_before
        )
        self.assertEqual(vp.benchmark_counters["vertex_updates"], 1000)
        # Resource-IDs (Identität) müssen über 1000 Moves stabil bleiben.
        self.assertEqual(len(vp.resource_ids()), 4)


if __name__ == "__main__":
    unittest.main()
