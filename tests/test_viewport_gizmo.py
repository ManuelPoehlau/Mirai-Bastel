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


# -- 2026-10-28 (Manu A4/A5, E3/E5): sizes, the filled centre, ring segments, hover on the active handle ---------


def test_every_session_size_is_smaller_than_the_old_one_and_scales_the_gizmo(camera):
    assert set(gizmo.GIZMO_SIZES) == {"S", "M", "L"} and gizmo.GIZMO_SIZE_DEFAULT in gizmo.GIZMO_SIZES
    assert all(scale < 0.18 for scale in gizmo.GIZMO_SIZES.values())  # 0.18 = the size until 2026-10-28
    small, large = gizmo.GIZMO_SIZES["S"], gizmo.GIZMO_SIZES["L"]
    assert gizmo.gizmo_size(camera, PIVOT, large) == pytest.approx(gizmo.gizmo_size(camera, PIVOT, small) * large / small)
    x_line = gizmo.draw_items(camera, PIVOT, "move", None, None, scale=small)[0]
    assert x_line.positions[3] == pytest.approx(gizmo.gizmo_size(camera, PIVOT, small))


def test_the_centre_circle_is_picked_over_its_whole_disc_not_only_at_the_pivot(camera):
    radius = gizmo.center_pick_radius_px(camera, PIVOT, WIDTH, HEIGHT)
    cx, cy = _screen(camera, PIVOT)
    for tool in gizmo.TOOLS:
        # On the x axis line (and on edge-on rings) just inside the circle's outline: the centre wins.
        assert gizmo.pick_handle(
            camera, PIVOT, gizmo.WORLD_AXES, gizmo.WORLD_PLANES, tool, cx + radius - 1.0, cy, WIDTH, HEIGHT
        ) == "center"
    outside = gizmo.pick_handle(
        camera, PIVOT, gizmo.WORLD_AXES, gizmo.WORLD_PLANES, "move", cx + radius + 3.0, cy, WIDTH, HEIGHT
    )
    assert outside == "x"


def test_the_centre_disc_covers_the_drawn_circle(camera):
    ring = gizmo.gizmo_size(camera, PIVOT) * gizmo.CENTER_RING_RATIO
    _, right, _ = camera.basis()
    edge = _screen(camera, tuple(right[i] * ring for i in range(3)))
    centre = _screen(camera, PIVOT)
    drawn = ((edge[0] - centre[0]) ** 2 + (edge[1] - centre[1]) ** 2) ** 0.5
    assert gizmo.center_pick_radius_px(camera, PIVOT, WIDTH, HEIGHT) >= drawn + gizmo.CENTER_PICK_MARGIN_PX - 1e-9


def test_a_large_ring_is_pickable_between_its_samples(camera):
    """Picking along the segments: a point on the chord between two of the 32 samples of a big ring is picked
    (sample points alone left gaps wider than the pick radius there)."""
    import math

    scale = 0.6
    size = gizmo.gizmo_size(camera, PIVOT, scale)
    half_step = math.pi / 32
    _, right, up = camera.basis()
    # The screen ring (Rotate) lies in the view plane: its chord midpoint between samples 0 and 1.
    r = size * gizmo.SCREEN_RING_RATIO * math.cos(half_step)
    c, s = math.cos(half_step), math.sin(half_step)
    point = tuple(r * (c * right[i] + s * up[i]) for i in range(3))
    sample = tuple(size * gizmo.SCREEN_RING_RATIO * right[i] for i in range(3))
    px, py = _screen(camera, point)
    sx, sy = _screen(camera, sample)
    assert math.hypot(px - sx, py - sy) > gizmo.PICK_RADIUS_PX  # the old sample pick would miss it
    picked = gizmo.pick_handle(
        camera, PIVOT, gizmo.WORLD_AXES, gizmo.WORLD_PLANES, "rotate", px, py, WIDTH, HEIGHT, scale=scale
    )
    assert picked == "screen"


def test_hovering_the_active_handle_has_its_own_visible_state(camera):
    """E5: until 2026-10-28 the active state hid the hover; now hover on the active handle is thicker than active
    and takes the hover colour."""
    plain_active = [i for i in gizmo.draw_items(camera, PIVOT, "move", "x", None) if i.width == gizmo.LINE_WIDTH_ACTIVE]
    items = gizmo.draw_items(camera, PIVOT, "move", "x", "x")
    hovered_active = [i for i in items if i.width == gizmo.LINE_WIDTH_ACTIVE_HOVER]
    assert len(plain_active) == len(hovered_active) == 2  # line + arrowhead
    assert gizmo.LINE_WIDTH_ACTIVE_HOVER > gizmo.LINE_WIDTH_ACTIVE
    assert all(i.color == gizmo.hover_color(gizmo.COLOR_X) != gizmo.COLOR_X for i in hovered_active)
    assert all(i.color == gizmo.COLOR_X for i in plain_active)


@pytest.mark.parametrize("tool", gizmo.TOOLS)
def test_every_handle_shows_its_hover(camera, tool):
    handles = {"center", "x", "y", "z"} | ({"screen"} if tool == "rotate" else {"xy", "xz", "yz"})
    base = gizmo.draw_items(camera, PIVOT, tool, None, None)
    for handle in handles:
        hovered = gizmo.draw_items(camera, PIVOT, tool, None, handle)
        changed = [h for b, h in zip(base, hovered) if (b.color, b.width) != (h.color, h.width)]
        assert changed, handle
        assert all(h.color != b.color for b, h in zip(base, hovered) if (b.color, b.width) != (h.color, h.width))
    assert gizmo.hover_color(gizmo.COLOR_CENTER) == gizmo.COLOR_CENTER_HOVER  # white cannot get lighter
