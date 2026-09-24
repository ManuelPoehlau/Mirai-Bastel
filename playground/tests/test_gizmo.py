"""Unit tests for WP-AP-GIZMO-01/04: transform gizmo mode classification,
geometry helpers, pick/hover, and GIZMO-04 additions (rings, caps, hover,
hit-radius enlargement, scale center handle).

`gizmo_mode`, `pick_gizmo_handle`, and `hover_gizmo_handle` are pure (no GL),
fully testable here.

Also contains TestGizmoWindowDispatch: integration tests for D3 (AD-016) —
Gizmo as entry point (click sets constraint without tool armed; drag executes tool).
Uses unittest.mock.patch to inject a gizmo hit without real GL coordinates.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
for _p in (str(_REPO_SRC), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import math  # noqa: E402

from core.selection import Selection, SelectionMode  # noqa: E402
from playground.gizmo import (  # noqa: E402
    GIZMO_SCALE,
    gizmo_mode,
    pick_gizmo_handle,
    hover_gizmo_handle,
    axis_line_positions,
    axis_ring_positions,
    arrow_cap_positions,
    box_cap_positions,
    plane_indicator_positions,
    screen_ring_positions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _face_sel(face_ids: set) -> Selection:
    sel = Selection()
    sel.mode = SelectionMode.FACE
    sel.faces = set(face_ids)
    return sel


def _vertex_sel(vertex_ids: set) -> Selection:
    sel = Selection()
    sel.mode = SelectionMode.VERTEX
    sel.vertices = set(vertex_ids)
    return sel


def _edge_sel(edge_ids: set) -> Selection:
    sel = Selection()
    sel.mode = SelectionMode.EDGE
    sel.edges = set(edge_ids)
    return sel


# ---------------------------------------------------------------------------
# gizmo_mode
# ---------------------------------------------------------------------------

class TestGizmoMode:
    def test_no_constraint_world_shows_tripod(self):
        # No axis chosen yet: default is the full World tripod, not the
        # (retired-as-default) screen ring — an axis must be directly
        # clickable without first setting a constraint via keyboard.
        sel = _vertex_sel({0})
        assert gizmo_mode(sel, "world", None) == "world"

    def test_no_constraint_normal_space_shows_tangent_frame(self):
        sel = _face_sel({0})
        assert gizmo_mode(sel, "normal", None) == "normal_full"

    def test_world_constraint_x(self):
        sel = _vertex_sel({0, 1})
        assert gizmo_mode(sel, "world", "x") == "world"

    def test_world_constraint_plane_yz(self):
        sel = _edge_sel({0})
        assert gizmo_mode(sel, "world", "yz") == "world"

    def test_normal_single_face_returns_full(self):
        sel = _face_sel({3})
        assert gizmo_mode(sel, "normal", "z") == "normal_full"

    def test_normal_multi_face_returns_z_only(self):
        sel = _face_sel({0, 1})
        assert gizmo_mode(sel, "normal", "z") == "normal_z_only"

    def test_normal_vertex_mode_returns_z_only(self):
        sel = _vertex_sel({0, 1, 2})
        assert gizmo_mode(sel, "normal", "x") == "normal_z_only"

    def test_normal_edge_mode_returns_z_only(self):
        sel = _edge_sel({5})
        assert gizmo_mode(sel, "normal", "y") == "normal_z_only"

    def test_world_all_constraint_values(self):
        sel = _vertex_sel({0})
        for c in ("x", "y", "z", "xy", "xz", "yz"):
            assert gizmo_mode(sel, "world", c) == "world"


# ---------------------------------------------------------------------------
# Geometry helpers (smoke tests — check vertex count and types)
# ---------------------------------------------------------------------------

class TestGeometryHelpers:
    pivot = (1.0, 2.0, 3.0)

    def test_axis_line_positions_has_6_floats(self):
        pos = axis_line_positions(self.pivot, (1.0, 0.0, 0.0), 1.0)
        assert len(pos) == 6  # 2 vertices × 3 components

    def test_axis_line_starts_at_pivot(self):
        pos = axis_line_positions(self.pivot, (0.0, 1.0, 0.0), 2.0)
        assert pos[:3] == list(self.pivot)

    def test_axis_line_tip_offset(self):
        pos = axis_line_positions(self.pivot, (0.0, 0.0, 1.0), 5.0)
        assert abs(pos[5] - (self.pivot[2] + 5.0)) < 1e-9

    def test_plane_indicator_has_12_floats(self):
        pos = plane_indicator_positions(
            self.pivot, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 2.0
        )
        assert len(pos) == 12  # 4 vertices × 3 components

    def test_screen_ring_segment_count(self):
        pos = screen_ring_positions(
            self.pivot, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 1.0, segments=16
        )
        assert len(pos) == 16 * 3


# ---------------------------------------------------------------------------
# pick_gizmo_handle
# ---------------------------------------------------------------------------

class _MockCamera:
    """Minimal camera stub: eye at origin, project maps 3D→2D trivially."""

    def eye(self):
        return (0.0, 0.0, 10.0)

    def project_to_screen(self, pos3d, width, height):
        # Simple orthographic projection onto screen centre + scaled coords.
        # Positions close to origin map near (width/2, height/2).
        cx, cy = width / 2.0, height / 2.0
        return (cx + pos3d[0] * 50.0, cy + pos3d[1] * 50.0)


# Camera at (0,0,10), pivot at origin → dist=10, size=10*GIZMO_SCALE
_PIVOT = (0.0, 0.0, 0.0)
_CAM = _MockCamera()
_W, _H = 800, 600


def _size():
    dist = abs(_CAM.eye()[2] - _PIVOT[2])
    return max(dist * GIZMO_SCALE, 1e-6)


def _screen(pos3d):
    return _CAM.project_to_screen(pos3d, _W, _H)


class TestPickGizmoHandle:
    def _world_sel(self):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.vertices = {0}
        return sel

    def test_click_near_x_tip_returns_x(self):
        size = _size()
        tip_screen = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0], tip_screen[1], _W, _H,
        )
        assert result == "x"

    def test_click_near_y_tip_returns_y(self):
        size = _size()
        tip_screen = _screen((_PIVOT[0], _PIVOT[1] + size, _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0], tip_screen[1], _W, _H,
        )
        assert result == "y"

    def test_click_near_z_tip_returns_z(self):
        size = _size()
        # Z axis has no screen offset with this camera (depth axis) — it projects
        # onto the screen centre regardless of length. Test y=0 click at centre.
        # Use y-axis test to confirm z does NOT steal when y is closer.
        tip_screen = _screen((_PIVOT[0], _PIVOT[1] + size, _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0] + 5.0, tip_screen[1], _W, _H,
            max_pixel_distance=100.0,
        )
        # y handle is clearly the closest; result must be y or x, never z
        assert result in ("x", "y")

    def test_click_far_from_all_handles_returns_none(self):
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            0.0, 0.0, _W, _H,
            max_pixel_distance=5.0,
        )
        assert result is None

    def test_click_just_outside_threshold_returns_none(self):
        size = _size()
        tip_screen = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0] + 15.0, tip_screen[1], _W, _H,
            max_pixel_distance=14.0,
        )
        assert result is None

    def test_screen_mode_returns_none(self):
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "screen", "world",
            self._world_sel(), None, None,
            _W / 2, _H / 2, _W, _H,
        )
        assert result is None

    def test_returns_nearest_when_two_handles_close(self):
        size = _size()
        # Click exactly on x tip — x should win over y
        tip_x = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_x[0], tip_x[1], _W, _H,
        )
        assert result == "x"


# ---------------------------------------------------------------------------
# D3 (AD-016): Gizmo as entry point — window-level dispatch tests
# ---------------------------------------------------------------------------

class TestGizmoWindowDispatch:
    """Integration tests for AD-016 D3: Gizmo click/drag without a pre-armed tool.

    Uses unittest.mock.patch to inject a gizmo hit so the tests are independent
    of the camera projection and GL context.
    """

    def _make_window_face_selected(self):
        from playground.app import PlaygroundApp
        from playground.window import PlaygroundWindow
        from core.selection import SelectionMode
        app = PlaygroundApp()
        win = PlaygroundWindow(app, initial_mesh="cube")
        sel = app.scene.selection
        sel.mode = SelectionMode.FACE
        sel.add({sorted(app.scene.mesh.all_face_ids())[0]})
        return win

    def test_gizmo_click_sets_constraint_without_tool_armed(self):
        """D3 (AD-016): clicking a gizmo handle sets axis constraint even with no active tool."""
        from unittest.mock import patch
        from pyglet.window import mouse as _mouse
        win = self._make_window_face_selected()
        try:
            assert win.app.active_tool is None
            assert win._transform_key_down is None
            assert win._transform_mode_on is False
            # Simulate a gizmo handle hit (patch pick_gizmo_handle to return "x")
            with patch("playground.window.pick_gizmo_handle", return_value="x"):
                win.on_mouse_press(400, 300, _mouse.LEFT, 0)
            assert win._axis_constraint == "x", "axis constraint must be set by gizmo click"
            assert win._gizmo_drag_armed is True, "gizmo drag must be armed"
            assert win.app.active_tool is None, "no keyboard tool was armed before the click"
        finally:
            win.close()

    def test_gizmo_click_only_no_transform_on_release(self):
        """D3 (AD-016): a gizmo click without drag sets constraint and does not execute a transform."""
        from unittest.mock import patch
        from pyglet.window import mouse as _mouse
        win = self._make_window_face_selected()
        try:
            with patch("playground.window.pick_gizmo_handle", return_value="y"):
                win.on_mouse_press(400, 300, _mouse.LEFT, 0)
            assert win._axis_constraint == "y"
            # Release without drag → no transform started, state cleared
            win.on_mouse_release(400, 300, _mouse.LEFT, 0)
            assert win._gizmo_drag_armed is False
            assert win._gizmo_drag_started is False
            assert win._axis_constraint == "y", "constraint survives a click-only gizmo interaction"
        finally:
            win.close()

    def test_gizmo_drag_executes_and_commits(self):
        """D3 (AD-016): gizmo handle drag executes the current tool and commits on LMB release."""
        from unittest.mock import patch
        from pyglet.window import mouse as _mouse
        win = self._make_window_face_selected()
        try:
            with patch("playground.window.pick_gizmo_handle", return_value="x"):
                win.on_mouse_press(400, 300, _mouse.LEFT, 0)
            assert win._gizmo_drag_armed is True
            # Drag → begin_transform should be called; gizmo_drag_started set
            win.on_mouse_drag(440, 300, 40, 0, _mouse.LEFT, 0)
            assert win._gizmo_drag_started is True, "drag must start the gizmo transform"
            # Release → commit
            win.on_mouse_release(440, 300, _mouse.LEFT, 0)
            assert win._gizmo_drag_armed is False
            assert win._gizmo_drag_started is False
            assert win._gizmo_drag_tool is None
        finally:
            win.close()

    def test_gizmo_miss_falls_through_to_selection(self):
        """D3 (AD-016): a gizmo miss does not arm gizmo drag, falls through to selection."""
        from unittest.mock import patch
        from pyglet.window import mouse as _mouse
        win = self._make_window_face_selected()
        try:
            # pick_gizmo_handle returns None → miss
            with patch("playground.window.pick_gizmo_handle", return_value=None):
                win.on_mouse_press(400, 300, _mouse.LEFT, 0)
            assert win._gizmo_drag_armed is False, "gizmo must not arm on a miss"
            assert win._axis_constraint is None, "constraint must not change on a miss"
        finally:
            win.close()


# ---------------------------------------------------------------------------
# GIZMO-04: axis_ring_positions geometry tests
# ---------------------------------------------------------------------------

class TestAxisRingPositions:
    _PIVOT = (1.0, 2.0, 3.0)

    def test_segment_count(self):
        pos = axis_ring_positions(self._PIVOT, (0.0, 0.0, 1.0), 1.0, segments=16)
        assert len(pos) == 16 * 3

    def test_default_segments(self):
        pos = axis_ring_positions(self._PIVOT, (1.0, 0.0, 0.0), 1.0)
        assert len(pos) == 32 * 3

    def test_all_points_at_correct_radius(self):
        radius = 2.5
        pos = axis_ring_positions(self._PIVOT, (0.0, 1.0, 0.0), radius, segments=24)
        for i in range(0, len(pos), 3):
            dx = pos[i] - self._PIVOT[0]
            dy = pos[i+1] - self._PIVOT[1]
            dz = pos[i+2] - self._PIVOT[2]
            r = math.sqrt(dx*dx + dy*dy + dz*dz)
            assert abs(r - radius) < 1e-6, f"point {i//3} radius {r} != {radius}"

    def test_all_points_in_perpendicular_plane(self):
        axis = (0.0, 0.0, 1.0)
        pos = axis_ring_positions(self._PIVOT, axis, 1.0, segments=32)
        for i in range(0, len(pos), 3):
            dx = pos[i] - self._PIVOT[0]
            dy = pos[i+1] - self._PIVOT[1]
            dz = pos[i+2] - self._PIVOT[2]
            dot = dx * axis[0] + dy * axis[1] + dz * axis[2]
            assert abs(dot) < 1e-6, f"point {i//3} not in perpendicular plane: dot={dot}"

    def test_general_axis_perpendicular_plane(self):
        axis_raw = (1.0, 1.0, 1.0)
        length = math.sqrt(3.0)
        axis = (axis_raw[0]/length, axis_raw[1]/length, axis_raw[2]/length)
        pos = axis_ring_positions(self._PIVOT, axis, 1.5, segments=20)
        for i in range(0, len(pos), 3):
            dx = pos[i] - self._PIVOT[0]
            dy = pos[i+1] - self._PIVOT[1]
            dz = pos[i+2] - self._PIVOT[2]
            dot = dx * axis[0] + dy * axis[1] + dz * axis[2]
            assert abs(dot) < 1e-6, f"general axis: point {i//3} not perpendicular: dot={dot}"


# ---------------------------------------------------------------------------
# GIZMO-04: cap geometry smoke tests
# ---------------------------------------------------------------------------

class TestCapGeometry:
    _TIP = (2.0, 0.0, 0.0)
    _DIR = (1.0, 0.0, 0.0)

    def test_arrow_cap_has_4_lines(self):
        pos = arrow_cap_positions(self._TIP, self._DIR, 0.2)
        assert len(pos) == 4 * 6  # 4 lines × 2 vertices × 3 floats

    def test_arrow_cap_all_lines_start_at_tip(self):
        pos = arrow_cap_positions(self._TIP, self._DIR, 0.2)
        for i in range(0, len(pos), 6):
            assert abs(pos[i] - self._TIP[0]) < 1e-9
            assert abs(pos[i+1] - self._TIP[1]) < 1e-9
            assert abs(pos[i+2] - self._TIP[2]) < 1e-9

    def test_box_cap_has_4_edges(self):
        pos = box_cap_positions(self._TIP, self._DIR, 0.2)
        assert len(pos) == 4 * 6  # 4 edges × 2 vertices × 3 floats


# ---------------------------------------------------------------------------
# GIZMO-04: rotate ring hit test
# ---------------------------------------------------------------------------

class TestRotateRingHit:
    def _world_sel(self):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.vertices = {0}
        return sel

    def test_click_near_x_ring_returns_x(self):
        size = _size()
        # A point on the X-axis ring lies in the YZ-plane through the tip circle.
        # At angle=0: pivot + right, where right is one of the perp vectors.
        # axis_ring_positions for x=(1,0,0) uses perp basis: right=(0,1,0), up=(0,0,1)
        # first ring point = pivot + size * (1*0 + 0) * right + ... = pivot + (0,size,0)
        ring_pts = axis_ring_positions(_PIVOT, (1.0, 0.0, 0.0), size)
        first_pt = (ring_pts[0], ring_pts[1], ring_pts[2])
        sx, sy = _screen(first_pt)
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            sx, sy, _W, _H,
            current_tool="rotate",
        )
        assert result == "x"

    def test_click_far_from_rings_returns_none(self):
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            0.0, 0.0, _W, _H,
            max_pixel_distance=5.0,
            current_tool="rotate",
        )
        assert result is None


# ---------------------------------------------------------------------------
# GIZMO-04: scale center handle test
# ---------------------------------------------------------------------------

class _MockCameraOblique:
    """Camera from a diagonal — all three world axes project to distinct screen offsets.

    The standard _MockCamera aligns with the Z axis, causing the Z tip and the pivot
    to project to the exact same screen point (both have screen_x=cx, screen_y=cy).
    This camera mixes all three axes so pivot ≠ any axis tip in screen space.
    """

    def eye(self):
        return (-8.0, -6.0, 10.0)

    def project_to_screen(self, pos3d, width, height):
        cx, cy = width / 2.0, height / 2.0
        return (cx + pos3d[0] * 40.0 - pos3d[2] * 15.0,
                cy + pos3d[1] * 40.0 + pos3d[2] * 15.0)


_CAM_OBLIQUE = _MockCameraOblique()
_PIVOT_O = (0.0, 0.0, 0.0)


def _size_oblique():
    eye = _CAM_OBLIQUE.eye()
    dist = math.sqrt(
        (_PIVOT_O[0] - eye[0])**2 + (_PIVOT_O[1] - eye[1])**2 + (_PIVOT_O[2] - eye[2])**2
    )
    return max(dist * GIZMO_SCALE, 1e-6)


class TestScaleCenterHandle:
    def _world_sel(self):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.vertices = {0}
        return sel

    def test_click_at_pivot_returns_center_for_scale(self):
        # Use the oblique camera so pivot screen pos is distinct from any axis tip.
        sx, sy = _CAM_OBLIQUE.project_to_screen(_PIVOT_O, _W, _H)
        result = pick_gizmo_handle(
            _CAM_OBLIQUE, _PIVOT_O, "world", "world",
            self._world_sel(), None, None,
            sx, sy, _W, _H,
            max_pixel_distance=8.0,
            current_tool="scale",
        )
        assert result == "center"

    def test_move_tool_has_no_center_handle(self):
        sx, sy = _CAM_OBLIQUE.project_to_screen(_PIVOT_O, _W, _H)
        result = pick_gizmo_handle(
            _CAM_OBLIQUE, _PIVOT_O, "world", "world",
            self._world_sel(), None, None,
            sx, sy, _W, _H,
            max_pixel_distance=8.0,
            current_tool="move",
        )
        # Axis segments start at pivot so clicking there hits an axis — but NOT "center".
        assert result != "center", "move tool must not expose a center handle"


# ---------------------------------------------------------------------------
# GIZMO-04: hover_gizmo_handle
# ---------------------------------------------------------------------------

class TestHoverGizmoHandle:
    def _world_sel(self):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.vertices = {0}
        return sel

    def test_hover_returns_handle_under_cursor(self):
        size = _size()
        tip_screen = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        result = hover_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0], tip_screen[1], _W, _H,
        )
        assert result == "x"

    def test_hover_returns_none_on_miss(self):
        result = hover_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            0.0, 0.0, _W, _H,
            max_pixel_distance=5.0,
        )
        assert result is None

    def test_hover_is_pure_repeated_calls_agree(self):
        size = _size()
        tip_screen = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        sel = self._world_sel()
        r1 = hover_gizmo_handle(_CAM, _PIVOT, "world", "world", sel, None, None,
                                 tip_screen[0], tip_screen[1], _W, _H)
        r2 = hover_gizmo_handle(_CAM, _PIVOT, "world", "world", sel, None, None,
                                 tip_screen[0], tip_screen[1], _W, _H)
        assert r1 == r2


# ---------------------------------------------------------------------------
# GIZMO-04: enlarged hit radius
# ---------------------------------------------------------------------------

class TestSegmentBasedPicking:
    """Verify that axis lines and plane brackets are hittable along their full length."""

    def _world_sel(self):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.vertices = {0}
        return sel

    def test_click_midpoint_of_x_axis_returns_x(self):
        size = _size()
        # Midpoint of x-axis segment in 3D: pivot + direction * size/2
        mid = (_PIVOT[0] + size * 0.5, _PIVOT[1], _PIVOT[2])
        sx, sy = _screen(mid)
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            sx, sy, _W, _H,
        )
        assert result == "x"

    def test_click_quarter_of_y_axis_returns_y(self):
        size = _size()
        pt = (_PIVOT[0], _PIVOT[1] + size * 0.25, _PIVOT[2])
        sx, sy = _screen(pt)
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            sx, sy, _W, _H,
        )
        assert result == "y"


class TestHitRadiusEnlarged:
    def _world_sel(self):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.vertices = {0}
        return sel

    def test_default_radius_catches_click_beyond_old_threshold(self):
        # Click 15px from x-tip: outside old 14px default, inside new 16px default.
        size = _size()
        tip_screen = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0] + 15.0, tip_screen[1], _W, _H,
        )
        assert result == "x", "default radius must cover 15px offset (regression of D0-4 fix)"

    def test_old_threshold_still_misses_at_15px(self):
        # Explicit 14px threshold: 15px still misses (existing test, unchanged).
        size = _size()
        tip_screen = _screen((_PIVOT[0] + size, _PIVOT[1], _PIVOT[2]))
        result = pick_gizmo_handle(
            _CAM, _PIVOT, "world", "world",
            self._world_sel(), None, None,
            tip_screen[0] + 15.0, tip_screen[1], _W, _H,
            max_pixel_distance=14.0,
        )
        assert result is None
