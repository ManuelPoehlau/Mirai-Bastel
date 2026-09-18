"""Integration test for axis="normal" with RotateTool via Application."""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices


class RotateNormalAxisIntegrationTests(unittest.TestCase):
    """End-to-end tests for rotate around selection normal."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")

    def test_rotate_around_face_normal_via_application(self):
        """Rotate around selected face normal through Application context."""
        # Select a face
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        # Activate Rotate tool with axis="normal"
        # Resolve vertices based on selection mode (face → boundary vertices)
        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )

        # Get derived geometry from viewport (it has it after init_scene)
        derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )
        self.assertIsNotNone(derived_geometry)

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "axis": "normal",
            "derived_geometry": derived_geometry,
        }

        # This should not raise an error
        self.assertTrue(self.app.dispatch_command(cmd.ROTATE, context=context))
        self.assertTrue(self.app.tool_manager.is_interacting)

    def test_rotate_normal_axis_on_vertex_selection(self):
        """Rotate around vertex selection normal."""
        # Select some vertices
        self.app.selection.mode = SelectionMode.VERTEX
        vertices = list(self.app.scene.mesh.all_vertex_ids())[:2]
        self.app.selection.set(set(vertices))

        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, SelectionMode.VERTEX
        )

        derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )
        self.assertIsNotNone(derived_geometry)

        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "axis": "normal",
            "derived_geometry": derived_geometry,
        }

        # This should not raise an error
        self.assertTrue(self.app.dispatch_command(cmd.ROTATE, context=context))
        self.assertTrue(self.app.tool_manager.is_interacting)


if __name__ == "__main__":
    unittest.main()
