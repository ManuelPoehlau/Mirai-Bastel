"""Tests for selection_normal() helper and axis="normal" for RotateTool."""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from core import Mesh, RotateOperation, SelectionMode
from mirai.interaction.tools.selection_helpers import selection_normal
from viewport import DerivedGeometry


def _close(a, b, tol=1e-6):
    """Check if two vectors are close."""
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class SelectionNormalTests(unittest.TestCase):
    """Tests for selection_normal() function."""

    def _make_mesh_with_faces(self):
        """Create a simple two-face mesh."""
        mesh = Mesh()
        # Face 1 (XY plane, normal pointing +Z)
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        v2 = mesh.add_vertex((1.0, 1.0, 0.0))
        v3 = mesh.add_vertex((0.0, 1.0, 0.0))
        f0 = mesh.add_face([v0, v1, v2, v3])

        # Face 2 (XZ plane, normal pointing +Y) adjacent to edge v1-v2
        v4 = mesh.add_vertex((1.0, 0.0, 1.0))
        v5 = mesh.add_vertex((1.0, 1.0, 1.0))
        f1 = mesh.add_face([v1, v4, v5, v2])

        return mesh, (v0, v1, v2, v3, v4, v5), (f0, f1)

    def test_face_mode_average_of_face_normals(self):
        """Face selection: average of selected face normals."""
        mesh, (v0, v1, v2, v3, v4, v5), (f0, f1) = self._make_mesh_with_faces()
        derived = DerivedGeometry(mesh)

        from core import Selection

        sel = Selection()
        sel.mode = SelectionMode.FACE
        sel.set({f0})

        normal = selection_normal(derived, mesh, sel, SelectionMode.FACE)
        # Face 0 is in XY plane, normal should point +Z
        self.assertTrue(_close(normal, (0.0, 0.0, 1.0)))

    def test_vertex_mode_average_of_vertex_normals(self):
        """Vertex selection: average of selected vertex normals."""
        mesh, (v0, v1, v2, v3, v4, v5), (f0, f1) = self._make_mesh_with_faces()
        derived = DerivedGeometry(mesh)

        from core import Selection

        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.set({v0})

        normal = selection_normal(derived, mesh, sel, SelectionMode.VERTEX)
        # v0 is on face f0 only, so its normal should be f0's normal
        self.assertTrue(_close(normal, (0.0, 0.0, 1.0)))

    def test_empty_selection_returns_zero(self):
        """Empty selection returns zero vector."""
        mesh, _, _ = self._make_mesh_with_faces()
        derived = DerivedGeometry(mesh)

        from core import Selection

        sel = Selection()
        sel.mode = SelectionMode.FACE
        sel.set(set())

        normal = selection_normal(derived, mesh, sel, SelectionMode.FACE)
        self.assertTrue(_close(normal, (0.0, 0.0, 0.0)))


class RotateToolNormalAxisTests(unittest.TestCase):
    """Tests for axis="normal" in RotateTool."""

    def test_rotate_around_face_normal(self):
        """Rotate around the normal of a single selected face."""
        from core import HistoryStack, OperationContext, RotateOperation, Scene, Selection
        from mirai.interaction.tools.rotate import _resolve_axis

        mesh = Mesh()
        # XY plane face, normal = +Z
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        v2 = mesh.add_vertex((1.0, 1.0, 0.0))
        v3 = mesh.add_vertex((0.0, 1.0, 0.0))
        f0 = mesh.add_face([v0, v1, v2, v3])

        derived = DerivedGeometry(mesh)

        sel = Selection()
        sel.mode = SelectionMode.FACE
        sel.set({f0})

        # Resolve axis="normal" with the mesh and selection
        axis = _resolve_axis(
            "normal",
            derived_geometry=derived,
            mesh=mesh,
            selection=sel,
        )

        # Should get +Z axis
        self.assertTrue(_close(axis, (0.0, 0.0, 1.0)))

    def test_rotate_zero_normal_raises(self):
        """Degenerate normal (zero vector) raises ValueError."""
        from core import Selection
        from mirai.interaction.tools.rotate import _resolve_axis

        mesh = Mesh()
        # Create a degenerate face (collinear vertices) → zero normal
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        v2 = mesh.add_vertex((2.0, 0.0, 0.0))
        f0 = mesh.add_face([v0, v1, v2])

        derived = DerivedGeometry(mesh)

        sel = Selection()
        sel.mode = SelectionMode.FACE
        sel.set({f0})

        # Should raise because the normal is zero
        with self.assertRaises(ValueError):
            _resolve_axis(
                "normal",
                derived_geometry=derived,
                mesh=mesh,
                selection=sel,
            )


if __name__ == "__main__":
    unittest.main()
