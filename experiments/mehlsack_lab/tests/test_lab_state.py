"""§7.7 State machine (pyglet-free): creation keys incl. clamps and the horizontal-scroll
fallback, Enter, Tab, X/Y/Z, presets, B, Esc during a drag vs idle, plus the edit-phase wheel
and keys. Slice 2a: Alt+Shift+wheel = depth (incl. the fallback), `P` = surface preview,
rims go into the session at Enter, a handle-mode-only curve change is display only."""

from __future__ import annotations

import math

import pytest

from mehlsack_lab import lab_bindings as lb
from mehlsack_lab import lab_state as ls
from mehlsack_lab.box import SEGMENTS_MAX, SIZE_MAX, SIZE_MIN, BoxParams
from mehlsack_lab.signed_curve import PRESET_HAT, PRESET_SMOOTH
from mehlsack_lab.targets import MODE_LOOP, MODE_RING
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool
from mirai.soft_selection.settings import DEFAULT_RADIUS_STEP, RADIUS_STEPS_PERCENT
from mirai.viewport.camera import OrbitCamera

from .helpers import horizontal_edge, positions


def edit_state(params=BoxParams(h=6, n=3)) -> ls.LabState:
    state = ls.LabState(params)
    assert ls.PHASE_CHANGED in state.key("RETURN")
    return state


# -- creation phase -------------------------------------------------------------------------


def test_starts_in_creation_phase_with_a_plain_cube():
    state = ls.LabState()
    assert state.phase == lb.PHASE_CREATE and state.session is None
    assert state.box.counts() == (8, 12, 6)


@pytest.mark.parametrize("mods,field,delta", [
    (set(), "height", 0.25), ({"alt"}, "width", 0.25), ({"alt", "shift"}, "depth", 0.25),
    ({"shift"}, "h", 1), ({"ctrl"}, "n", 1),
])
def test_creation_wheel(mods, field, delta):
    state = ls.LabState()
    before = getattr(state.box, field)
    out = state.wheel(0, 1, mods)
    assert ls.BOX_CHANGED in out and out.zoom_steps == 0  # the wheel never zooms here
    assert getattr(state.box, field) == before + delta
    state.wheel(0, -1, mods)
    assert getattr(state.box, field) == before


def test_creation_clamps():
    state = ls.LabState()
    for _ in range(60):
        state.wheel(0, 1, {"shift"})
        state.wheel(0, 1, {"ctrl"})
        state.wheel(0, 1, set())
        state.wheel(0, -1, {"alt"})
    assert state.box.h == SEGMENTS_MAX and state.box.n == SEGMENTS_MAX
    assert state.box.height == SIZE_MAX and state.box.width == SIZE_MIN
    assert ls.BOX_CHANGED not in state.wheel(0, 1, {"shift"})  # at the clamp: no change


def test_horizontal_scroll_fallback():
    """Windows drivers that send Shift+wheel as `scroll_x`: read it when a modifier is held."""
    state = ls.LabState()
    state.wheel(1, 0, {"shift"})
    assert state.box.h == 2
    state.wheel(-1, 0, {"shift"})
    assert state.box.h == 1
    state.wheel(1, 0, {"ctrl"})
    assert state.box.n == 2
    state.wheel(1, 0, {"alt", "shift"})  # depth, also as a horizontal scroll
    assert state.box.depth == 2.25 and state.box.width == 2.0
    state.wheel(-1, 0, {"alt", "shift"})
    assert state.box.depth == 2.0
    height = state.box.height
    assert state.wheel(1, 0, set()).effects == set()  # no modifier: no fallback
    assert state.box.height == height
    assert lb.wheel_steps(0.3, 0, {"alt"}) == 1 and lb.wheel_steps(0, -2.5, set()) == -1


def test_unknown_modifier_combinations_do_nothing():
    state = ls.LabState()
    box = state.box
    assert state.wheel(0, 1, {"shift", "ctrl"}).effects == set()
    assert state.box == box


def test_enter_commits_also_without_divisions():
    state = ls.LabState()
    out = state.key("RETURN")
    assert ls.PHASE_CHANGED in out and state.phase == lb.PHASE_EDIT
    assert len(state.session.mesh.all_vertex_ids()) == 8
    assert state.key("RETURN").effects == set()  # Enter means nothing in the edit phase
    state2 = ls.LabState()
    state2.key("ENTER")  # numpad Enter
    assert state2.phase == lb.PHASE_EDIT


def test_edit_keys_do_nothing_in_creation_phase():
    state = ls.LabState()
    for name in ("TAB", "X", "_1", "_2", "_3", "K", "N", "B"):
        assert state.key(name).effects == set(), name
    assert state.key("Z", {"ctrl"}).effects == set()
    assert state.mode == MODE_LOOP and state.axis is None


# -- edit phase --------------------------------------------------------------------------------


def test_tab_toggles_loop_ring_sticky():
    state = edit_state()
    assert ls.PREVIEW_CHANGED in state.key("TAB")
    assert state.mode == MODE_RING
    state.key("TAB")
    assert state.mode == MODE_LOOP


def test_axis_keys_sticky_same_key_off():
    state = edit_state()
    state.key("X")
    assert state.axis == "x" and state.axis_mask == (1.0, 0.0, 0.0)
    state.key("Y")
    assert state.axis == "y"
    state.key("Y")
    assert state.axis is None
    state.key("Z")
    assert state.masked((1.0, 2.0, 3.0)) == (0.0, 0.0, 3.0)
    # Slice 2b E18: Shift+X/Y/Z = sticky exclude-axis planes in the same state (B4.1)
    state.key("X", {"shift"})
    assert state.axis == "yz" and state.masked((1.0, 2.0, 3.0)) == (0.0, 2.0, 3.0)
    state.key("Y", {"shift"})
    assert state.axis == "xz" and state.axis_mask == (1.0, 0.0, 1.0)
    state.key("Z", {"shift"})
    assert state.axis == "xy"
    state.key("Z", {"shift"})
    assert state.axis is None
    state.key("Y", {"shift"})
    state.key("Z")  # another key replaces
    assert state.axis == "z"


def test_axis_mask_applies_to_the_drag():
    state = edit_state()
    target = state.session.target(horizontal_edge(state.session.mesh, 0.0), MODE_LOOP)
    start = positions(state.session.mesh)
    state.key("Y")
    state.begin_drag(target)
    state.drag_step((0.3, 0.2, -0.4))
    state.end_drag()
    for vid in target.seeds:
        p, s = state.session.mesh.vertex_position(vid), start[vid]
        assert (p[0], p[2]) == (s[0], s[2]) and p[1] == s[1] + 0.2


def test_presets():
    state = edit_state()
    assert state.curve.preset == PRESET_SMOOTH
    assert ls.PREVIEW_CHANGED in state.key("K", {"shift"})
    assert state.curve.preset == PRESET_HAT
    state.key("K")
    assert state.curve.preset == PRESET_SMOOTH
    assert state.key("K").effects == set()  # already Smooth


def test_edit_wheel_zoom_and_radius():
    state = edit_state()
    assert state.wheel(0, 1).zoom_steps == 1 and state.wheel(0, -1).zoom_steps == -1
    assert state.radius_step == DEFAULT_RADIUS_STEP and state.radius_percent == 15
    out = state.wheel(0, 1, {"shift"})
    assert ls.PREVIEW_CHANGED in out and state.radius_step == DEFAULT_RADIUS_STEP + 1
    for _ in range(30):
        state.wheel(0, 1, {"shift"})
    assert state.radius_percent == RADIUS_STEPS_PERCENT[-1] == 200
    for _ in range(30):
        state.wheel(0, -1, {"shift"})
    assert state.radius_percent == 2
    assert state.wheel(0, 1, {"ctrl"}).effects == set() and state.wheel(0, 1, {"alt"}).effects == set()


def test_metric_bands_nachfuehren_help():
    state = edit_state()
    assert state.metric == "geodesic"
    state.key("O", {"ctrl"})
    assert state.metric == "euclidean"
    state.key("O", {"ctrl"})
    assert state.metric == "geodesic"
    state.key("O", {"alt"})
    assert not state.bands_visible
    state.key("N")
    assert not state.nachfuehren
    state.key("H")
    assert state.help_visible and state.help_lines()
    assert state.key("O").effects == set()  # plain O is unbound (app: Soft toggle)


def _drag(state, delta=(0.0, 0.2, 0.0), target=None):
    if target is None:
        target = state.session.target(horizontal_edge(state.session.mesh, 0.0), MODE_LOOP)
    state.begin_drag(target)
    state.drag_step(delta)
    return target


def test_esc_during_drag_cancels_exactly_and_idle_quits():
    state = edit_state()
    start = positions(state.session.mesh)
    _drag(state)
    assert state.dragging
    out = state.key("ESCAPE")
    assert ls.QUIT not in out and ls.MESH_CHANGED in out and out.changed
    assert not state.dragging
    assert positions(state.session.mesh) == start and len(state.session.history) == 0
    assert ls.QUIT in state.key("ESCAPE")
    assert ls.QUIT in ls.LabState().key("ESCAPE")  # also in the creation phase


def test_release_commits_one_entry_and_undo_redo_keys():
    state = edit_state()
    start = positions(state.session.mesh)
    _drag(state)
    out = state.end_drag()
    assert ls.REPICK in out and len(state.session.history) == 1
    end = positions(state.session.mesh)
    out = state.key("Z", {"ctrl"})
    assert ls.MESH_CHANGED in out and out.changed is None
    assert positions(state.session.mesh) == start
    state.key("Y", {"ctrl"})
    assert positions(state.session.mesh) == end


def test_undo_ignored_during_drag():
    state = edit_state()
    target = _drag(state)
    state.end_drag()
    _drag(state, (0.0, 0.1, 0.0), target)
    assert state.key("Z", {"ctrl"}).effects == set()
    assert state.dragging and len(state.session.history) == 1


def test_new_box_needs_confirmation():
    state = edit_state(BoxParams(h=4, n=2))
    _drag(state)
    state.end_drag()
    out = state.key("B")
    assert state.confirm_new_box and state.phase == lb.PHASE_EDIT
    assert any(line.style == "warning" for line in state.hud_lines(None))
    out = state.key("B")
    assert {ls.PHASE_CHANGED, ls.BOX_CHANGED} <= out.effects
    assert state.phase == lb.PHASE_CREATE and state.session is None
    assert state.box == BoxParams(h=4, n=2)  # starts from the last box


def test_new_box_confirmation_cancelled_by_other_key_and_by_esc():
    state = edit_state()
    state.key("B")
    state.key("TAB")
    assert not state.confirm_new_box and state.phase == lb.PHASE_EDIT and state.mode == MODE_RING
    state.key("B")
    out = state.key("ESCAPE")
    assert ls.QUIT not in out and not state.confirm_new_box and state.phase == lb.PHASE_EDIT


def test_b_ignored_during_drag():
    state = edit_state()
    _drag(state)
    state.key("B")
    assert not state.confirm_new_box and state.dragging


def test_settings_survive_a_new_box():
    state = edit_state()
    state.key("TAB")
    state.key("X")
    state.key("K", {"shift"})
    state.key("N")
    state.key("B")
    state.key("B")
    state.key("RETURN")
    assert (state.mode, state.axis, state.curve.preset, state.nachfuehren) == (MODE_RING, "x", PRESET_HAT, False)
    assert len(state.session.history) == 0


def test_hud_and_status_text():
    state = ls.LabState()
    assert "Loops 0" in state.status_text() and "V 8 / E 12 / F 6" in state.status_text()
    state.wheel(0, -1, {"alt", "shift"})
    assert "Breite 2 · Tiefe 1.75" in state.status_text() and "Höhe 2" in state.status_text()
    state.key("RETURN")
    text = state.status_text()
    assert "Loop" in text and "15 %" in text and "geodesic" in text and "Nachführen an" in text
    assert "Vorschau aus" in text
    assert state.hud_lines(16.0)[0].style == "title"


def test_depth_is_independent_of_width():
    state = ls.LabState()
    for _ in range(3):
        state.wheel(0, -1, {"alt", "shift"})
    state.wheel(0, 2, {"alt"})
    assert (state.box.width, state.box.depth, state.box.height) == (2.25, 1.25, 2.0)
    state.key("RETURN")
    xs = [p[0] for p in positions(state.session.mesh).values()]
    zs = [p[2] for p in positions(state.session.mesh).values()]
    assert (max(xs) - min(xs), max(zs) - min(zs)) == (2.25, 1.25)


def test_p_toggles_the_surface_preview_default_off():
    state = edit_state()
    assert state.preview_visible is False  # A9: optional, off at start
    out = state.key("P")
    assert ls.DISPLAY_CHANGED in out and state.preview_visible
    state.key("P")
    assert not state.preview_visible
    state.key("P")
    state.key("B")
    state.key("B")
    state.key("RETURN")
    assert state.preview_visible  # sticky like the other display settings


def test_enter_passes_the_rims_to_the_session():
    state = edit_state(BoxParams(h=3, n=2))
    finder = state.session.finder
    assert len(finder.rim_of_edge) == 16
    top = horizontal_edge(state.session.mesh, 1.0)
    target = state.session.target(top, MODE_LOOP)
    assert target.closed and len(target.edges) == 8


def test_handle_mode_only_change_is_display_only():
    state = edit_state()
    curve = state.curve
    broken = curve.with_handle(2, "out", *curve.handles_out[2], break_alignment=True)
    assert broken.shape == curve.shape and broken != curve
    out = state.set_curve(broken)
    assert out.effects == {ls.DISPLAY_CHANGED} and state.curve.aligned[2] is False
    out = state.set_curve(state.curve.with_knot(2, 0.45, 0.3))
    assert ls.PREVIEW_CHANGED in out


# -- Slice 2b E16–E20: W/E/R held over the hover target ------------------------------------------

W, H = 800, 600


def hold_state(params=BoxParams(h=6, n=3), curve_key=None):
    state = edit_state(params)
    if curve_key:
        state.key(*curve_key)
    state.hover_target = state.session.target(horizontal_edge(state.session.mesh, 0.0), MODE_LOOP)
    camera = OrbitCamera()
    return state, camera


def test_hold_r_arms_moves_and_commits_one_entry():
    state, cam = hold_state()
    start = positions(state.session.mesh)
    out = state.key("R")
    assert state.armed and not state.dragging and ls.DISPLAY_CHANGED in out
    assert positions(state.session.mesh) == start  # arming moves nothing
    out = state.hold_motion(10, 5, W, H, cam)
    assert ls.GESTURE_BEGAN in out and ls.MESH_CHANGED in out and state.dragging
    state.hold_motion(20, 0, W, H, cam)
    assert state.session.drag.kind == "scale"
    assert state.session.drag.total == pytest.approx((1.0 + ScaleTool.SCALE_PER_PIXEL * 35,) * 3)
    out = state.key_release("R")
    assert ls.REPICK in out and not state.armed and not state.dragging
    assert len(state.session.history) == 1 and state.session.last.kind == "scale"
    assert positions(state.session.mesh) != start


def test_tap_without_motion_is_a_no_op_and_zero_motion_does_not_begin():
    state, cam = hold_state()
    start = positions(state.session.mesh)
    for name in ("W", "E", "R"):
        state.key(name)
        assert state.hold_motion(0, 0, W, H, cam).effects == set() and not state.dragging
        state.key_release(name)
        assert not state.armed
    assert positions(state.session.mesh) == start and len(state.session.history) == 0


def test_target_is_frozen_at_the_key_press():
    state, cam = hold_state()
    armed_target = state.hover_target
    state.key("E")
    state.hover_target = state.session.target(horizontal_edge(state.session.mesh, 1.0 / 3.0), MODE_LOOP)
    state.hold_motion(15, 0, W, H, cam)
    assert state.session.drag.target is armed_target


def test_no_hover_no_arm_and_second_hold_key_ignored():
    state, cam = hold_state()
    target = state.hover_target
    state.hover_target = None
    state.key("R")
    assert not state.armed and "nichts ausgewählt oder gehovert" in state.note
    state.hover_target = target
    state.key("R")
    state.key("E")  # a second hold key while one is held: ignored
    assert state.hold.kind == "scale"
    state.key_release("E")  # releasing the other key does nothing
    assert state.armed


def test_rotate_mapping_and_axis():
    state, cam = hold_state()
    state.key("E")
    state.hold_motion(12, 40, W, H, cam)  # dy does not rotate
    state.hold_motion(8, 0, W, H, cam)
    assert state.session.drag.total == pytest.approx(RotateTool.RADIANS_PER_PIXEL * 20)
    assert state.session.drag.axis == pytest.approx(cam.basis()[0])  # view axis at begin
    state.key_release("E")
    state.key("Y")
    state.key("E")
    state.hold_motion(5, 0, W, H, cam)
    assert state.session.drag.axis == (0.0, 1.0, 0.0)
    state.key_release("E")
    state.key("Y", {"shift"})  # plane XZ → rotate about Y as well (`_resolve_space`, for_rotation)
    state.key("E")
    state.hold_motion(5, 0, W, H, cam)
    assert state.session.drag.axis == (0.0, 1.0, 0.0)
    state.key_release("E")


def test_rotate_chunking_independent():
    a, cam = hold_state()
    b, _ = hold_state()
    for s, chunks in ((a, [30]), (b, [10, 10, 10])):
        s.key("E")
        for dx in chunks:
            s.hold_motion(dx, 0, W, H, cam)
        s.key_release("E")
    pa, pb = positions(a.session.mesh), positions(b.session.mesh)
    assert all(math.dist(pa[v], pb[v]) <= 1e-12 for v in pa)


def test_scale_waist_with_plane_and_min_scale():
    state, cam = hold_state()
    state.key("Y", {"shift"})
    start = positions(state.session.mesh)
    state.key("R")
    state.hold_motion(-1000, -1000, W, H, cam)  # far inward: clamped like ScaleTool
    assert state.session.drag.total == (ScaleTool.MIN_SCALE, 1.0, ScaleTool.MIN_SCALE)
    state.key_release("R")
    for vid in state.session.last.seeds:
        assert state.session.mesh.vertex_position(vid)[1] == start[vid][1]  # Y untouched
    # a constraint key during a running gesture applies only from the next one
    state.key("R")
    state.hold_motion(10, 0, W, H, cam)
    state.key("X")
    state.hold_motion(10, 0, W, H, cam)
    assert state.session.drag.total[1] == 1.0 and state.axis == "x"
    state.key_release("R")


def test_hold_w_moves_like_the_lmb_drag():
    state, cam = hold_state()
    start = positions(state.session.mesh)
    state.key("Y")
    state.key("W")
    state.hold_motion(0, 25, W, H, cam)
    state.key_release("W")
    assert state.session.last.kind == "move"
    for vid in state.session.last.seeds:
        p, s = state.session.mesh.vertex_position(vid), start[vid]
        assert (p[0], p[2]) == (s[0], s[2]) and p[1] > s[1]


def test_cancel_paths_and_undo_during_hold():
    state, cam = hold_state()
    start = positions(state.session.mesh)
    state.key("R")
    state.hold_motion(30, 0, W, H, cam)
    out = state.key("ESCAPE")
    assert ls.QUIT not in out and not state.armed and not state.dragging
    assert positions(state.session.mesh) == start and len(state.session.history) == 0
    state.key("R")
    out = state.key("ESCAPE")  # armed only: disarm, no quit
    assert ls.QUIT not in out and not state.armed
    # a committed gesture, then Undo while a new one runs: ignored; while only armed: disarm + undo
    state.key("E")
    state.hold_motion(30, 0, W, H, cam)
    state.key_release("E")
    state.key("R")
    state.hold_motion(10, 0, W, H, cam)
    assert state.key("Z", {"ctrl"}).effects == set() and state.dragging
    state.cancel_drag()  # RMB path
    assert not state.armed and len(state.session.history) == 1
    state.key("R")
    out = state.key("Z", {"ctrl"})
    assert ls.MESH_CHANGED in out and not state.armed
    assert positions(state.session.mesh) == start


def test_m_toggles_formula_and_retunes_the_last_scale():
    state, cam = hold_state(BoxParams(h=10, n=4), curve_key=("K", {"shift"}))
    for _ in range(6):
        state.wheel(0, 1, {"shift"})  # bigger radius: the negative lobe reaches vertices
    assert state.scale_formula == "linear" and "Scale linear" in state.status_text()
    state.key("Y", {"shift"})
    state.key("R")
    state.hold_motion(1000, 0, W, H, cam)  # F = 6: linear g <= 0 for every w <= -0.2
    assert state.collapsed is not None
    collapsed_linear = state.collapsed
    state.key_release("R")
    assert any("g ≤ 0" in line.text for line in state.hud_lines(None))
    linear = positions(state.session.mesh)
    out = state.key("M")
    assert state.scale_formula == "power" and ls.MESH_CHANGED in out
    assert positions(state.session.mesh) != linear and len(state.session.history) == 1
    assert state.collapsed == 0 and collapsed_linear > 0
    state.key("M")
    assert positions(state.session.mesh) == linear and state.collapsed == collapsed_linear
