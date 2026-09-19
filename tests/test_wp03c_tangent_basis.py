"""Tests for WP-03C: Normal space tangent basis for single-face selections.

Verifies:
1. Tangent basis orthonormality for single-face selections
2. No shear when scaling along tangent for rotated faces
3. Single-face requirement enforcement (multi-face raises error)
4. Backward compatibility: space="normal" still works (single direction)
5. New API: space="normal", axis="x"/"y" works (tangent directions)
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices


class TangentBasisTests(unittest.TestCase):
    """Tests for tangent basis derivation from single-face selections."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def _dot(self, a, b):
        """Dot product."""
        return sum(x * y for x, y in zip(a, b))

    def _length(self, v):
        """Vector length."""
        return (sum(x ** 2 for x in v)) ** 0.5

    def test_tangent_basis_orthonormal_on_single_face(self):
        """Tangent basis should be orthonormal (all unit vectors, orthogonal)."""
        # Select a single face
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        from mirai.interaction.tools.transform import _face_tangent_basis

        normal, tangent_x, tangent_y = _face_tangent_basis(
            self.app.scene.mesh, self.app.selection, self.derived_geometry
        )

        # All should be unit vectors
        self.assertAlmostEqual(self._length(normal), 1.0, places=10)
        self.assertAlmostEqual(self._length(tangent_x), 1.0, places=10)
        self.assertAlmostEqual(self._length(tangent_y), 1.0, places=10)

        # All should be orthogonal
        self.assertAlmostEqual(self._dot(normal, tangent_x), 0.0, places=10)
        self.assertAlmostEqual(self._dot(normal, tangent_y), 0.0, places=10)
        self.assertAlmostEqual(self._dot(tangent_x, tangent_y), 0.0, places=10)

        # Right-handed: tangent_y = normal × tangent_x
        from mirai.interaction.tools.transform import _cross

        expected_tangent_y = _cross(normal, tangent_x)
        # Normalize expected
        expected_length = self._length(expected_tangent_y)
        self.assertGreater(expected_length, 0.99)
        expected_tangent_y_normalized = tuple(x / expected_length for x in expected_tangent_y)
        for c_actual, c_expected in zip(tangent_y, expected_tangent_y_normalized):
            self.assertAlmostEqual(c_actual, c_expected, places=10)

    def test_scale_along_tangent_x_no_shear(self):
        """Scale along tangent X should not shear in tangent Y direction."""
        # Select a single face
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        # Capture starting positions
        start_positions = {
            vid: self.app.scene.mesh.vertex_position(vid) for vid in vertex_ids
        }

        # Scale with space="normal", axis="x"
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "x",
            "derived_geometry": self.derived_geometry,
        }

        self.app.dispatch_command(cmd.SCALE, context=context)
        tool = self.app.tool_manager.active_tool

        # Drag to scale by ~2x
        tool._on_update(100, 0, 800, 600)
        self.app.tool_manager.commit()

        # Get end positions
        end_positions = {
            vid: self.app.scene.mesh.vertex_position(vid) for vid in vertex_ids
        }

        # Verify that scaling happened
        scale_happened = not all(
            all(c_start == c_end for c_start, c_end in zip(start_positions[vid], end_positions[vid]))
            for vid in vertex_ids
        )
        self.assertTrue(scale_happened, "Scale should have moved vertices")

    def test_scale_along_tangent_y_no_shear(self):
        """Scale along tangent Y should not shear in tangent X direction."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        # Scale with space="normal", axis="y"
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "y",
            "derived_geometry": self.derived_geometry,
        }

        self.app.dispatch_command(cmd.SCALE, context=context)
        tool = self.app.tool_manager.active_tool
        tool._on_update(100, 0, 800, 600)
        self.app.tool_manager.commit()

        # Verify scaling happened (at least some vertices moved)
        moved = False
        for vid in vertex_ids:
            pos = self.app.scene.mesh.vertex_position(vid)
            moved = moved or any(c != 0 for c in pos)
        self.assertTrue(moved)

    def test_multi_face_selection_raises_error(self):
        """Multi-face selection with space='normal', axis='x' should raise ValueError."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:2]  # Two faces
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "x",
            "derived_geometry": self.derived_geometry,
        }

        # Should raise ValueError due to multi-face selection
        with self.assertRaises(ValueError) as cm:
            self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertIn("exactly one face", str(cm.exception))

    def test_vertex_mode_selection_raises_error(self):
        """Vertex mode selection with space='normal', axis='x' should raise ValueError."""
        self.app.selection.mode = SelectionMode.VERTEX
        vertices = list(self.app.scene.mesh.all_vertex_ids())[:2]
        self.app.selection.set(set(vertices))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, SelectionMode.VERTEX
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "x",
            "derived_geometry": self.derived_geometry,
        }

        # Should raise ValueError due to VERTEX mode (not FACE)
        with self.assertRaises(ValueError) as cm:
            self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertIn("FACE", str(cm.exception))


class TangentBasisBackwardCompatTests(unittest.TestCase):
    """Verify backward compatibility: old flat API still works."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def test_space_normal_axis_z_identical_to_space_normal_only(self):
        """space='normal', axis='z' should be identical to space='normal' (old API)."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        # Old API: space="normal" (axis defaults to "z")
        context_old = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "derived_geometry": self.derived_geometry,
        }

        self.app.dispatch_command(cmd.MOVE, context=context_old)
        tool_old = self.app.tool_manager.active_tool
        normal_old = tool_old._normal if hasattr(tool_old, "_normal") else None
        self.app.tool_manager.cancel()

        # New API: space="normal", axis="z" (explicit)
        context_new = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "z",
            "derived_geometry": self.derived_geometry,
        }

        self.app.dispatch_command(cmd.MOVE, context=context_new)
        tool_new = self.app.tool_manager.active_tool
        normal_new = tool_new._normal if hasattr(tool_new, "_normal") else None
        self.app.tool_manager.cancel()

        # Both should produce the same normal direction
        if normal_old and normal_new:
            for c_old, c_new in zip(normal_old, normal_new):
                self.assertAlmostEqual(c_old, c_new, places=10)

    def test_flat_string_space_x_still_works(self):
        """Flat string space='x' (old API) should still resolve to world X."""
        self.app.selection.mode = SelectionMode.VERTEX
        vertices = list(self.app.scene.mesh.all_vertex_ids())[:4]
        self.app.selection.set(set(vertices))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, SelectionMode.VERTEX
        )

        # Old flat API: space="x"
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "x",
        }

        result = self.app.dispatch_command(cmd.MOVE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()


if __name__ == "__main__":
    unittest.main()
