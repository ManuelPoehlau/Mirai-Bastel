"""WP-03: Transform-Tools (RotateTool/ScaleTool) auf Tool-Ebene.

Verifiziert den WP-02-Tool-Vertrag für die neuen Transform-Tools:

* Lifecycle: activate → begin → update* → commit/cancel → deactivate.
* Eingabe-Interpretation: kumulierte Pixel-Distanz → Zielschritt
  (Chunking-Unabhängigkeit: ein großer Drag und zwei halbe Drags liefern
  dasselbe Ergebnis).
* Rotate: Default-Achse = Kamera-Blickachse, Weltachsen-Override.
* Scale: uniform (Default) und achsenbeschränkt, Min-Clamp (keine Spiegelung).
* Commit → genau ein History-Eintrag, Cancel → exakter Vorzustand, keine
  History.
"""
import math
import unittest
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import HistoryStack, Mesh, RotateOperation, ScaleOperation, Scene  # noqa: E402

from viewport.transform_tool import RotateTool, ScaleTool, selection_pivot  # noqa: E402


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class _StubCamera:
    """Kamera-Stub: feste Blickachse +z (wie WP-02-Tests pyglet-frei)."""

    def basis(self):
        return (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)

    def screen_delta_to_world(self, anchor_pos, dx, dy, width, height):
        return (dx, dy, 0.0)


class TransformToolTestBase(unittest.TestCase):
    def _make_scene(self):
        mesh = Mesh()
        ids = (
            mesh.add_vertex((2.0, 0.0, 0.0)),
            mesh.add_vertex((1.0, 0.0, 0.0)),
            mesh.add_vertex((0.0, 3.0, 0.0)),
        )
        scene = Scene()
        scene.mesh = mesh
        scene.history = HistoryStack()
        return scene, ids

    def _positions(self, scene, ids):
        return {vid: scene.mesh.vertex_position(vid) for vid in ids}


class RotateToolTests(TransformToolTestBase):
    def setUp(self):
        self.scene, self.ids = self._make_scene()
        self.tool = RotateTool(self.scene, _StubCamera())

    def test_begin_uses_core_rotate_operation(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        self.assertIsInstance(self.tool.operation, RotateOperation)
        self.assertEqual(self.tool.vertex_ids, set(self.ids))
        self.assertTrue(self.tool.is_interacting)

    def test_default_axis_is_camera_forward(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        self.assertEqual(self.tool.axis, (0.0, 0.0, 1.0))

    def test_world_axis_override(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids), axis="y")
        self.assertEqual(self.tool.axis, (0.0, 1.0, 0.0))
        self.tool.cancel()
        self.tool.deactivate()

    def test_world_axis_override_case_insensitive(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids), axis="Z")
        self.assertEqual(self.tool.axis, (0.0, 0.0, 1.0))
        self.tool.cancel()
        self.tool.deactivate()

    def test_invalid_world_axis_raises(self):
        self.tool.activate()
        with self.assertRaises(ValueError):
            self.tool.begin(vertex_ids=set(self.ids), axis="q")

    def test_update_rotates_around_pivot(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        start = self._positions(self.scene, self.ids)
        expected_angle = RotateTool.RADIANS_PER_PIXEL * 200.0
        self.tool.update(dx=200.0, dy=0.0, width=800, height=600)
        mesh = self.scene.mesh
        pivot = self.tool.operation.pivot
        # Rotation um +z (Rechte-Hand-Regel): z-Komponente bleibt unverändert.
        for vid in self.ids:
            pos = mesh.vertex_position(vid)
            rel = (start[vid][0] - pivot[0], start[vid][1] - pivot[1])
            expected = (
                pivot[0] + rel[0] * math.cos(expected_angle) - rel[1] * math.sin(expected_angle),
                pivot[1] + rel[0] * math.sin(expected_angle) + rel[1] * math.cos(expected_angle),
                pos[2],
            )
            self.assertTrue(_close(pos, expected), msg=f"vertex {vid} falsch rotiert")

    def test_update_is_chunking_independent(self):
        scene_a, ids_a = self._make_scene()
        tool_a = RotateTool(scene_a, _StubCamera())
        tool_a.activate()
        tool_a.begin(vertex_ids=set(ids_a))
        tool_a.update(dx=200.0, dy=0.0, width=800, height=600)

        scene_b, ids_b = self._make_scene()
        tool_b = RotateTool(scene_b, _StubCamera())
        tool_b.activate()
        tool_b.begin(vertex_ids=set(ids_b))
        tool_b.update(dx=100.0, dy=0.0, width=800, height=600)
        tool_b.update(dx=100.0, dy=0.0, width=800, height=600)

        for va, vb in zip(ids_a, ids_b):
            self.assertTrue(
                _close(
                    scene_a.mesh.vertex_position(va),
                    scene_b.mesh.vertex_position(vb),
                ),
                msg="Drag-Chunking darf das Ergebnis nicht ändern",
            )

    def test_commit_creates_single_history_entry(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        self.tool.update(dx=150.0, dy=0.0, width=800, height=600)
        self.tool.update(dx=50.0, dy=0.0, width=800, height=600)
        self.tool.commit()
        self.tool.deactivate()
        self.assertEqual(len(self.scene.history), 1)
        self.assertEqual(self.scene.history._undo_stack[0].description, "Rotate Vertices")

    def test_commit_undo_restores_exact_start(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        start = self._positions(self.scene, self.ids)
        self.tool.update(dx=120.0, dy=0.0, width=800, height=600)
        self.tool.commit()
        self.tool.deactivate()
        self.scene.history.undo()
        for vid in self.ids:
            self.assertEqual(self.scene.mesh.vertex_position(vid), start[vid])

    def test_cancel_restores_exact_start_without_history(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        start = self._positions(self.scene, self.ids)
        self.tool.update(dx=300.0, dy=0.0, width=800, height=600)
        self.tool.cancel()
        self.tool.deactivate()
        for vid in self.ids:
            self.assertEqual(self.scene.mesh.vertex_position(vid), start[vid])
        self.assertEqual(len(self.scene.history), 0)

    def test_explicit_pivot(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids), pivot=(5.0, 5.0, 5.0))
        self.assertEqual(self.tool.operation.pivot, (5.0, 5.0, 5.0))
        self.tool.cancel()
        self.tool.deactivate()

    def test_empty_selection_raises(self):
        self.tool.activate()
        with self.assertRaises(ValueError):
            self.tool.begin(vertex_ids=set())


class ScaleToolTests(TransformToolTestBase):
    def setUp(self):
        self.scene, self.ids = self._make_scene()
        self.tool = ScaleTool(self.scene, _StubCamera())

    def test_begin_uses_core_scale_operation(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        self.assertIsInstance(self.tool.operation, ScaleOperation)
        self.assertEqual(self.tool.axes_mask, (1.0, 1.0, 1.0))

    def test_uniform_update_scales_offsets_from_pivot(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        pivot = self.tool.operation.pivot
        start = self._positions(self.scene, self.ids)
        self.tool.update(dx=100.0, dy=0.0, width=800, height=600)
        expected_factor = 1.0 + ScaleTool.SCALE_PER_PIXEL * 100.0
        for vid in self.ids:
            expected = tuple(
                pivot[i] + expected_factor * (start[vid][i] - pivot[i])
                for i in range(3)
            )
            self.assertTrue(
                _close(self.scene.mesh.vertex_position(vid), expected),
                msg=f"vertex {vid} falsch skaliert",
            )

    def test_axis_constraint_mask(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids), axes="x")
        self.assertEqual(self.tool.axes_mask, (1.0, 0.0, 0.0))
        pivot = self.tool.operation.pivot
        start = self._positions(self.scene, self.ids)
        self.tool.update(dx=100.0, dy=0.0, width=800, height=600)
        expected_factor = 1.0 + ScaleTool.SCALE_PER_PIXEL * 100.0
        for vid in self.ids:
            pos = self.scene.mesh.vertex_position(vid)
            self.assertAlmostEqual(
                pos[0],
                pivot[0] + expected_factor * (start[vid][0] - pivot[0]),
                places=9,
            )
            # Nicht maskierte Achsen bleiben exakt unverändert.
            self.assertEqual(pos[1], start[vid][1])
            self.assertEqual(pos[2], start[vid][2])

    def test_invalid_scale_axis_raises(self):
        self.tool.activate()
        with self.assertRaises(ValueError):
            self.tool.begin(vertex_ids=set(self.ids), axes="w")

    def test_update_is_chunking_independent(self):
        scene_a, ids_a = self._make_scene()
        tool_a = ScaleTool(scene_a, _StubCamera())
        tool_a.activate()
        tool_a.begin(vertex_ids=set(ids_a))
        tool_a.update(dx=60.0, dy=40.0, width=800, height=600)

        scene_b, ids_b = self._make_scene()
        tool_b = ScaleTool(scene_b, _StubCamera())
        tool_b.activate()
        tool_b.begin(vertex_ids=set(ids_b))
        tool_b.update(dx=30.0, dy=20.0, width=800, height=600)
        tool_b.update(dx=30.0, dy=20.0, width=800, height=600)

        for va, vb in zip(ids_a, ids_b):
            self.assertTrue(
                _close(
                    scene_a.mesh.vertex_position(va),
                    scene_b.mesh.vertex_position(vb),
                ),
                msg="Drag-Chunking darf das Ergebnis nicht ändern",
            )

    def test_min_clamp_prevents_mirror(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids), pivot=(0.0, 0.0, 0.0))
        self.tool.update(dx=-100000.0, dy=0.0, width=800, height=600)
        # Zielfaktor ist auf MIN_SCALE begrenzt: positive Offsets bleiben
        # positiv (keine Spiegelung), nichts kollabiert auf 0.
        pos = self.scene.mesh.vertex_position(self.ids[0])
        self.assertTrue(pos[0] > 0.0)
        self.assertTrue(_close(pos, (2.0 * ScaleTool.MIN_SCALE, 0.0, 0.0)))
        self.tool.cancel()
        self.tool.deactivate()

    def test_commit_and_cancel_history_boundaries(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        self.tool.update(dx=80.0, dy=0.0, width=800, height=600)
        self.tool.commit()
        self.tool.deactivate()
        self.assertEqual(len(self.scene.history), 1)
        self.assertEqual(self.scene.history._undo_stack[0].description, "Scale Vertices")

        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.ids))
        self.tool.update(dx=80.0, dy=0.0, width=800, height=600)
        self.tool.cancel()
        self.tool.deactivate()
        # Cancel erzeugt keinen weiteren History-Eintrag.
        self.assertEqual(len(self.scene.history), 1)

    def test_empty_selection_raises(self):
        self.tool.activate()
        with self.assertRaises(ValueError):
            self.tool.begin(vertex_ids=set())


class SelectionPivotTests(TransformToolTestBase):
    def test_selection_pivot_is_centroid(self):
        scene, ids = self._make_scene()
        self.assertTrue(_close(selection_pivot(scene.mesh, ids), (1.0, 1.0, 0.0)))

    def test_selection_pivot_requires_vertices(self):
        scene, _ = self._make_scene()
        with self.assertRaises(ValueError):
            selection_pivot(scene.mesh, set())


if __name__ == "__main__":
    unittest.main()
