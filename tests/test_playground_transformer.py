"""Playground Transformer — Tests für AP-04 Phase 1 Transform Functions.

Tests für die Wrapper-Funktionen in playground/transformer.py:
- create_tool_for_type: Factory für Move/Rotate/Scale Tools
- begin_transform: Tool-Aktivierung + begin()
- update_transform: Drag-Input verarbeiten
- commit_transform: Transform speichern
- cancel_transform: Transform verwerfen

Hinweis: Die Production-Tools (MoveTool, RotateTool, ScaleTool) erfordern
ein vollständiges Scene/Camera-Setup. Diese Tests fokussieren auf die
Wrapper-Logik und error handling ohne GL.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401

# Bootstrap Playground-Pfade (Repo-Root + src/)
from playground._paths import ensure_paths
ensure_paths()

from playground.transformer import (
    create_tool_for_type,
    begin_transform,
    update_transform,
    commit_transform,
    cancel_transform,
)


class TestCreateToolForType(unittest.TestCase):
    """Test create_tool_for_type Factory."""

    def test_create_move_tool(self):
        """create_tool_for_type('move') gibt MoveTool zurück."""
        tool = create_tool_for_type("move")
        self.assertIsNotNone(tool)
        self.assertTrue(hasattr(tool, "activate"))
        self.assertTrue(hasattr(tool, "begin"))
        self.assertTrue(hasattr(tool, "update"))
        self.assertTrue(hasattr(tool, "commit"))
        self.assertTrue(hasattr(tool, "cancel"))

    def test_create_rotate_tool(self):
        """create_tool_for_type('rotate') gibt RotateTool zurück."""
        tool = create_tool_for_type("rotate")
        self.assertIsNotNone(tool)
        self.assertTrue(hasattr(tool, "activate"))
        self.assertTrue(hasattr(tool, "begin"))

    def test_create_scale_tool(self):
        """create_tool_for_type('scale') gibt ScaleTool zurück."""
        tool = create_tool_for_type("scale")
        self.assertIsNotNone(tool)
        self.assertTrue(hasattr(tool, "activate"))
        self.assertTrue(hasattr(tool, "begin"))

    def test_create_tool_unknown_type(self):
        """create_tool_for_type mit ungültigem Typ wirft ValueError."""
        with self.assertRaises(ValueError):
            create_tool_for_type("invalid")


class TestTransformFunctions(unittest.TestCase):
    """Test der Transformer-Wrapper-Funktionen."""

    def setUp(self):
        """Setze Mock-Objekte auf."""
        self.mock_tool = MagicMock()
        self.mock_scene = MagicMock()
        self.mock_camera = MagicMock()
        self.mock_selection = MagicMock()

    def test_begin_transform_with_empty_selection(self):
        """begin_transform gibt False zurück wenn Selektion leer."""
        self.mock_selection.is_empty.return_value = True
        result = begin_transform(
            self.mock_tool,
            self.mock_scene,
            self.mock_camera,
            self.mock_selection,
        )
        self.assertFalse(result)
        self.mock_tool.begin.assert_not_called()

    def test_begin_transform_with_selection(self):
        """begin_transform konvertiert Faces zu Vertices und ruft begin() auf."""
        self.mock_selection.is_empty.return_value = False
        self.mock_selection.faces = [1, 2]  # Zwei selektierte Faces
        self.mock_tool.is_active = False
        self.mock_tool.begin.return_value = None

        # Mock mesh.face_vertices() → gibt Vertices für jede Face zurück
        self.mock_scene.mesh.face_vertices.side_effect = lambda face_id: {
            1: [10, 11, 12],  # Face 1 hat Vertices 10, 11, 12
            2: [12, 13, 14],  # Face 2 hat Vertices 12, 13, 14 (gemeinsamer Vertex 12)
        }.get(face_id, [])

        result = begin_transform(
            self.mock_tool,
            self.mock_scene,
            self.mock_camera,
            self.mock_selection,
        )

        self.assertTrue(result)
        self.mock_tool.activate.assert_called_once()
        self.mock_tool.begin.assert_called_once()
        # Überprüfe, dass vertex_ids aus den Faces zusammengesetzt wurde
        call_args = self.mock_tool.begin.call_args
        vertex_ids = call_args.kwargs.get('vertex_ids')
        self.assertEqual(vertex_ids, {10, 11, 12, 13, 14})

    def test_begin_transform_already_active(self):
        """begin_transform ruft activate() nicht auf wenn Tool bereits aktiv."""
        self.mock_selection.is_empty.return_value = False
        self.mock_selection.faces = [1]
        self.mock_scene.mesh.face_vertices.return_value = [10, 11, 12]
        self.mock_tool.is_active = True
        self.mock_tool.begin.return_value = None

        result = begin_transform(
            self.mock_tool,
            self.mock_scene,
            self.mock_camera,
            self.mock_selection,
        )

        self.assertTrue(result)
        self.mock_tool.activate.assert_not_called()

    def test_update_transform_not_interacting(self):
        """update_transform gibt False zurück wenn Tool nicht interagiert."""
        self.mock_tool.is_interacting = False
        result = update_transform(
            self.mock_tool, 10.0, 5.0, 800, 600, self.mock_camera
        )
        self.assertFalse(result)
        self.mock_tool.update.assert_not_called()

    def test_update_transform_interacting(self):
        """update_transform ruft tool.update() auf wenn interagiert."""
        self.mock_tool.is_interacting = True
        self.mock_tool.update.return_value = None

        result = update_transform(
            self.mock_tool, 10.0, 5.0, 800, 600, self.mock_camera
        )

        self.assertTrue(result)
        self.mock_tool.update.assert_called_once()

    def test_commit_transform_not_interacting(self):
        """commit_transform gibt False zurück wenn nicht interagiert."""
        self.mock_tool.is_interacting = False
        result = commit_transform(self.mock_tool)
        self.assertFalse(result)
        self.mock_tool.commit.assert_not_called()

    def test_commit_transform_interacting(self):
        """commit_transform ruft tool.commit() auf wenn interagiert."""
        self.mock_tool.is_interacting = True
        self.mock_tool.commit.return_value = None

        result = commit_transform(self.mock_tool)

        self.assertTrue(result)
        self.mock_tool.commit.assert_called_once()

    def test_cancel_transform_not_interacting(self):
        """cancel_transform gibt False zurück wenn nicht interagiert."""
        self.mock_tool.is_interacting = False
        result = cancel_transform(self.mock_tool)
        self.assertFalse(result)
        self.mock_tool.cancel.assert_not_called()

    def test_cancel_transform_interacting(self):
        """cancel_transform ruft tool.cancel() auf wenn interagiert."""
        self.mock_tool.is_interacting = True
        self.mock_tool.cancel.return_value = None

        result = cancel_transform(self.mock_tool)

        self.assertTrue(result)
        self.mock_tool.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
