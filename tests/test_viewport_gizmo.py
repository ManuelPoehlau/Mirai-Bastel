"""Transform gizmo maths (`mirai.viewport.gizmo`, promoted from the Playground 2026-10-21): handle picking along the
projected segments / rings, the Scale centre, and the draw primitives per tool and state. Pure, no GL."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from mirai.viewport import gizmo
from mirai.viewport.camera import OrbitCamera

WIDTH, HEIGHT = 800, 600
PIVOT = (0.0, 0.0, 0.0)


@pytest.fixture
def camera() -> OrbitCamera:
    cam = OrbitCamera()
    cam.yaw = 0.0
    cam.pitch = 0.0
    cam.distance = 10.0
    cam.camera_revision += 1
    return cam


def _screen(camera, point):
    return camera.project_to_screen(point, WIDTH, HEIGHT)


def _pick(camera, point, tool="move"):
    x, y = _screen(camera, point)
    return gizmo.pick_handle(camera, PIVOT, gizmo.WORLD_AXES, gizmo.WORLD_PLANES, tool, x, y, WIDTH, HEIGHT)


def test_a_click_anywhere_along_an_axis_line_picks_that_axis(camera):
    size = gizmo.gizmo_size(camera, PIVOT)
    for fraction in (0.35, 0.6, 0.95):
        assert _pick(camera, (size * fraction, 0.0, 0.0)) == "x"
        assert _pick(camera, (0.0, size * fraction, 0.0)) == "y"


def test_plane_brackets_are_picked_at_their_corner_and_nothing_far_away(camera):
    size = gizmo.gizmo_size(camera, PIVOT)
    s = size * 0.35
    assert _pick(camera, (s, s, 0.0)) == "xy"
    assert _pick(camera, (size * 2.0, size * 2.0, 0.0)) is None


def test_rotate_picks_the_ring_not_the_line_and_has_no_plane_brackets(camera):
    size = gizmo.gizmo_size(camera, PIVOT)
    # The z ring is a circle in the XY plane: a point on it is picked in Rotate, while in Move the same point is
    # nowhere near a handle line (the z axis points at the eye).
    assert _pick(camera, (size, 0.0, 0.0), "rotate") in {"y", "z"}  # ring crossing (y ring passes (size, 0, 0) too)
    s = size * 0.35
    assert _pick(camera, (s, s, 0.0), "rotate") is None


def test_the_centre_circle_exists_in_every_tool_and_wins_at_the_pivot(camera):
    for tool in gizmo.TOOLS:
        assert _pick(camera, PIVOT, tool) == "center"


def test_the_outer_screen_ring_is_pickable_for_rotate_only(camera):
    _, right, _ = camera.basis()
    r = gizmo.gizmo_size(camera, PIVOT) * gizmo.SCREEN_RING_RATIO
    on_ring = (right[0] * r, right[1] * r, right[2] * r)
    assert _pick(camera, on_ring, "rotate") == "screen"
    assert _pick(camera, on_ring, "move") != "screen"


def test_draw_items_follow_the_tool(camera):
    def kinds(tool):
        items = gizmo.draw_items(camera, PIVOT, tool, None, None)
        return [(i.primitive, len(i.positions) // 3) for i in items]

    move = kinds("move")
    assert len(move) == 3 + 3 + 3 + 1  # 3 axis lines + 3 arrow caps + 3 plane brackets + centre circle
    scale = kinds("scale")
    assert len(scale) == 3 + 3 + 3 + 1  # lines + box caps + brackets + centre circle
    rotate = kinds("rotate")
    assert all(primitive == "loop" for primitive, _ in rotate)
    assert len(rotate) == 3 + 1 + 1  # three rings + the camera-facing ring + the centre circle


def test_rotate_keeps_the_screen_ring_and_centre_when_an_axis_is_chosen(camera):
    items = gizmo.draw_items(camera, PIVOT, "rotate", "x", None)
    assert len(items) == 5


def test_active_and_hover_states_change_width_and_hover_brightens(camera):
    base = {i.width for i in gizmo.draw_items(camera, PIVOT, "move", None, None)}
    assert base == {gizmo.LINE_WIDTH_DEFAULT}
    items = gizmo.draw_items(camera, PIVOT, "move", "x", "y")
    widths = {i.width for i in items}
    assert gizmo.LINE_WIDTH_ACTIVE in widths and gizmo.LINE_WIDTH_HOVER in widths
    hovered_y = [i for i in items if i.width == gizmo.LINE_WIDTH_HOVER]
    assert all(i.color[1] > gizmo.COLOR_Y[1] * 0.99 for i in hovered_y)  # brighter (clamped at 1.0)
    # The active handle is not additionally brightened.
    active = [i for i in items if i.width == gizmo.LINE_WIDTH_ACTIVE]
    assert all(i.color == gizmo.COLOR_X for i in active)


def test_the_size_is_a_constant_fraction_of_the_eye_distance(camera):
    near = gizmo.gizmo_size(camera, PIVOT)
    camera.distance = 20.0
    far = gizmo.gizmo_size(camera, PIVOT)
    assert far == pytest.approx(near * 2.0, rel=1e-6)
