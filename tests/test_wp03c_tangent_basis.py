"""Tests for WP-03C/WP-CORE-01: Normal space tangent basis for scale operations.

Verifies:
1. Tangent basis orthonormality for single-face selections
2. No shear when scaling along tangent X/Y on a non-axis-aligned face (WP-CORE-01)
3. No shear for plane-constraint scale (xy/yz/xz) on a non-axis-aligned face
4. Incremental contract for ScaleOperation with basis parameter
5. Single-face requirement enforcement (multi-face raises error)
6. Backward compatibility: space="normal" still works (single direction)
7. New API: space="normal", axis="x"/"y" works (tangent directions)
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from core import Mesh, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices


def _make_rotated_quad_app(angle_deg: float = 30.0) -> Application:
    """Application with a single quad rotated angle_deg degrees around Z.

    Face lies in the XY plane, so normal = (0, 0, 1).
    tangent_x = (cos(a), sin(a), 0) — first edge direction.
    tangent_y = (-sin(a), cos(a), 0) — normal × tangent_x.

    This face is NOT world-axis-aligned (for angle_deg != 0/90/180/270),
    so the old diagonal-approximation shear bug is visible here.
    """
    from viewport import Viewport

    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)

    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((c, s, 0.0))
    v2 = mesh.add_vertex((c - s, s + c, 0.0))
    v3 = mesh.add_vertex((-s, c, 0.0))
    mesh.add_face([v0, v1, v2, v3])

    app = Application()
    app.scene.mesh = mesh
    app.viewport = Viewport(mesh, selection=app.scene.selection)
    app.viewport.bind_camera(app.camera)
    return app


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _length(v):
    return math.sqrt(sum(x * x for x in v))


class TangentBasisTests(unittest.TestCase):
    """Tests for tangent basis derivation from single-face selections."""

    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")
        self.derived_geometry = (
            self.app.viewport.render_mesh.derived if self.app.viewport else None
        )

    def test_tangent_basis_orthonormal_on_single_face(self):
        """Tangent basis should be orthonormal (all unit vectors, orthogonal)."""
        self.app.selection.mode = SelectionMode.FACE
        faces = list(self.app.scene.mesh.all_face_ids())[:1]
        self.app.selection.set(set(faces))

        from mirai.interaction.tools.transform import _face_tangent_basis

        normal, tangent_x, tangent_y = _face_tangent_basis(
            self.app.scene.mesh, self.app.selection, self.derived_geometry
        )

        self.assertAlmostEqual(_length(normal), 1.0, places=10)
        self.assertAlmostEqual(_length(tangent_x), 1.0, places=10)
        self.assertAlmostEqual(_length(tangent_y), 1.0, places=10)

        self.assertAlmostEqual(_dot(normal, tangent_x), 0.0, places=10)
        self.assertAlmostEqual(_dot(normal, tangent_y), 0.0, places=10)
        self.assertAlmostEqual(_dot(tangent_x, tangent_y), 0.0, places=10)

        # Right-handed: tangent_y = normal × tangent_x
        from mirai.interaction.tools.transform import _cross

        expected_tangent_y = _cross(normal, tangent_x)
        expected_length = _length(expected_tangent_y)
        self.assertGreater(expected_length, 0.99)
        expected_tangent_y_normalized = tuple(x / expected_length for x in expected_tangent_y)
        for c_actual, c_expected in zip(tangent_y, expected_tangent_y_normalized):
            self.assertAlmostEqual(c_actual, c_expected, places=10)

    def test_scale_along_tangent_x_no_shear(self):
        """Scale along tangent X must not shear in tangent Y or normal direction.

        Uses a 30°-rotated quad — a face where the old diagonal approximation
        would produce a measurable tangent_y displacement.  The bug was invisible
        on axis-aligned cube faces (hence the fixture change from setUp's cube).
        """
        app = _make_rotated_quad_app(30.0)
        derived = app.viewport.render_mesh.derived

        a = math.radians(30.0)
        normal = (0.0, 0.0, 1.0)
        tangent_x = (math.cos(a), math.sin(a), 0.0)
        tangent_y = (-math.sin(a), math.cos(a), 0.0)

        app.selection.mode = SelectionMode.FACE
        faces = list(app.scene.mesh.all_face_ids())[:1]
        app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            app.scene.mesh, app.selection, app.selection.mode
        )
        start_positions = {vid: app.scene.mesh.vertex_position(vid) for vid in vertex_ids}

        app.dispatch_command(cmd.SCALE, context={
            "scene": app.scene,
            "camera": app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "x",
            "derived_geometry": derived,
        })
        app.tool_manager.active_tool._on_update(100, 0, 800, 600)
        app.tool_manager.commit()

        end_positions = {vid: app.scene.mesh.vertex_position(vid) for vid in vertex_ids}

        # At least one vertex must have moved (scale actually happened).
        self.assertTrue(
            any(start_positions[vid] != end_positions[vid] for vid in vertex_ids),
            "Scale should have moved vertices",
        )

        # Displacement for every vertex must be purely along tangent_x —
        # zero projection on tangent_y and on the face normal.
        for vid in vertex_ids:
            p0, p1 = start_positions[vid], end_positions[vid]
            d = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
            self.assertAlmostEqual(
                _dot(d, tangent_y), 0.0, places=10,
                msg=f"Vertex {vid}: shear in tangent_y direction (old bug still present)",
            )
            self.assertAlmostEqual(_dot(d, normal), 0.0, places=10)

    def test_scale_along_tangent_y_no_shear(self):
        """Scale along tangent Y must not shear in tangent X or normal direction."""
        app = _make_rotated_quad_app(30.0)
        derived = app.viewport.render_mesh.derived

        a = math.radians(30.0)
        normal = (0.0, 0.0, 1.0)
        tangent_x = (math.cos(a), math.sin(a), 0.0)
        tangent_y = (-math.sin(a), math.cos(a), 0.0)

        app.selection.mode = SelectionMode.FACE
        faces = list(app.scene.mesh.all_face_ids())[:1]
        app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            app.scene.mesh, app.selection, app.selection.mode
        )
        start_positions = {vid: app.scene.mesh.vertex_position(vid) for vid in vertex_ids}

        app.dispatch_command(cmd.SCALE, context={
            "scene": app.scene,
            "camera": app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": "y",
            "derived_geometry": derived,
        })
        app.tool_manager.active_tool._on_update(100, 0, 800, 600)
        app.tool_manager.commit()

        end_positions = {vid: app.scene.mesh.vertex_position(vid) for vid in vertex_ids}

        self.assertTrue(
            any(start_positions[vid] != end_positions[vid] for vid in vertex_ids),
            "Scale should have moved vertices",
        )

        for vid in vertex_ids:
            p0, p1 = start_positions[vid], end_positions[vid]
            d = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
            self.assertAlmostEqual(
                _dot(d, tangent_x), 0.0, places=10,
                msg=f"Vertex {vid}: shear in tangent_x direction",
            )
            self.assertAlmostEqual(_dot(d, normal), 0.0, places=10)

    def _run_plane_scale_and_check_no_shear(self, plane_axis: str, frozen_basis_vec, test_label: str):
        """Helper: scale with space="normal", axis=plane_axis and assert no shear along frozen_basis_vec."""
        app = _make_rotated_quad_app(30.0)
        derived = app.viewport.render_mesh.derived

        app.selection.mode = SelectionMode.FACE
        faces = list(app.scene.mesh.all_face_ids())[:1]
        app.selection.set(set(faces))

        vertex_ids = resolve_selection_vertices(
            app.scene.mesh, app.selection, app.selection.mode
        )
        start_positions = {vid: app.scene.mesh.vertex_position(vid) for vid in vertex_ids}

        app.dispatch_command(cmd.SCALE, context={
            "scene": app.scene,
            "camera": app.camera,
            "vertex_ids": vertex_ids,
            "space": "normal",
            "axis": plane_axis,
            "derived_geometry": derived,
        })
        app.tool_manager.active_tool._on_update(100, 0, 800, 600)
        app.tool_manager.commit()

        end_positions = {vid: app.scene.mesh.vertex_position(vid) for vid in vertex_ids}

        self.assertTrue(
            any(start_positions[vid] != end_positions[vid] for vid in vertex_ids),
            f"Scale (axis={plane_axis!r}) should have moved vertices",
        )

        for vid in vertex_ids:
            p0, p1 = start_positions[vid], end_positions[vid]
            d = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
            self.assertAlmostEqual(
                _dot(d, frozen_basis_vec), 0.0, places=10,
                msg=f"{test_label}: vertex {vid} displaced along frozen direction",
            )

    def test_scale_plane_xy_no_shear(self):
        """Scale in tangent plane (axis='xy') must not displace along face normal."""
        normal = (0.0, 0.0, 1.0)
        self._run_plane_scale_and_check_no_shear("xy", normal, "plane xy, frozen=normal")

    def test_scale_plane_yz_no_shear(self):
        """Scale in yz plane (axis='yz') must not displace along tangent_x."""
        a = math.radians(30.0)
        tangent_x = (math.cos(a), math.sin(a), 0.0)
        self._run_plane_scale_and_check_no_shear("yz", tangent_x, "plane yz, frozen=tangent_x")

    def test_scale_plane_xz_no_shear(self):
        """Scale in xz plane (axis='xz') must not displace along tangent_y."""
        a = math.radians(30.0)
        tangent_y = (-math.sin(a), math.cos(a), 0.0)
        self._run_plane_scale_and_check_no_shear("xz", tangent_y, "plane xz, frozen=tangent_y")

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


class ScaleOperationBasisContractTests(unittest.TestCase):
    """Direct tests for ScaleOperation with basis parameter (WP-CORE-01)."""

    def _make_scale_op(self, verts: list, pivot=None):
        """Create and begin a ScaleOperation on a minimal mesh."""
        from core import HistoryStack, OperationContext, ScaleOperation, Selection, SelectionMode

        mesh = Mesh()
        ids = [mesh.add_vertex(v) for v in verts]
        if len(ids) >= 3:
            mesh.add_face(ids)

        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.set(set(ids))

        params = {}
        if pivot is not None:
            params["pivot"] = pivot

        ctx = OperationContext(target=mesh, selection=sel, history=HistoryStack(), params=params)
        op = ScaleOperation(ctx)
        op.begin()
        return op, mesh, ids

    def test_basis_incremental_two_steps_equal_one(self):
        """Two update(factor=(2,1,1), basis=B) calls compose to factor=(4,1,1) on same start."""
        # Non-axis-aligned basis: 30° rotation around Z.
        a = math.radians(30.0)
        c, s = math.cos(a), math.sin(a)
        tx = (c, s, 0.0)
        ty = (-s, c, 0.0)
        nv = (0.0, 0.0, 1.0)
        basis = (tx, ty, nv)

        # One vertex at a known position relative to pivot.
        verts = [(c, s, 0.0), (0.0, 0.0, 0.0)]  # second vertex doubles as pivot candidate
        pivot = (0.0, 0.0, 0.0)

        # Two-step path: begin fresh, apply (2,1,1) twice.
        op_two, mesh_two, ids_two = self._make_scale_op(verts, pivot=pivot)
        op_two.update(factor=(2.0, 1.0, 1.0), basis=basis)
        op_two.update(factor=(2.0, 1.0, 1.0), basis=basis)
        two_step = {vid: mesh_two.vertex_position(vid) for vid in ids_two}

        # One-step path: begin fresh, apply (4,1,1) once.
        op_one, mesh_one, ids_one = self._make_scale_op(verts, pivot=pivot)
        op_one.update(factor=(4.0, 1.0, 1.0), basis=basis)
        one_step = {vid: mesh_one.vertex_position(vid) for vid in ids_one}

        for v2, v1 in zip(ids_two, ids_one):
            p2 = two_step[v2]
            p1 = one_step[v1]
            for i in range(3):
                self.assertAlmostEqual(
                    p2[i], p1[i], places=12,
                    msg=f"Incremental contract violated for component {i}",
                )

    def test_basis_none_bit_identical_to_diagonal(self):
        """basis=None path must be bit-identical to the old diagonal formula."""
        from core import HistoryStack, OperationContext, ScaleOperation, Selection, SelectionMode

        verts = [(1.0, 2.0, 3.0), (-1.0, 0.5, 0.0)]
        mesh = Mesh()
        ids = [mesh.add_vertex(v) for v in verts]
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.set(set(ids))
        ctx = OperationContext(target=mesh, selection=sel, history=HistoryStack(), params={})
        op = ScaleOperation(ctx)
        op.begin()
        op.update(factor=(1.5, 2.0, 0.5))  # no basis — diagonal path

        # Manually compute expected positions using diagonal formula.
        from core.operations.transform import _as_triple, _add, _sub

        pivot = op.pivot
        for vid, start in zip(ids, verts):
            f = _as_triple((1.5, 2.0, 0.5))
            q = _sub(start, pivot)
            expected = _add(pivot, (f[0] * q[0], f[1] * q[1], f[2] * q[2]))
            actual = mesh.vertex_position(vid)
            for i in range(3):
                self.assertEqual(actual[i], expected[i])


if __name__ == "__main__":
    unittest.main()
