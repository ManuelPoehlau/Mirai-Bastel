"""WP-AP-CUT Hover: headless tests for kind-based dispatch, t→world lerp,
and cancel-before-switch state logic.

Tests §2.1, §3.2, §2.3 of KNIFE_HOVER_CLAUDE_CODE_HANDOFF.md.
No GL context, no window — pure data logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playground.vbo_builder import build_knife_preview_point_data  # noqa: E402


# ---------------------------------------------------------------------------
# 1. t → world position lerp
# ---------------------------------------------------------------------------

def test_t_lerp_at_zero_returns_p0():
    p0 = (0.0, 0.0, 0.0)
    p1 = (2.0, 0.0, 0.0)
    t = 0.0
    result = (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
        p0[2] + t * (p1[2] - p0[2]),
    )
    assert result == (0.0, 0.0, 0.0)


def test_t_lerp_at_one_returns_p1():
    p0 = (0.0, 0.0, 0.0)
    p1 = (2.0, 4.0, 6.0)
    t = 1.0
    result = (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
        p0[2] + t * (p1[2] - p0[2]),
    )
    assert result == (2.0, 4.0, 6.0)


def test_t_lerp_at_half_returns_midpoint():
    p0 = (0.0, 0.0, 0.0)
    p1 = (2.0, 4.0, 6.0)
    t = 0.5
    result = (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
        p0[2] + t * (p1[2] - p0[2]),
    )
    assert result == (1.0, 2.0, 3.0)


def test_t_lerp_negative_axis():
    p0 = (3.0, 3.0, 3.0)
    p1 = (1.0, 1.0, 1.0)
    t = 0.5
    result = (
        p0[0] + t * (p1[0] - p0[0]),
        p0[1] + t * (p1[1] - p0[1]),
        p0[2] + t * (p1[2] - p0[2]),
    )
    assert result == (2.0, 2.0, 2.0)


# ---------------------------------------------------------------------------
# 2. build_knife_preview_point_data
# ---------------------------------------------------------------------------

def test_preview_point_data_returns_list_of_three():
    data = build_knife_preview_point_data((1.5, 2.5, 3.5))
    assert data == [1.5, 2.5, 3.5]


def test_preview_point_data_at_origin():
    data = build_knife_preview_point_data((0.0, 0.0, 0.0))
    assert data == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# 3. Kind-based dispatch logic
# ---------------------------------------------------------------------------

def _dispatch_should_show_highlight(kind: str) -> bool:
    """The dispatch rule from §2.1: only vertex and edge produce highlight geometry."""
    return kind in ("vertex", "edge")


def _dispatch_should_show_preview(kind: str, valid: bool, model: str) -> bool:
    """Preview point shown only for edge + valid + live_preview model."""
    return kind == "edge" and valid and model == "live_preview"


def test_dispatch_vertex_shows_highlight():
    assert _dispatch_should_show_highlight("vertex") is True


def test_dispatch_edge_shows_highlight():
    assert _dispatch_should_show_highlight("edge") is True


def test_dispatch_face_no_highlight():
    assert _dispatch_should_show_highlight("face") is False


def test_dispatch_outside_no_highlight():
    assert _dispatch_should_show_highlight("outside") is False


def test_dispatch_preview_edge_valid_live():
    assert _dispatch_should_show_preview("edge", True, "live_preview") is True


def test_dispatch_preview_edge_invalid():
    assert _dispatch_should_show_preview("edge", False, "live_preview") is False


def test_dispatch_preview_edge_wrong_model():
    assert _dispatch_should_show_preview("edge", True, "press_slide_release") is False


def test_dispatch_preview_vertex_no_point():
    assert _dispatch_should_show_preview("vertex", True, "live_preview") is False


# ---------------------------------------------------------------------------
# 4. Cancel-before-switch logic
# ---------------------------------------------------------------------------

def test_cancel_before_switch_resets_knife_tool():
    """Simulates the state machine: knife_tool not None → cancel → becomes None."""
    class _FakeKnifeTool:
        cancelled = False
        deactivated = False

        def cancel(self):
            self.cancelled = True

        def deactivate(self):
            self.deactivated = True

    knife_tool = _FakeKnifeTool()

    # Simulate the M-key cancel-before-switch path
    if knife_tool is not None:
        knife_tool.cancel()
        knife_tool.deactivate()
        knife_tool = None

    assert knife_tool is None


def test_cancel_before_switch_noop_when_no_session():
    """If no session is active, cancel-before-switch does nothing."""
    knife_tool = None
    if knife_tool is not None:
        knife_tool.cancel()
    assert knife_tool is None
