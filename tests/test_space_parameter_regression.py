"""Regression tests for WP-03B space parameter unification.

Verifies:
1. Backward compatibility with old axis=/axes= parameters
2. New space= parameter is accepted
3. Normal space resolution works across all three tools
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices


class SpaceParameterAPITests(unittest.TestCase):
    """Tests that the space parameter is properly accepted by all tools."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.app.selection.mode = SelectionMode.VERTEX
        vertices = list(self.app.scene.mesh.all_vertex_ids())[:4]
        self.app.selection.set(set(vertices))
        self.vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, SelectionMode.VERTEX
        )
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def test_rotate_backward_compat_axis_parameter(self):
        """Rotate accepts old axis= parameter (backward compatibility)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "axis": "x",  # Old parameter name
        }
        # Should not raise
        result = self.app.dispatch_command(cmd.ROTATE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_rotate_space_parameter(self):
        """Rotate accepts new space= parameter."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "x",  # New parameter name
        }
        # Should not raise
        result = self.app.dispatch_command(cmd.ROTATE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_rotate_space_xy_plane(self):
        """Rotate accepts space='xy' (plane constraint)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "xy",
        }
        result = self.app.dispatch_command(cmd.ROTATE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_move_backward_compat_axis_parameter(self):
        """Move accepts old axis= parameter (backward compatibility)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "axis": "x",
        }
        result = self.app.dispatch_command(cmd.MOVE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_move_space_parameter(self):
        """Move accepts new space= parameter."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "x",
        }
        result = self.app.dispatch_command(cmd.MOVE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_move_space_xy_plane(self):
        """Move accepts space='xy' (plane constraint)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "xy",
        }
        result = self.app.dispatch_command(cmd.MOVE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_scale_backward_compat_axes_parameter(self):
        """Scale accepts old axes= parameter (backward compatibility)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "axes": "x",
        }
        result = self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_scale_space_parameter(self):
        """Scale accepts new space= parameter."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "x",
        }
        result = self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()

    def test_scale_space_xy_plane(self):
        """Scale accepts space='xy' (plane constraint)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "xy",
        }
        result = self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.tool_manager.cancel()


class SpaceParameterNormalTests(unittest.TestCase):
    """Tests for new space='normal' functionality."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def test_rotate_space_normal_on_face_selection(self):
        """Rotate with space='normal' on face selection should work."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "derived_geometry": self.derived_geometry,
        }

        result = self.app.dispatch_command(cmd.ROTATE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)

        # Verify that the axis is set and normalized
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._axis)
        length = sum(c**2 for c in tool._axis) ** 0.5
        self.assertGreater(length, 0.99)  # Roughly normalized
        self.app.tool_manager.cancel()

    def test_move_space_normal_on_face_selection(self):
        """Move with space='normal' on face selection should work."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "derived_geometry": self.derived_geometry,
        }

        result = self.app.dispatch_command(cmd.MOVE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)

        # Verify that the normal is set and normalized
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._normal)
        length = sum(c**2 for c in tool._normal) ** 0.5
        self.assertGreater(length, 0.99)
        self.app.tool_manager.cancel()

    def test_scale_space_normal_on_face_selection(self):
        """Scale with space='normal' on face selection should work."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "derived_geometry": self.derived_geometry,
        }

        result = self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertTrue(result)
        self.assertTrue(self.app.tool_manager.is_interacting)

        # Verify that the normal is set and normalized
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._normal)
        length = sum(c**2 for c in tool._normal) ** 0.5
        self.assertGreater(length, 0.99)
        self.app.tool_manager.cancel()

    def test_move_space_normal_missing_geometry_raises(self):
        """Move with space='normal' but no derived_geometry should raise."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            # Missing derived_geometry
        }

        # Should raise ValueError due to missing derived_geometry
        with self.assertRaises(ValueError) as cm:
            self.app.dispatch_command(cmd.MOVE, context=context)
        self.assertIn("derived_geometry", str(cm.exception))

    def test_rotate_space_normal_missing_geometry_raises(self):
        """Rotate with space='normal' but no derived_geometry should raise."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            # Missing derived_geometry
        }

        # Should raise ValueError due to missing derived_geometry
        with self.assertRaises(ValueError) as cm:
            self.app.dispatch_command(cmd.ROTATE, context=context)
        self.assertIn("derived_geometry", str(cm.exception))

    def test_scale_space_normal_missing_geometry_raises(self):
        """Scale with space='normal' but no derived_geometry should raise."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            # Missing derived_geometry
        }

        # Should raise ValueError due to missing derived_geometry
        with self.assertRaises(ValueError) as cm:
            self.app.dispatch_command(cmd.SCALE, context=context)
        self.assertIn("derived_geometry", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
