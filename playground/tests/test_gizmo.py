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
    gizmo_mode,
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
