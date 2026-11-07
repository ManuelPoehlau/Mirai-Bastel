"""GUI Phase A1 (2026-11-03): the status strip, the orientation triad and the current bone's name, headless.

Rows per state (pose mode, posed + bound badge, non-default filtering, dimmed hints, the morph suffix), the bone
name item, the triad's directions for known camera states and its layout against the strip, the "never rebuilt per
frame" contract of the triad and the tag (GL-free stand-ins), and the new window keys against every binding. The
real pyglet objects are in `tests/test_gl_hud_marks.py`. The older HUD tests stay in `tests/test_hud.py`.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

from hud import (
    TRIAD_CORNERS,
    TRIAD_LABEL_ROOM,
    TRIAD_MARGIN,
    TRIAD_SIZES,
    Hud,
    OrientationTriad,
    hud_rows,
    hud_state,
    key_hint_parts,
    key_hints,
    strip_rows,
    triad_axes,
    triad_center,
)
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.viewport.camera import OrbitCamera
from tests.interaction_trace import key
from tests.rig_support import E, FALLOFF, POSE_MODE, head_driver, hold, rig_head


def _key(value: str, *mods: str) -> Input:
    return Input("key", value, frozenset(mods))


@pytest.fixture
def app():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(800, 600)
    return app


def _rows(app_or_state, hints=None, parts=None):
    state = hud_state(app_or_state) if isinstance(app_or_state, Application) else app_or_state
    return hud_rows(state, {} if hints is None else hints, parts)


def _labels(rows):
    return [row.label for row in rows]


@pytest.fixture(scope="module")
def posed_rig():
    """The head rigged, weighted from its group and posed (E held in pose mode) - as in `test_application_rig`."""
    d = head_driver()
    rig_head(d)
    hold(d, FALLOFF)
    d.tap(POSE_MODE)
    hold(d, E, ((30, 5), (10, 0)))
    assert d.app.posed
    return d


# -- the strip: what it lists ------------------------------------------------------------------------------


def test_default_state_lists_only_mode_and_tool(app):
    rows = strip_rows(_rows(app), "compact")
    assert _labels(rows) == ["Mode", "Tool"]
    assert _labels(strip_rows(_rows(app), "full")) == _labels(_rows(app))  # full = every row, none dropped


def test_only_settings_off_their_default_join_the_strip(app):
    """Axis, Space, Pivot, Sym, Soft, SubD appear when they deviate, and leave again when back at the default."""
    shown = lambda: _labels(strip_rows(_rows(app), "compact"))  # noqa: E731
    app.key_press(_key("x"))
    assert shown() == ["Mode", "Tool", "Axis"]
    app.key_press(_key("x"))  # toggled off again
    assert shown() == ["Mode", "Tool"]
    app.key_press(_key("f7"))  # sticky constraints are not the default either, even with no axis chosen
    assert "Axis" in shown()
    app.key_press(_key("f7"))
    app.key_press(_key("s", "shift"))
    app.key_press(_key("o"))
    app.key_press(_key("v"))
    app.key_press(_key("k"))
    assert shown() == ["Mode", "Tool", "Space", "Sym", "Soft", "SubD"]
    # Display / View / Look / Region / Fixed are the secondary tier: never in the strip, always in "full".
    secondary = [row.label for row in _rows(app) if row.tier == "secondary"]
    assert secondary == ["Display", "View", "Region", "Look", "Fixed"]
    assert not set(secondary) & set(shown())
    assert set(secondary) <= set(_labels(strip_rows(_rows(app), "full")))


def test_the_mode_row_is_one_row_of_five_modes_with_pose_as_the_fifth(app):
    mode = _rows(app)[0]
    assert mode.label == "Mode" and mode.choices == ("Vertex", "Edge", "Face", "Object", "Pose")
    assert mode.chosen == "Vertex" and mode.value == "Vertex" and mode.on
    for digit, name in (("2", "Edge"), ("3", "Face"), ("4", "Object")):
        app.key_press(_key(digit))
        assert _rows(app)[0].chosen == name
    assert mode.keys == "" and key_hints(app.bindings)["Mode"] == "1/2/3/4/5"


def test_pose_mode_is_the_chosen_mode_and_the_tool_names_the_bone(posed_rig):
    app = posed_rig.app
    assert app.pose_mode
    rows = {row.label: row for row in _rows(app)}
    assert rows["Mode"].chosen == "Pose" and rows["Mode"].value == "Pose"
    assert rows["Tool"].value == "Bone · Rotate"  # the last W/E/R was E (the scenario poses with it)
    state = hud_state(app)
    assert state.mode in ("Vertex", "Edge", "Face", "Object") and state.pose_mode  # the selection mode is untouched


def test_the_running_gesture_in_pose_mode_is_called_bone(posed_rig):
    d = posed_rig
    d.key_down(E)
    try:
        state = hud_state(d.app)
        assert state.active == "Bone · Rotate"
        assert {row.label: row for row in _rows(state)}["Tool"].value == "Bone · Rotate (running)"
    finally:
        d.key_up("e")
    assert hud_state(d.app).active is None


def test_a_running_tweak_outside_pose_mode_keeps_its_name(app):
    app.selection.vertices = {next(iter(app.scene.mesh.all_vertex_ids()))}
    app.key_press(_key("w"))
    assert hud_state(app).active == "Tweak · Move"
    app.key_release(_key("w"))


def test_a_rig_gesture_is_named_by_its_own_label(posed_rig):
    """A weight gesture is no transform tool: the HUD shows the gesture's label, not the raw command name."""
    d = posed_rig
    d.key_down(key("8"))
    try:
        assert d.app.gesture_label == "Set weight"
        assert hud_state(d.app).active == "Set weight"
    finally:
        d.key_up("8")


def test_the_morph_editing_view_is_a_suffix_of_the_mode(app):
    app.key_press(_key("3"))
    app.key_press(_key("n", "ctrl"))  # a new target
    assert _rows(app)[0].value == "Face" and hud_state(app).morph_view is None
    assert app.key_press(_key("tab")), app.status_message  # edit the target beside the base
    name = app.morph_editing_target_name
    assert name is not None
    mode = _rows(app)[0]
    assert mode.value == f"Face · target {name!r}" and mode.suffix == f"target {name!r}" and mode.chosen == "Face"
    app.key_press(_key("tab"))
    assert _rows(app)[0].suffix == "" and hud_state(app).morph_view is None


def test_the_current_target_and_bone_show_only_when_they_exist(app, posed_rig):
    assert not {"Morph", "Bone"} & set(_labels(strip_rows(_rows(app), "compact")))
    app.key_press(_key("n", "ctrl"))
    assert "Morph" in _labels(strip_rows(_rows(app), "compact"))
    rig_app = posed_rig.app
    strip = {row.label: row for row in strip_rows(_rows(rig_app), "compact")}
    assert strip["Bone"].value.endswith(" · posed") and strip["Bone"].value.startswith("'")
    assert strip["Bone"].on and "Rig" not in strip  # the long rig text is the secondary row


# -- the warning badge ----------------------------------------------------------------------------------------


def test_the_badge_appears_while_the_edit_mesh_is_posed_and_bound(posed_rig):
    app = posed_rig.app
    assert app.edit_mesh_posed_and_bound
    state = hud_state(app)
    assert state.pose_locked and state.posed
    hints = key_hints(app.bindings)
    rows = hud_rows(state, hints)
    assert rows[0].tier == "badge" and rows[0].value == "Pose · 6 = rest" and rows[0].on
    assert strip_rows(rows, "compact")[0] is rows[0]  # the badge is in every detail
    # the key comes from the bindings: a rebinding shows
    assert hud_rows(state, {"Rest": "F9"})[0].value == "Pose · F9 = rest"
    assert hud_rows(state, {})[0].value == "Pose · mesh posed and bound"


def test_the_badge_is_announced_before_the_refusal_and_goes_with_the_rest_pose(posed_rig):
    d = posed_rig
    app = d.app
    d.tap(key("6"))  # POSE_TOGGLE_REST: back to rest
    try:
        assert not app.posed and not hud_state(app).pose_locked
        assert hud_rows(hud_state(app), key_hints(app.bindings))[0].tier != "badge"
    finally:
        d.tap(key("6"))  # and back to the pose for the other tests
    assert hud_state(app).pose_locked


def test_an_unbound_posed_mesh_gets_no_badge(app):
    """Posed but not bound (no weights): nothing is refused, so nothing is announced."""
    state = dataclasses.replace(hud_state(app), posed=True, pose_locked=False)
    assert _rows(state)[0].label == "Mode"


def test_an_invalid_keymap_is_a_badge(app):
    state = dataclasses.replace(hud_state(app), keymap_problem="bad json")
    rows = _rows(state)
    assert rows[0].label == "Keymap" and rows[0].tier == "badge" and rows[0].on
    assert "Keymap" in _labels(strip_rows(rows, "compact"))


# -- dimmed hints ---------------------------------------------------------------------------------------------


def test_hints_of_unavailable_commands_are_dimmed(app):
    hints, parts = key_hints(app.bindings), key_hint_parts(app.bindings)
    state = dataclasses.replace(hud_state(app), unavailable=frozenset({commands.SOFT_TOGGLE, commands.POSE_MODE}))
    rows = {row.label: row for row in hud_rows(state, hints, parts)}
    assert rows["Soft"].key_parts == (("O", True),)
    assert rows["Mode"].key_parts == (("1", False), ("2", False), ("3", False), ("4", False), ("5", True))
    assert rows["Tool"].key_parts == (("W", False), ("E", False), ("R", False))
    assert rows["Mode"].keys == "1/2/3/4/5"  # the text form is unchanged


def test_the_runs_of_a_dimmed_hint_keep_the_slashes():
    from hud import HudRow, _key_runs

    row = HudRow("Mode", "Face", "1/2/3/4/5", key_parts=(("1", False), ("2", False), ("5", True)))
    assert _key_runs(row) == [("[1/2/", False), ("5]", True)]
    assert _key_runs(dataclasses.replace(row, key_parts=(("5", True),))) == [("[5]", True)]
    assert _key_runs(dataclasses.replace(row, key_parts=())) == [("[1/2/3/4/5]", False)]
    assert _key_runs(dataclasses.replace(row, keys="", key_parts=())) == []


def test_pose_mode_dims_the_commands_it_refuses(posed_rig):
    """The real `can_run` data: in pose mode modelling commands are refused, so their hints go dim."""
    app = posed_rig.app
    state = hud_state(app)
    assert commands.SYMMETRY_CYCLE in state.unavailable
    rows = {row.label: row for row in hud_rows(state, key_hints(app.bindings), key_hint_parts(app.bindings))}
    assert any(dim for _, dim in rows["Sym"].key_parts)
    assert all(not dim for _, dim in rows["Mode"].key_parts)  # the mode keys leave pose mode: available
    assert all(not dim for _, dim in rows["Tool"].key_parts)  # W/E/R pose the bone


# -- read-only guard ------------------------------------------------------------------------------------------


def test_the_hud_and_its_marks_assign_nothing_to_the_app(posed_rig):
    class Guard:
        def __init__(self, target):
            object.__setattr__(self, "_t", target)

        def __getattr__(self, name):
            return getattr(self._t, name)

        def __setattr__(self, name, value):
            raise AssertionError(f"HUD wrote app.{name}")

    app = posed_rig.app
    guarded = Guard(app)
    Hud(app.bindings).update(guarded, 800, 600)
    triad = OrientationTriad()
    triad.make_parts = _FakeTriadParts
    triad.update(guarded.camera, 800, 600)
    before = (app.status_serial, app.status_message, app.pose, app.selection.mode, app.current_bone, app.posed)
    for _ in range(3):
        hud_state(app)
    assert before == (app.status_serial, app.status_message, app.pose, app.selection.mode, app.current_bone, app.posed)


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# -- the orientation triad: directions -------------------------------------------------------------------------


def _triad(camera):
    return {name: (right, up, depth) for name, right, up, depth in triad_axes(camera)}


def _near(a, b, eps=1e-9):
    return all(abs(x - y) < eps for x, y in zip(a, b))


def test_front_ortho_x_is_right_y_is_up_and_z_points_at_the_viewer():
    camera = OrbitCamera()
    camera.set_view(0.0, 0.0, ortho=True)  # Front
    axes = _triad(camera)
    assert _near(axes["X"][:2], (1.0, 0.0)) and _near(axes["Y"][:2], (0.0, 1.0)) and _near(axes["Z"][:2], (0.0, 0.0))
    assert axes["X"][2] == pytest.approx(0.0) and axes["Z"][2] == pytest.approx(-1.0)  # toward the viewer


@pytest.mark.parametrize(
    "yaw, pitch, expected",
    [
        (math.pi / 2, 0.0, {"X": (0, 0), "Y": (0, 1), "Z": (-1, 0)}),  # Right: +Z runs to the left
        (math.pi, 0.0, {"X": (-1, 0), "Y": (0, 1), "Z": (0, 0)}),  # Back: +X runs to the left
        (-math.pi / 2, 0.0, {"X": (0, 0), "Y": (0, 1), "Z": (1, 0)}),  # Left
        (0.0, math.pi / 2, {"X": (1, 0), "Y": (0, 0), "Z": (0, -1)}),  # Top: +Z runs down the screen
        (0.0, -math.pi / 2, {"X": (1, 0), "Y": (0, 0), "Z": (0, 1)}),  # Bottom
    ],
)
def test_snapped_views_turn_the_axes_as_expected(yaw, pitch, expected):
    camera = OrbitCamera()
    camera.set_view(yaw, pitch, ortho=True)
    for name, (right, up) in expected.items():
        assert _near(_triad(camera)[name][:2], (right, up)), name


def test_a_free_perspective_view_keeps_the_handedness():
    camera = OrbitCamera(yaw=math.radians(45), pitch=math.radians(25))
    axes = _triad(camera)
    assert axes["X"][0] > 0 > axes["Z"][0] and axes["Y"][1] > 0
    # the three screen vectors come from a rotation: right/up/depth of each axis is a unit vector
    for right, up, depth in axes.values():
        assert right * right + up * up + depth * depth == pytest.approx(1.0)
    # the camera's own projection agrees: +X really lies to the right of the origin on screen
    origin = camera.project_to_screen((0.0, 0.0, 0.0), 800, 600)
    x_axis = camera.project_to_screen((1.0, 0.0, 0.0), 800, 600)
    assert x_axis[0] > origin[0]


def test_the_triad_ignores_zoom_and_pan_and_perspective():
    a, b = OrbitCamera(), OrbitCamera(target=(5.0, 2.0, -3.0), distance=40.0, fov_degrees=20.0)
    assert triad_axes(a) == triad_axes(b)  # only the view rotation counts
    b.set_ortho(True)
    assert triad_axes(a) == triad_axes(b)


# -- the orientation triad: layout against the strip ------------------------------------------------------------


@pytest.mark.parametrize("corner", TRIAD_CORNERS)
@pytest.mark.parametrize("size", TRIAD_SIZES)
def test_the_triad_stays_inside_the_window_in_both_corners(corner, size):
    length = TRIAD_SIZES[size]
    cx, cy = triad_center(corner, length, 1024, 768)
    reach = length + TRIAD_LABEL_ROOM
    assert TRIAD_MARGIN <= cx - reach and cx + reach <= 1024 - TRIAD_MARGIN
    assert TRIAD_MARGIN <= cy - reach and cy + reach <= 768 - TRIAD_MARGIN


class _StripBuilder:
    last = None

    def __init__(self, sink):
        self.batch, self.sink, self.rects = None, sink, []
        _StripBuilder.last = self

    def label(self, text, x, y, color):
        item = _Obj(text=text, x=x, y=y, content_width=7 * len(text), delete=lambda: None)
        self.sink.append(item)
        return item

    def rect(self, x, y, width, height, color=None, badge=False):
        self.rects.append((x, y, width, height))


@pytest.mark.parametrize("corner", TRIAD_CORNERS)
@pytest.mark.parametrize("position", ("bottom", "top"))
@pytest.mark.parametrize("detail", ("compact", "full"))
@pytest.mark.parametrize("width", (1280, 700, 420))
@pytest.mark.parametrize("size", TRIAD_SIZES)
def test_the_triad_never_collides_with_the_strip(app, corner, position, detail, width, size):
    """Both strip positions, both details, a wide and a narrow (wrapped) window, both corners and both sizes."""
    height = 768
    hud = Hud(app.bindings, position=position, detail=detail)
    hud.make_builder = _StripBuilder
    app.key_press(_key("s", "shift"))  # a few more rows so the narrow strip wraps
    app.key_press(_key("o"))
    hud.update(app, width, height)
    hud.draw()
    strip_x, strip_y, strip_w, strip_h = _StripBuilder.last.rects[0]
    triad = OrientationTriad(corner=corner, size=size)
    triad.make_parts = lambda: _FakeTriadParts()
    camera = OrbitCamera()
    camera.set_view(0.0, 0.0, ortho=True)
    triad.update(camera, width, height, hud.inset_top, hud.inset_bottom)
    reach = triad.length + TRIAD_LABEL_ROOM
    cx, cy = triad_center(corner, triad.length, width, height, hud.inset_top, hud.inset_bottom)
    box = (cx - reach, cy - reach, cx + reach, cy + reach)
    strip = (strip_x, strip_y, strip_x + strip_w, strip_y + strip_h)
    assert box[2] <= strip[0] or box[0] >= strip[2] or box[3] <= strip[1] or box[1] >= strip[3], (box, strip)
    assert 0 <= box[0] and box[2] <= width and 0 <= box[1] and box[3] <= height
    # and the placed tips / letters are inside that box
    for _, tip, letter in triad.placement:
        for px, py in (tip, letter):
            assert box[0] <= px <= box[2] and box[1] <= py <= box[3]


def test_a_hidden_hud_leaves_the_corner_free(app):
    hud = Hud(app.bindings, visible=False)
    assert (hud.inset_top, hud.inset_bottom) == (0, 0)
    hud = Hud(app.bindings)
    hud.make_builder = _StripBuilder
    hud.update(app, 800, 600)
    hud.draw()
    assert hud.inset_bottom > 0 and hud.inset_top == 0
    hud.toggle()
    assert (hud.inset_top, hud.inset_bottom) == (0, 0)


# -- the orientation triad: no per-frame rebuilds --------------------------------------------------------------


class _FakeTriadParts:
    instances = 0

    def __init__(self):
        type(self).instances += 1
        self.lines = [_Obj(position=(0, 0), x2=0.0, y2=0.0, opacity=255) for _ in range(3)]
        self.labels = [_Obj(x=0.0, y=0.0, opacity=255) for _ in range(3)]
        self.draws = 0

    def draw(self):
        self.draws += 1


def test_the_triad_is_created_once_and_only_moves_when_its_inputs_change():
    _FakeTriadParts.instances = 0
    triad = OrientationTriad()
    triad.make_parts = _FakeTriadParts
    camera = OrbitCamera()
    for _ in range(50):  # an idle viewport: nothing is touched, the parts are drawn each frame
        triad.draw(camera, 1024, 768)
    assert _FakeTriadParts.instances == 1 and triad.moves == 1
    assert triad._parts.draws == 50
    for index in range(100):  # an orbit: a move per frame, never a new object
        camera.orbit(0.01, 0.002)
        triad.draw(camera, 1024, 768)
    assert triad.moves == 101 and _FakeTriadParts.instances == 1
    triad.toggle_corner()
    triad.draw(camera, 1024, 768)
    triad.toggle_size()
    triad.draw(camera, 1024, 768)
    triad.draw(camera, 1024, 768, 0, 60)  # the strip appeared under it
    assert triad.moves == 104 and _FakeTriadParts.instances == 1
    assert triad.corner == "top-right" and triad.size == "S"


def test_the_triad_dims_axes_that_point_away_and_tracks_the_letters():
    triad = OrientationTriad()
    triad.make_parts = _FakeTriadParts
    camera = OrbitCamera()
    camera.set_view(0.0, 0.0, ortho=True)
    triad.update(camera, 800, 600)
    lines, labels = triad._parts.lines, triad._parts.labels
    assert [line.opacity for line in lines] == [255, 255, 255]  # none points away in Front
    camera.set_view(math.pi, 0.0, ortho=True)  # Back: Z points away from the viewer
    triad.update(camera, 800, 600)
    assert [line.opacity for line in lines] == [255, 255, 140]
    cx, cy = triad_center("bottom-left", triad.length, 800, 600)
    assert lines[0].position == (cx, cy)
    assert (lines[0].x2, lines[0].y2) == pytest.approx((cx - triad.length, cy))  # Back: +X runs to the left
    assert labels[0].x < cx and labels[1].y > cy  # letters sit past the tips
    assert labels[2].x > cx and labels[2].y > cy  # the end-on Z letter is placed beside the centre


def test_invalid_variants_are_refused():
    with pytest.raises(ValueError):
        OrientationTriad(corner="middle")
    with pytest.raises(ValueError):
        OrientationTriad(size="XL")


# -- keys: conflict check -----------------------------------------------------------------------------------------


NEW_KEYS = {
    "f3": commands.HUD_POSITION_TOGGLE,
    "f4": commands.HUD_DETAIL_TOGGLE,
    "f5": commands.TRIAD_CORNER_TOGGLE,
    "f6": commands.TRIAD_SIZE_TOGGLE,
}


def test_the_new_keys_are_window_commands_and_conflict_with_nothing():
    bindings = build_default_bindings()
    for value, command in NEW_KEYS.items():
        assert command in commands.WINDOW_COMMANDS
        f_key = _key(value)
        assert bindings.command_for(f_key, "window") == command
        assert bindings.command_for(f_key) is None  # `Application` never sees them
        for context in ("morph", "subd"):
            assert bindings.command_for(f_key, context) is None
        assert [inp for inp in bindings.inputs_for(command, "window")] == [f_key]
    # no other command, in any context, sits on these keys
    for command in commands.WINDOW_COMMANDS - set(NEW_KEYS.values()):
        for inp in bindings.inputs_for(command, "window"):
            assert not (inp.kind == "key" and inp.value in NEW_KEYS and not inp.modifiers)


def test_the_keymap_json_has_no_entry_on_the_new_keys():
    entries = json.loads((_REPO_ROOT / "config" / "keymap.json").read_text(encoding="utf-8"))["bindings"]
    taken = {
        (e["input"]["value"].lower(), tuple(e["input"].get("modifiers", [])))
        for e in entries if e["input"]["kind"] == "key"
    }
    for value in NEW_KEYS:
        assert (value, ()) not in taken
