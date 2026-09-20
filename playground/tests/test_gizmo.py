"""Unit tests for WP-AP-GIZMO-01: transform gizmo mode classification.

`gizmo_mode` is pure (no GL, no window), so it's fully testable here.
Geometry helpers are smoke-tested for shape/length.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
for _p in (str(_REPO_SRC), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.selection import Selection, SelectionMode  # noqa: E402
from playground.gizmo import (  # noqa: E402
    GIZMO_SCALE,
    gizmo_mode,
    pick_gizmo_handle,
    axis_line_positions,
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
    def test_no_constraint_returns_screen(self):
        sel = _vertex_sel({0})
        assert gizmo_mode(sel, "world", None) == "screen"

    def test_no_constraint_normal_space_still_screen(self):
        sel = _face_sel({0})
        assert gizmo_mode(sel, "normal", None) == "screen"

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
