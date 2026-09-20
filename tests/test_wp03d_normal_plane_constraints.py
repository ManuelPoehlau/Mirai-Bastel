"""Tests for WP-03D: Normal-space plane constraints (axis="xy"/"yz"/"xz").

Verifies:
1. Move: displacement has zero component along the excluded axis (face normal / tangent)
2. Scale: scaling happens in-plane, excluded axis is frozen
3. Rotate: space="normal", axis="xy"/"yz"/"xz" produces same rotation axis as the
   corresponding single-axis equivalent (proving plane-to-axis reuse, not coincidence)
4. Regression: existing single-axis normal constraints still work unchanged
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices
from mirai.interaction.tools.transform import _face_tangent_basis


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _length(v):
    return sum(x ** 2 for x in v) ** 0.5


class NormalPlaneMoveTests(unittest.TestCase):
    """Move tool: plane constraints in normal space."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))
        self.vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )
        self.normal, self.tangent_x, self.tangent_y = _face_tangent_basis(
            self.app.scene.mesh, self.app.selection, self.derived_geometry
        )

    def _run_move(self, axis):
        """Begin move with given normal-space axis, drag, commit; return per-vertex deltas."""
        start = {vid: self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids}
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": axis,
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.MOVE, context=context)
        tool = self.app.tool_manager.active_tool
        # Verify plane_exclude is set, not normal projection
        self.assertIsNotNone(tool._plane_exclude)
        self.assertIsNone(tool._normal)
        tool._on_update(50, 30, 800, 600)
        self.app.tool_manager.commit()
        end = {vid: self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids}
        return {
            vid: tuple(end[vid][i] - start[vid][i] for i in range(3))
            for vid in self.vertex_ids
        }

    def test_xy_plane_zero_normal_component(self):
        """Move in normal-space xy plane: displacement must have zero component along face normal."""
        deltas = self._run_move("xy")
        for vid, delta in deltas.items():
            dot = _dot(delta, self.normal)
            self.assertAlmostEqual(dot, 0.0, places=10,
                msg=f"Vertex {vid}: displacement has component {dot} along normal (xy plane)")

    def test_yz_plane_zero_tangent_x_component(self):
        """Move in normal-space yz plane: displacement must have zero component along tangent_x."""
        deltas = self._run_move("yz")
        for vid, delta in deltas.items():
            dot = _dot(delta, self.tangent_x)
            self.assertAlmostEqual(dot, 0.0, places=10,
                msg=f"Vertex {vid}: displacement has component {dot} along tangent_x (yz plane)")

    def test_xz_plane_zero_tangent_y_component(self):
        """Move in normal-space xz plane: displacement must have zero component along tangent_y."""
        deltas = self._run_move("xz")
        for vid, delta in deltas.items():
            dot = _dot(delta, self.tangent_y)
            self.assertAlmostEqual(dot, 0.0, places=10,
                msg=f"Vertex {vid}: displacement has component {dot} along tangent_y (xz plane)")

    def test_xy_plane_tool_state(self):
        """Move with space='normal', axis='xy' sets plane_exclude, clears normal."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": "xy",
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.MOVE, context=context)
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._plane_exclude)
        self.assertIsNone(tool._normal)
        self.app.tool_manager.cancel()


class NormalPlaneScaleTests(unittest.TestCase):
    """Scale tool: plane constraints in normal space."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))
        self.vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )
        self.normal, self.tangent_x, self.tangent_y = _face_tangent_basis(
            self.app.scene.mesh, self.app.selection, self.derived_geometry
        )
        # Compute pivot (centroid of selected vertices)
        positions = [self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids]
        n = len(positions)
        self.pivot = tuple(sum(p[i] for p in positions) / n for i in range(3))

    def _run_scale(self, axis):
        """Begin scale with given normal-space axis, drag, commit; return per-vertex deltas."""
        start = {vid: self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids}
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": axis,
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.SCALE, context=context)
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._plane_exclude)
        self.assertIsNone(tool._normal)
        # 100px right: generates scale factor > 1
        tool._on_update(100, 0, 800, 600)
        self.app.tool_manager.commit()
        end = {vid: self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids}
        return start, end

    def test_xy_plane_zero_normal_displacement(self):
        """Scale in normal-space xy plane: vertex displacements have zero component along normal."""
        start, end = self._run_scale("xy")
        for vid in self.vertex_ids:
            # Displacement from start position (not pivot) projected onto normal
            delta = tuple(end[vid][i] - start[vid][i] for i in range(3))
            dot = _dot(delta, self.normal)
            self.assertAlmostEqual(dot, 0.0, places=10,
                msg=f"Vertex {vid}: scale in xy plane produced displacement along normal: {dot}")

    def test_yz_plane_zero_tangent_x_displacement(self):
        """Scale in normal-space yz plane: vertex displacements have zero component along tangent_x."""
        start, end = self._run_scale("yz")
        for vid in self.vertex_ids:
            delta = tuple(end[vid][i] - start[vid][i] for i in range(3))
            dot = _dot(delta, self.tangent_x)
            self.assertAlmostEqual(dot, 0.0, places=10,
                msg=f"Vertex {vid}: scale in yz plane produced displacement along tangent_x: {dot}")

    def test_xz_plane_zero_tangent_y_displacement(self):
        """Scale in normal-space xz plane: vertex displacements have zero component along tangent_y."""
        start, end = self._run_scale("xz")
        for vid in self.vertex_ids:
            delta = tuple(end[vid][i] - start[vid][i] for i in range(3))
            dot = _dot(delta, self.tangent_y)
            self.assertAlmostEqual(dot, 0.0, places=10,
                msg=f"Vertex {vid}: scale in xz plane produced displacement along tangent_y: {dot}")

    def test_xy_plane_tool_state(self):
        """Scale with space='normal', axis='xy' sets plane_exclude, clears normal."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": "xy",
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.SCALE, context=context)
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._plane_exclude)
        self.assertIsNone(tool._normal)
        self.app.tool_manager.cancel()


class NormalPlaneRotateTests(unittest.TestCase):
    """Rotate tool: plane axis produces same rotation axis as single-axis equivalent."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))
        self.vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def _get_rotation_axis(self, axis):
        """Begin rotate and return the resolved rotation axis."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": axis,
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.ROTATE, context=context)
        tool = self.app.tool_manager.active_tool
        result = tool._axis
        self.app.tool_manager.cancel()
        return result

    def test_xy_plane_same_axis_as_z(self):
        """space='normal', axis='xy' produces the same rotation axis as axis='z' (face normal)."""
        axis_plane = self._get_rotation_axis("xy")
        axis_single = self._get_rotation_axis("z")
        # Must be the same vector (or antiparallel — same rotation axis up to sign)
        dot = _dot(axis_plane, axis_single)
        self.assertAlmostEqual(abs(dot), 1.0, places=10,
            msg=f"'xy' axis {axis_plane} and 'z' axis {axis_single} differ: dot={dot}")

    def test_yz_plane_same_axis_as_x(self):
        """space='normal', axis='yz' produces the same rotation axis as axis='x' (tangent_x)."""
        axis_plane = self._get_rotation_axis("yz")
        axis_single = self._get_rotation_axis("x")
        dot = _dot(axis_plane, axis_single)
        self.assertAlmostEqual(abs(dot), 1.0, places=10,
            msg=f"'yz' axis {axis_plane} and 'x' axis {axis_single} differ: dot={dot}")

    def test_xz_plane_same_axis_as_y(self):
        """space='normal', axis='xz' produces the same rotation axis as axis='y' (tangent_y)."""
        axis_plane = self._get_rotation_axis("xz")
        axis_single = self._get_rotation_axis("y")
        dot = _dot(axis_plane, axis_single)
        self.assertAlmostEqual(abs(dot), 1.0, places=10,
            msg=f"'xz' axis {axis_plane} and 'y' axis {axis_single} differ: dot={dot}")

    def test_xy_plane_produces_same_positions_as_z(self):
        """Rotate with axis='xy' produces identical vertex positions as axis='z'."""
        start = {vid: self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids}

        def run_rotate(axis_name):
            # Reset to start
            for vid, pos in start.items():
                self.app.scene.mesh.set_vertex_position(vid, pos)
            context = {
                "scene": self.app.scene,
                "camera": self.app.camera,
                "vertex_ids": self.vertex_ids,
                "space": "normal",
                "axis": axis_name,
                "derived_geometry": self.derived_geometry,
            }
            self.app.dispatch_command(cmd.ROTATE, context=context)
            tool = self.app.tool_manager.active_tool
            tool._on_update(50, 0, 800, 600)
            self.app.tool_manager.commit()
            return {vid: self.app.scene.mesh.vertex_position(vid) for vid in self.vertex_ids}

        pos_xy = run_rotate("xy")
        pos_z = run_rotate("z")

        for vid in self.vertex_ids:
            for i in range(3):
                self.assertAlmostEqual(pos_xy[vid][i], pos_z[vid][i], places=10,
                    msg=f"Vertex {vid} component {i}: axis='xy' gave {pos_xy[vid][i]}, "
                        f"axis='z' gave {pos_z[vid][i]}")


class NormalPlaneRegressionTests(unittest.TestCase):
    """Regression: existing single-axis normal constraints work unchanged after WP-03D."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))
        self.vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def test_move_normal_z_still_uses_normal_projection(self):
        """space='normal', axis='z' still uses _normal (projection), not _plane_exclude."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": "z",
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.MOVE, context=context)
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._normal)
        self.assertIsNone(tool._plane_exclude)
        self.app.tool_manager.cancel()

    def test_move_normal_no_axis_still_uses_normal_projection(self):
        """space='normal' without axis still uses _normal (backward compat)."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.MOVE, context=context)
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._normal)
        self.assertIsNone(tool._plane_exclude)
        self.app.tool_manager.cancel()

    def test_scale_normal_z_still_uses_normal(self):
        """space='normal', axis='z' for Scale still uses _normal, not _plane_exclude."""
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": self.vertex_ids,
            "space": "normal",
            "axis": "z",
            "derived_geometry": self.derived_geometry,
        }
        self.app.dispatch_command(cmd.SCALE, context=context)
        tool = self.app.tool_manager.active_tool
        self.assertIsNotNone(tool._normal)
        self.assertIsNone(tool._plane_exclude)
        self.app.tool_manager.cancel()

    def test_multi_face_plane_raises_error(self):
        """Multi-face selection with space='normal', axis='xy' raises ValueError."""
        self.app.selection.mode = SelectionMode.FACE
        all_faces = list(self.app.scene.mesh.all_face_ids())
        if len(all_faces) < 2:
            self.skipTest("Need at least 2 faces for this test")
        self.app.selection.set(set(all_faces[:2]))
        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, self.app.selection.mode
        )
        context = {
            "scene": self.app.scene,
            "camera": self.app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "xy",
            "derived_geometry": self.derived_geometry,
        }
        with self.assertRaises(ValueError):
            self.app.dispatch_command(cmd.MOVE, context=context)


if __name__ == "__main__":
    unittest.main()
