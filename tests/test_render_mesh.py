"""RenderMesh: zentrale V0.2-Architektur-Invarianten.

Gate 5 (Viewport Production). Diese Tests sind die formale Absicherung der
in VIEWPORT_V02_ARCHITECTURE.md §13 geforderten Test-Matrix (Camera/
Position/Selection/Topology/Persistence), gegen die reale `core.Mesh`-API.

Headless (TraceStore, kein GL-Kontext nötig).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import Selection, SelectionMode
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport.overlay import SelectionOverlay
from viewport.render_mesh import RenderMesh


class _StubMaterial:
    """Minimaler Material-Stub für Tests der `material`-Kategorie."""

    def __init__(self):
        self.color = (1.0, 0.5, 0.0)

    def uniform_packet(self) -> list[float]:
        return list(self.color)


def _build(with_camera: bool = False, with_material: bool = False):
    mesh = create_cube()
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay)
    if with_camera:
        rm.bind_camera(OrbitCamera())
    if with_material:
        rm.bind_material(_StubMaterial())
    return mesh, selection, overlay, rm


class InitialBuildTests(unittest.TestCase):
    """Test 1 (§13): Initial Build — Ressourcen/Rebuild erlaubt."""

    def test_build_allocates_core_resources(self):
        _mesh, _sel, _overlay, rm = _build()
        ids = rm.resource_ids()
        self.assertIn("positions", ids)
        self.assertIn("normals", ids)
        self.assertIn("indices", ids)
        self.assertIn("highlight_flags", ids)

    def test_build_counts_as_structural(self):
        _mesh, _sel, _overlay, rm = _build()
        counters = rm.benchmark_counters
        self.assertEqual(counters.get("structural_rebuilds"), 1)
        self.assertEqual(counters.get("mesh_rebuilds"), 1)

    def test_positions_buffer_matches_mesh(self):
        mesh, _sel, _overlay, rm = _build()
        flat = rm.store.data("positions")
        for vid in mesh.all_vertex_ids():
            idx = rm.vertex_index_of(vid)
            expected = mesh.vertex_position(vid)
            actual = tuple(flat[idx * 3: idx * 3 + 3])
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, places=6)


class CameraUpdateTests(unittest.TestCase):
    """Test 2 (§13): Camera Orbit/Pan/Zoom — keine Mesh-Rebuilds/Uploads."""

    def test_camera_orbit_never_touches_geometry(self):
        _mesh, _sel, _overlay, rm = _build(with_camera=True)
        rm.mark_camera_dirty()
        rm.sync()  # initial camera_uniforms allocation (counts as 1 update)

        before_ids = rm.resource_ids()
        pos_before = list(rm.store.data("positions"))
        normals_before = list(rm.store.data("normals"))
        struct_before = rm.benchmark_counters["structural_rebuilds"]
        camera_updates_before = rm.benchmark_counters["camera_updates"]

        cam = rm.camera
        for _ in range(100):
            cam.orbit(0.01, 0.0)
            rm.mark_camera_dirty()
            rm.sync()

        self.assertEqual(rm.resource_ids(), before_ids)
        self.assertEqual(rm.store.data("positions"), pos_before)
        self.assertEqual(rm.store.data("normals"), normals_before)
        self.assertEqual(rm.benchmark_counters["structural_rebuilds"], struct_before)
        self.assertEqual(rm.benchmark_counters.get("geometry_uploads", 0), 0)
        self.assertEqual(
            rm.benchmark_counters["camera_updates"] - camera_updates_before, 100
        )

    def test_camera_dolly_and_pan_also_isolated(self):
        _mesh, _sel, _overlay, rm = _build(with_camera=True)
        rm.mark_camera_dirty()
        rm.sync()
        before_ids = rm.resource_ids()

        cam = rm.camera
        cam.dolly(1.1)
        rm.mark_camera_dirty()
        cam.pan(3.0, -2.0, 800, 600)
        rm.mark_camera_dirty()
        rm.sync()

        self.assertEqual(rm.resource_ids(), before_ids)
        self.assertEqual(rm.benchmark_counters.get("geometry_uploads", 0), 0)

    def test_camera_uniforms_reflect_current_matrices(self):
        _mesh, _sel, _overlay, rm = _build(with_camera=True)
        rm.mark_camera_dirty(aspect=1.5)
        rm.sync()
        uniforms = rm.store.data("camera_uniforms")
        expected = list(rm.camera.build_view_matrix()) + list(
            rm.camera.build_projection_matrix(1.5)
        )
        self.assertEqual(uniforms, expected)

    def test_no_camera_bound_sync_is_noop_for_camera_category(self):
        _mesh, _sel, _overlay, rm = _build(with_camera=False)
        rm.mark_camera_dirty()
        rm.sync()  # must not raise despite self.camera is None
        self.assertNotIn("camera_uniforms", rm.resource_ids())


class VertexMoveTests(unittest.TestCase):
    """Test 4 (§13): Vertex Move — kein Topology-Rebuild, gezieltes Update."""

    def test_single_vertex_move_no_structural_rebuild(self):
        mesh, _sel, _overlay, rm = _build()
        before_ids = rm.resource_ids()
        struct_before = rm.benchmark_counters["structural_rebuilds"]

        vid = mesh.all_vertex_ids()[0]
        old = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (old[0] + 1.0, old[1], old[2]))
        rm.mark_vertices_dirty({vid})
        rm.sync()

        self.assertEqual(rm.resource_ids(), before_ids)
        self.assertEqual(rm.benchmark_counters["structural_rebuilds"], struct_before)
        self.assertEqual(rm.benchmark_counters.get("topology_updates", 0), 0)

    def test_single_vertex_move_updates_only_affected_normals(self):
        mesh, _sel, _overlay, rm = _build()
        vid = mesh.all_vertex_ids()[0]
        affected_faces = rm.derived.vertex_to_faces[vid]
        expected_affected_vertices = set()
        for f in affected_faces:
            expected_affected_vertices.update(mesh.face_vertices(f))

        old = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (old[0], old[1] + 1.0, old[2]))
        rm.mark_vertices_dirty({vid})
        rm.sync()

        # Genau ein Vertex-Update wurde gezählt.
        self.assertEqual(rm.benchmark_counters["vertex_updates"], 1)
        # Partial-Updates: 1 Position + len(betroffene Normalen).
        expected_partial = 1 + len(expected_affected_vertices)
        self.assertEqual(rm.benchmark_counters["partial_updates"], expected_partial)

    def test_moved_vertex_position_reflected_in_buffer(self):
        mesh, _sel, _overlay, rm = _build()
        vid = mesh.all_vertex_ids()[0]
        new_pos = (5.0, 6.0, 7.0)
        mesh.set_vertex_position(vid, new_pos)
        rm.mark_vertices_dirty({vid})
        rm.sync()

        idx = rm.vertex_index_of(vid)
        stored = rm.store.data("positions")[idx * 3: idx * 3 + 3]
        for a, b in zip(stored, new_pos):
            self.assertAlmostEqual(a, b, places=6)

    def test_unaffected_vertex_position_untouched(self):
        mesh, _sel, _overlay, rm = _build()
        v0 = mesh.all_vertex_ids()[0]
        v1 = mesh.all_vertex_ids()[1]
        # v1 sollte nicht incident zu allen Faces von v0 sein - wir prüfen
        # stattdessen direkt den Puffer eines Vertex, der garantiert nicht
        # in der affected_neighborhood von v0 liegt.
        affected_faces, affected_verts = rm.derived.affected_neighborhood(mesh, {v0})
        untouched = [
            v for v in mesh.all_vertex_ids() if v not in affected_verts
        ]
        self.assertTrue(untouched, "Erwartet mind. einen unbetroffenen Vertex im Cube")
        target = untouched[0]
        idx = rm.vertex_index_of(target)
        before = rm.store.data("positions")[idx * 3: idx * 3 + 3]

        old = mesh.vertex_position(v0)
        mesh.set_vertex_position(v0, (old[0] + 2.0, old[1], old[2]))
        rm.mark_vertices_dirty({v0})
        rm.sync()

        after = rm.store.data("positions")[idx * 3: idx * 3 + 3]
        self.assertEqual(before, after)

    def test_bounds_recalculated_on_move(self):
        mesh, _sel, _overlay, rm = _build()
        vid = mesh.all_vertex_ids()[0]
        old = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (old[0] + 10.0, old[1], old[2]))
        rm.mark_vertices_dirty({vid})
        rm.sync()

        self.assertEqual(rm.benchmark_counters["bounds_recalculations"], 1)
        self.assertGreaterEqual(rm.derived.bounds_max[0], old[0] + 10.0 - 1e-6)

    def test_multiple_vertices_moved_together_counted_once_per_vertex(self):
        mesh, _sel, _overlay, rm = _build()
        ids = mesh.all_vertex_ids()[:3]
        for vid in ids:
            old = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (old[0], old[1] + 0.1, old[2]))
        rm.mark_vertices_dirty(set(ids))
        rm.sync()
        self.assertEqual(rm.benchmark_counters["vertex_updates"], 3)


class SelectionOverlayIsolationTests(unittest.TestCase):
    """Test 3 (§13): Selection — kein Base-Mesh-/Structural-Rebuild."""

    def test_selection_does_not_touch_base_geometry(self):
        mesh, selection, _overlay, rm = _build()
        before_ids = rm.resource_ids()
        pos_before = list(rm.store.data("positions"))
        normals_before = list(rm.store.data("normals"))
        struct_before = rm.benchmark_counters["structural_rebuilds"]

        vid = mesh.all_vertex_ids()[0]
        selection.mode = SelectionMode.VERTEX
        selection.set({vid})
        rm.mark_selection_dirty()
        rm.sync()

        self.assertEqual(rm.resource_ids(), before_ids)
        self.assertEqual(rm.store.data("positions"), pos_before)
        self.assertEqual(rm.store.data("normals"), normals_before)
        self.assertEqual(rm.benchmark_counters["structural_rebuilds"], struct_before)
        self.assertEqual(rm.benchmark_counters.get("geometry_uploads", 0), 0)

    def test_selection_updates_highlight_flags_correctly(self):
        mesh, selection, _overlay, rm = _build()
        vid = mesh.all_vertex_ids()[2]
        selection.mode = SelectionMode.VERTEX
        selection.set({vid})
        rm.mark_selection_dirty()
        rm.sync()

        idx = rm.vertex_index_of(vid)
        flags = rm.store.data("highlight_flags")
        self.assertEqual(flags[idx], 1.0)
        self.assertEqual(sum(flags), 1.0)

    def test_edge_mode_selection_highlights_both_endpoints(self):
        mesh, selection, _overlay, rm = _build()
        eid = mesh.all_edge_ids()[0]
        va, vb = mesh.edge_vertices(eid)
        selection.mode = SelectionMode.EDGE
        selection.set({eid})
        rm.mark_selection_dirty()
        rm.sync()

        flags = rm.store.data("highlight_flags")
        self.assertEqual(flags[rm.vertex_index_of(va)], 1.0)
        self.assertEqual(flags[rm.vertex_index_of(vb)], 1.0)

    def test_hover_is_independent_of_selection(self):
        mesh, selection, _overlay, rm = _build()
        selected = mesh.all_vertex_ids()[0]
        hovered = mesh.all_vertex_ids()[1]
        selection.mode = SelectionMode.VERTEX
        selection.set({selected})
        selection.hovered = hovered
        rm.mark_selection_dirty()
        rm.sync()

        flags = rm.store.data("highlight_flags")
        self.assertEqual(flags[rm.vertex_index_of(selected)], 1.0)
        self.assertEqual(flags[rm.vertex_index_of(hovered)], 1.0)

    def test_clearing_selection_clears_flags(self):
        mesh, selection, _overlay, rm = _build()
        vid = mesh.all_vertex_ids()[0]
        selection.mode = SelectionMode.VERTEX
        selection.set({vid})
        rm.mark_selection_dirty()
        rm.sync()

        selection.clear()
        rm.mark_selection_dirty()
        rm.sync()

        flags = rm.store.data("highlight_flags")
        self.assertEqual(sum(flags), 0.0)


class MaterialUpdateTests(unittest.TestCase):
    def test_material_update_isolated_from_geometry(self):
        _mesh, _sel, _overlay, rm = _build(with_material=True)
        rm.mark_material_dirty()
        rm.sync()  # initial material_uniforms allocation

        before_ids = rm.resource_ids()
        pos_before = list(rm.store.data("positions"))
        updates_before = rm.benchmark_counters["material_updates"]

        rm.material.color = (0.1, 0.2, 0.3)
        rm.mark_material_dirty()
        rm.sync()

        self.assertEqual(rm.resource_ids(), before_ids)
        self.assertEqual(rm.store.data("positions"), pos_before)
        self.assertEqual(rm.store.data("material_uniforms"), [0.1, 0.2, 0.3])
        self.assertEqual(rm.benchmark_counters["material_updates"] - updates_before, 1)


class TopologyChangeTests(unittest.TestCase):
    """Test 5 (§13): Topology Change — Structural Rebuild erlaubt."""

    def test_edge_split_triggers_structural_rebuild(self):
        mesh, _sel, _overlay, rm = _build()
        before_ids = rm.resource_ids()

        eid = mesh.all_edge_ids()[0]
        mesh.split_edge(eid)
        rm.mark_topology_dirty()
        rm.sync()

        after_ids = rm.resource_ids()
        self.assertNotEqual(before_ids, after_ids)
        self.assertGreaterEqual(rm.benchmark_counters["topology_updates"], 1)

    def test_topology_change_updates_vertex_count_in_buffers(self):
        mesh, _sel, _overlay, rm = _build()
        eid = mesh.all_edge_ids()[0]
        mesh.split_edge(eid)
        rm.mark_topology_dirty()
        rm.sync()

        n_verts = len(mesh.all_vertex_ids())
        self.assertEqual(len(rm.store.data("positions")), n_verts * 3)
        self.assertEqual(len(rm.store.data("normals")), n_verts * 3)
        self.assertEqual(len(rm.store.data("highlight_flags")), n_verts)

    def test_topology_change_clears_stale_modified_vertices(self):
        mesh, _sel, _overlay, rm = _build()
        vid = mesh.all_vertex_ids()[0]
        rm.mark_vertices_dirty({vid})  # noch nicht synced

        eid = mesh.all_edge_ids()[0]
        mesh.split_edge(eid)
        rm.mark_topology_dirty()
        rm.sync()  # darf nicht auf stale vertex_id aus vor-Split-Zustand zugreifen

        self.assertEqual(rm.dirty.modified_vertices, set())

    def test_new_vertex_from_split_has_valid_normal(self):
        mesh, _sel, _overlay, rm = _build()
        eid = mesh.all_edge_ids()[0]
        new_vid, _e1, _e2 = mesh.split_edge(eid)
        rm.mark_topology_dirty()
        rm.sync()

        self.assertIn(new_vid, rm.derived.vertex_normals)
        idx = rm.vertex_index_of(new_vid)
        self.assertLess(idx, len(mesh.all_vertex_ids()))


class ResourcePersistenceTests(unittest.TestCase):
    """Test 6 (§13): Resource Persistence bei nicht-strukturellen Änderungen."""

    def test_mixed_interactions_preserve_resource_identity(self):
        mesh, selection, _overlay, rm = _build(with_camera=True)
        rm.mark_camera_dirty()
        rm.sync()
        before_ids = rm.resource_ids()

        cam = rm.camera
        for i in range(10):
            cam.orbit(0.02, 0.0)
            rm.mark_camera_dirty()

            vid = mesh.all_vertex_ids()[i % len(mesh.all_vertex_ids())]
            old = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (old[0] + 0.01, old[1], old[2]))
            rm.mark_vertices_dirty({vid})

            selection.mode = SelectionMode.VERTEX
            selection.toggle(vid)
            rm.mark_selection_dirty()

            rm.sync()

        self.assertEqual(rm.resource_ids(), before_ids)

    def test_no_gpu_resource_creation_during_stress_moves(self):
        mesh, _sel, _overlay, rm = _build()
        creations_before = rm.benchmark_counters["gpu_resource_creations"]

        for i in range(1000):
            vid = mesh.all_vertex_ids()[i % len(mesh.all_vertex_ids())]
            old = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (old[0], old[1], old[2] + 0.001))
            rm.mark_vertices_dirty({vid})
            rm.sync()

        self.assertEqual(
            rm.benchmark_counters["gpu_resource_creations"], creations_before
        )
        self.assertEqual(rm.benchmark_counters["vertex_updates"], 1000)


class InterleavingTests(unittest.TestCase):
    """Mehrere Update-Kategorien im selben Frame (vor einem `sync()`)."""

    def test_camera_and_selection_and_position_in_same_frame(self):
        mesh, selection, _overlay, rm = _build(with_camera=True)
        rm.mark_camera_dirty()
        rm.sync()  # initial camera_uniforms allocation
        camera_updates_before = rm.benchmark_counters["camera_updates"]

        vid = mesh.all_vertex_ids()[0]
        old = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (old[0] + 1.0, old[1], old[2]))

        rm.camera.orbit(0.05, 0.0)
        rm.mark_camera_dirty()
        rm.mark_vertices_dirty({vid})
        selection.mode = SelectionMode.VERTEX
        selection.set({vid})
        rm.mark_selection_dirty()

        rm.sync()

        counters = rm.benchmark_counters
        self.assertEqual(counters["camera_updates"] - camera_updates_before, 1)
        self.assertEqual(counters["vertex_updates"], 1)
        self.assertEqual(counters["selection_updates"], 1)
        # dirty state muss nach sync() vollstaendig zurueckgesetzt sein
        self.assertFalse(rm.dirty.camera)
        self.assertFalse(rm.dirty.geometry)
        self.assertFalse(rm.dirty.selection)
        self.assertEqual(rm.dirty.modified_vertices, set())


if __name__ == "__main__":
    unittest.main()
