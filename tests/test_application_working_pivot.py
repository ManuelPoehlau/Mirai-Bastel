"""Working Pivot in the production app (2026-10-28, Manu U-1..U-4, AD-012 addendum "Working Pivot"): hold P + LMB
click places it, a tap switches it off / on, Esc during placement restores it; E / R then turn and scale around it
(also under Soft and symmetry), Move is unaffected, the gizmo sits on it; placing is no undo step."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core.operations.transform import mirror_point, rotate_around_axis
from hud import hud_rows, hud_state, key_hints
from mirai.interaction import commands as cmd
from mirai.symmetry_axis import current_axis
from tests.test_application_gizmo import (  # noqa: F401  (app is a fixture)
    E, ESC, K1, K4, R, W, HEIGHT, WIDTH, _key, _mouse, _screen, _vertex, app,
)

P = _key("p")
O = _key("o")
SHIFT_S = _key("s", "shift")
CTRL_Z = _key("z", "ctrl")
QUAD = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def _place(app, point, *, modifiers=()) -> None:
    """Hold P, click on the screen position of `point`, release P."""
    x, y = _screen(app, point)
    app.pointer_motion(x, y)
    assert app.key_press(P)
    app.pointer_press(_mouse("LEFT", *modifiers), x, y)
    app.pointer_release("LEFT", x, y)
    assert app.key_release(P)


def _select(app, coords):
    mesh = app.scene.mesh
    ids = [_vertex(mesh, x, y) for x, y in coords]
    app.key_press(K1)
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    return ids


def _positions(app, ids):
    return [app.scene.mesh.vertex_position(i) for i in ids]


def _circle(centre, radius, degrees):
    a = math.radians(degrees)
    return (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a))


def _hold_and_circle(app, key, centre_point, a0, a1, steps=18, radius=110.0) -> None:
    centre = _screen(app, centre_point)
    px, py = _circle(centre, radius, a0)
    app.pointer_motion(px, py)
    assert app.key_press(key)
    for i in range(1, steps + 1):
        x, y = _circle(centre, radius, a0 + (a1 - a0) * i / steps)
        app.pointer_motion(x, y, x - px, y - py)
        px, py = x, y


def _forward(app):
    return app.camera.basis()[0]


def _approx(point, tol=1e-6):
    return pytest.approx(point, abs=tol)


@pytest.fixture
def begins(app, monkeypatch) -> list[dict]:
    calls: list[dict] = []
    original = app.tool_manager.begin_current_interaction

    def spy(context=None):
        calls.append(context)
        original(context)

    monkeypatch.setattr(app.tool_manager, "begin_current_interaction", spy)
    return calls


# -- placement (U-1, U-2, U-3) ------------------------------------------------------------------------


def test_the_key_is_a_provisional_hold_default(app):
    assert app.bindings.command_for(P) == cmd.PIVOT_PLACE
    assert cmd.PIVOT_PLACE in cmd.HOLD_COMMANDS


def test_hold_p_and_click_places_the_pivot_without_touching_selection_or_history(app):
    ids = _select(app, QUAD)
    before = set(app.selection.vertices)
    _place(app, (-1.0, -1.0, 0.0))
    pivot = app.working_pivot
    assert pivot is not None and pivot.enabled and pivot.object_id == app.scene.edit_object_id
    assert pivot.position == _approx((-1.0, -1.0, 0.0))
    assert app.active_pivot == pivot.position
    assert set(app.selection.vertices) == before and len(ids) == 4
    assert len(app.history) == 0  # U-3: placing is no undo step


def test_a_second_click_while_held_corrects_and_a_drag_follows(app):
    x0, y0 = _screen(app, (-1.0, -1.0, 0.0))
    x1, y1 = _screen(app, (1.5, 0.5, 0.0))
    app.pointer_motion(x0, y0)
    assert app.key_press(P)
    app.pointer_press(_mouse("LEFT"), x0, y0)
    app.pointer_drag(x1 - x0, y1 - y0, x1, y1)
    app.pointer_release("LEFT", x1, y1)
    assert app.working_pivot.position == _approx((1.5, 0.5, 0.0))
    app.pointer_press(_mouse("LEFT"), x0, y0)
    app.pointer_release("LEFT", x0, y0)
    app.key_release(P)
    assert app.working_pivot.position == _approx((-1.0, -1.0, 0.0))


def test_shift_click_snaps_to_the_vertex(app):
    x, y = _screen(app, (1.0, 1.0, 0.0))
    app.pointer_motion(x + 3.0, y - 2.0)
    app.key_press(P)
    app.pointer_press(_mouse("LEFT", "shift"), x + 3.0, y - 2.0)
    app.pointer_release("LEFT", x + 3.0, y - 2.0)
    app.key_release(P)
    assert app.working_pivot.position == (1.0, 1.0, 0.0)


def test_a_tap_switches_the_pivot_off_and_on_and_keeps_its_place(app):
    assert app.key_press(P) and app.key_release(P)
    assert app.working_pivot is None and "none" in app.status_message
    _place(app, (-1.0, -1.0, 0.0))
    placed = app.working_pivot.position
    app.key_press(P)
    app.key_release(P)
    assert not app.working_pivot.enabled and app.active_pivot is None
    app.key_press(P)
    app.key_release(P)
    assert app.working_pivot.enabled and app.active_pivot == placed


def test_esc_while_placing_restores_the_pivot_from_before(app):
    _place(app, (-1.0, -1.0, 0.0))
    x, y = _screen(app, (1.0, 1.0, 0.0))
    app.pointer_motion(x, y)
    app.key_press(P)
    app.pointer_press(_mouse("LEFT"), x, y)
    app.pointer_release("LEFT", x, y)
    assert app.key_press(ESC)
    assert app.working_pivot.position == _approx((-1.0, -1.0, 0.0))
    assert not app.pivot_placing
    assert app.key_release(P) is False  # placement already ended


def test_a_click_while_placing_never_selects(app):
    _select(app, QUAD)
    x, y = _screen(app, (-1.5, -1.5, 0.0))
    app.pointer_motion(x, y)
    app.key_press(P)
    app.pointer_press(_mouse("LEFT"), x, y)
    app.pointer_release("LEFT", x, y)
    app.key_release(P)
    assert len(app.selection.vertices) == 4


def test_alt_lmb_still_orbits_while_placing(app):
    x, y = _screen(app, (0.0, 0.0, 0.0))
    yaw = app.camera.yaw
    app.pointer_motion(x, y)
    app.key_press(P)
    app.pointer_press(_mouse("LEFT", "alt"), x, y)
    app.pointer_drag(40.0, 0.0, x + 40.0, y)
    app.pointer_release("LEFT", x + 40.0, y)
    app.key_release(P)
    assert app.camera.yaw != yaw
    assert app.working_pivot is None


def test_placing_is_refused_in_object_mode_and_under_a_held_transform(app):
    app.key_press(K4)
    assert app.key_press(P) is False and not app.pivot_placing
    _select(app, QUAD)
    x, y = _screen(app, (0.5, 0.5, 0.0))
    app.pointer_motion(x, y)
    assert app.key_press(E)
    assert app.key_press(P) is False and not app.pivot_placing
    app.key_release(E)


def test_the_preview_follows_the_cursor_while_placing(app):
    x, y = _screen(app, (1.0, -1.0, 0.0))
    app.key_press(P)
    app.pointer_motion(x, y)
    items = app.pivot_marker_items()
    assert items and items[0].color[3] < 1.0  # dimmed preview
    app.key_release(P)
    assert app.pivot_marker_items() == []  # nothing placed: no marker


# -- transforms around the pivot (U-1, U-4) --------------------------------------------------------------


def test_e_turns_around_the_working_pivot(app):
    pivot = (-1.0, -1.0, 0.0)
    _place(app, pivot)
    placed = app.working_pivot.position
    ids = _select(app, QUAD)
    _hold_and_circle(app, E, placed, 0.0, 90.0)
    assert app.tool_manager.active_tool.operation.pivot == placed
    app.key_release(E)
    want = [rotate_around_axis((x, y, 0.0), placed, _forward(app), -math.pi / 2) for x, y in QUAD]
    for got, expected in zip(_positions(app, ids), want):
        assert got == _approx(expected)
    assert len(app.history) == 1


def test_the_arm_line_names_the_working_pivot_for_rotate_and_scale_only(app):
    _place(app, (-1.0, -1.0, 0.0))
    _select(app, QUAD)
    app.pointer_motion(400.0, 300.0)
    app.key_press(E)
    assert "around the Working Pivot" in app.status_message
    app.key_release(E)
    app.key_press(W)
    assert "Working Pivot" not in app.status_message
    app.key_release(W)


def test_r_scales_around_the_working_pivot(app):
    _place(app, (-1.0, -1.0, 0.0))
    placed = app.working_pivot.position
    ids = _select(app, QUAD)
    app.pointer_motion(500.0, 300.0)
    app.key_press(R)
    for _ in range(6):
        app.pointer_motion(500.0, 300.0, 8.0, 0.0)
    app.key_release(R)
    start = [(x, y, 0.0) for x, y in QUAD]
    factors = set()
    for got, s in zip(_positions(app, ids), start):
        d0 = [s[i] - placed[i] for i in range(3)]
        d1 = [got[i] - placed[i] for i in range(3)]
        k = d1[0] / d0[0] if abs(d0[0]) > 1e-9 else d1[1] / d0[1]
        assert d1 == _approx([k * c for c in d0], 1e-9)
        factors.add(round(k, 9))
    assert len(factors) == 1 and factors != {1.0}


def test_move_is_unaffected(app, begins):
    _place(app, (-1.0, -1.0, 0.0))
    _select(app, QUAD)
    app.pointer_motion(400.0, 300.0)
    app.key_press(W)
    app.pointer_motion(410.0, 300.0, 10.0, 0.0)
    app.key_release(W)
    assert "pivot" not in begins[-1]  # Move is pivot-independent: today's payload


def test_pivot_off_is_todays_payload(app, begins):
    _place(app, (-1.0, -1.0, 0.0))
    app.key_press(P)
    app.key_release(P)  # off
    ids = _select(app, QUAD)
    _hold_and_circle(app, E, (0.5, 0.5, 0.0), 0.0, 90.0)
    assert "pivot" not in begins[-1]
    app.key_release(E)
    want = [rotate_around_axis((x, y, 0.0), (0.5, 0.5, 0.0), _forward(app), -math.pi / 2) for x, y in QUAD]
    for got, expected in zip(_positions(app, ids), want):
        assert got == _approx(expected)


def test_undo_restores_geometry_and_keeps_the_pivot(app):
    _place(app, (-1.0, -1.0, 0.0))
    placed = app.working_pivot
    ids = _select(app, QUAD)
    before = _positions(app, ids)
    _hold_and_circle(app, E, placed.position, 0.0, 60.0)
    app.key_release(E)
    assert app.key_press(CTRL_Z)
    assert _positions(app, ids) == before
    assert app.working_pivot == placed


def test_esc_during_the_gesture_cancels_and_keeps_the_pivot(app):
    _place(app, (-1.0, -1.0, 0.0))
    placed = app.working_pivot
    ids = _select(app, QUAD)
    before = _positions(app, ids)
    _hold_and_circle(app, E, placed.position, 0.0, 60.0)
    assert app.key_press(ESC)
    app.key_release(E)
    assert _positions(app, ids) == before and len(app.history) == 0
    assert app.working_pivot == placed


def test_soft_turns_around_the_pivot_with_unchanged_influence(app, begins):
    ids = _select(app, QUAD)
    assert app.key_press(O)
    _hold_and_circle(app, E, (0.5, 0.5, 0.0), 0.0, 30.0)
    influenced_default = set(app.tool_manager.active_tool.vertex_ids)
    assert app.key_press(ESC)
    app.key_release(E)
    _place(app, (-1.0, -1.0, 0.0))
    placed = app.working_pivot.position
    app.selection.set(set(ids))
    _hold_and_circle(app, E, placed, 0.0, 30.0)
    tool = app.tool_manager.active_tool
    assert tool.operation.pivot == placed
    assert set(tool.vertex_ids) == influenced_default  # the falloff comes from the seeds, not the pivot
    assert begins[-1]["pivot"] == placed and "soft" in begins[-1]
    app.key_release(E)


def test_the_gizmo_and_the_marker_sit_on_the_pivot(app):
    _place(app, (-1.0, -1.0, 0.0))
    _select(app, QUAD)
    assert app._gizmo_pivot() == _approx((-1.0, -1.0, 0.0))
    items = app.pivot_marker_items()
    assert len(items) == 2 and items[0].color[3] == 1.0
    _hold_and_circle(app, E, app.active_pivot, 0.0, 20.0)
    assert app.gizmo_items() == []  # the gizmo hides during a gesture ...
    assert app.pivot_marker_items()  # ... the marker stays: what you turn around
    app.key_release(E)


def test_the_pivot_does_not_apply_in_object_mode(app, begins):
    _place(app, (-1.0, -1.0, 0.0))
    app.key_press(K4)
    assert app.active_pivot is None
    assert app.pivot_marker_items() == []


def test_load_scene_forgets_the_pivot(app):
    _place(app, (-1.0, -1.0, 0.0))
    app.load_scene("cube")
    assert app.working_pivot is None


def test_hud_row(app):
    def row():
        rows = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}
        return rows["Pivot"]

    assert row().value == "off" and row().keys == "P" and not row().on
    app.key_press(P)
    assert row().value == "placing" and row().on
    app.key_release(P)
    _place(app, (-1.0, -1.0, 0.0))
    assert row().value == "on" and row().on
    app.key_press(P)
    app.key_release(P)
    assert row().value == "off · placed"


# -- symmetry ----------------------------------------------------------------------------------------


def test_symmetry_mirrors_the_pivot_for_the_partner(app):
    assert app.key_press(SHIFT_S) and current_axis(app.scene.mesh) == "X"
    mesh = app.scene.mesh
    _place(app, (1.5, 1.5, 0.0))
    placed = app.working_pivot.position
    own = _vertex(mesh, 2.0, 2.0)
    partner = _vertex(mesh, -2.0, 2.0)
    app.key_press(K1)
    app.selection.set({own})
    app.viewport.on_selection_changed()
    _hold_and_circle(app, E, placed, 0.0, 90.0)
    app.key_release(E)
    moved = mesh.vertex_position(own)
    assert moved == _approx(rotate_around_axis((2.0, 2.0, 0.0), placed, _forward(app), -math.pi / 2))
    assert mesh.vertex_position(partner) == _approx(mirror_point(moved, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))


def test_seam_vertices_with_an_off_plane_pivot_are_refused_with_a_hint(app):
    assert app.key_press(SHIFT_S)
    mesh = app.scene.mesh
    _place(app, (1.5, 1.5, 0.0))
    ids = [_vertex(mesh, 0.0, 1.0), _vertex(mesh, 1.0, 1.0)]
    app.key_press(K1)
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    before = _positions(app, ids)
    history = len(app.history)
    _hold_and_circle(app, E, app.active_pivot, 0.0, 30.0)
    assert "refused" in app.status_message and "Working Pivot" in app.status_message
    app.key_release(E)
    assert _positions(app, ids) == before and len(app.history) == history


def test_a_click_is_not_bound_on_its_own(app):
    """Placement lives on the held key only: a plain LMB click still selects."""
    x, y = _screen(app, (1.0, 1.0, 0.0))
    app.key_press(K1)
    app.pointer_motion(x, y)
    app.pointer_press(_mouse("LEFT"), x, y)
    app.pointer_release("LEFT", x, y)
    assert app.working_pivot is None and len(app.selection.vertices) == 1
