"""Re-Symmetrize in the Production app (AD-SYM-04 slice A3, §10 R-a).

The preview is an `Application` interaction like the Knife session: the Re-Symmetrize key (default
Alt+M, `PROVISIONAL`) with exactly one selected vertex opens it (plan computed once), the key again
executes exactly that plan (one Undo step, an empty plan records nothing), Esc closes it. While it
is open `interaction_owner == "resymmetrize"`, only the pure display keys and navigation pass,
every other key, click, drag selection and Soft step is ignored with the hint, and the hover is
paused. Ported from the Symmetry Lab, where the preview lived until A3 (Lab gate row "preview
open", `hover_suspended`, D1):

| Lab test (`experiments/symmetry_lab/tests/`) | here |
|---|---|
| `test_app_lab_resymmetrize.py` (dispatcher ports: either side, seam, rejections, M/M, M/Esc, 0 changes, status, navigation, click before M, other keys, select, paired state) | same names |
| `test_app_lab_preview.py::test_plan_is_computed_once_when_opening`, `..._ctrl_z_restores_mesh_and_selection_then_redo`, `test_t_r2c_...`, `test_t_r2e_...`, `test_display_commands_pass_the_preview`, `test_n2_...`, `test_t_r3_...`, `test_t_h_...` | same statements against `Application` |
| `test_app_lab_preview.py::test_preview_layers_present_while_open_and_empty_after_execute` | `test_preview_layers_...` (the app's `GLSymmetryOverlay`) |
| `test_app_lab_preview_fuzz.py` (T-R2g) | `test_random_input_under_the_preview_changes_nothing` |

Headless (TraceStore) with the real symmetry sink type, as `src/main.py` passes it. Selection only
through clicks, symmetry through Shift+S, the preview through the bound key.
"""

from __future__ import annotations

import random
import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode, VertexId  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai import application as application_module  # noqa: E402
from mirai.application import RESYM_PREVIEW_HINT, Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.resymmetrize import plan_summary  # noqa: E402
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state  # noqa: E402
from mirai.symmetry_axis import current_axis  # noqa: E402
from mirai.symmetry_display import symmetry_report  # noqa: E402
from mirai.symmetry_topology import topology_report  # noqa: E402
from mirai.viewport.picking import pick_nearest_vertex  # noqa: E402
from viewport import gl_symmetry_overlay as sink_module  # noqa: E402
from viewport.gl_symmetry_overlay import GLSymmetryOverlay  # noqa: E402

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)
PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


ALT_M = _key("m", "alt")
SHIFT_S = _key("s", "shift")
W, E, R, C, D = _key("w"), _key("e"), _key("r"), _key("c"), _key("d")
SHIFT_D = _key("d", "shift")
X, SHIFT_X, ALT_A = _key("x"), _key("x", "shift"), _key("a", "alt")
ONE, TWO, THREE = _key("1"), _key("2"), _key("3")
ESC = _key("ESCAPE")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")
LMB = Input("mouse", "LEFT")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
CTRL_LMB = Input("mouse", "LEFT", frozenset({"ctrl"}))
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
WHEEL_UP = Input("wheel", "UP")
SHIFT_WHEEL_UP = Input("wheel", "UP", frozenset({"shift"}))


# -- helpers ----------------------------------------------------------------------------------------


def make_app(asset: str = "subd_cube") -> Application:
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset), symmetry_overlay_type=GLSymmetryOverlay)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(*MISS)
    app.viewport.sync()
    return app


def screen(app: Application, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def click(app: Application, x: float, y: float, inp: Input = LMB) -> bool:
    app.pointer_press(inp, x, y)
    return app.pointer_release(inp.value, x, y)


def first_visible(app: Application, ids):
    mesh = app.scene.mesh
    for vid in sorted(ids, key=int):
        sx, sy = screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=app.display.show_faces) == vid:
            return vid
    raise AssertionError("no visible vertex")


def side_vertices(app: Application, side: int) -> list:
    sides = topology_report(app.scene.mesh).sides
    return sorted((v for v, s in sides.vertex_side.items() if s == side), key=int)


def seam_vertices(app: Application) -> list:
    return sorted(topology_report(app.scene.mesh).sides.seam_vertices, key=int)


def select(app: Application, vid) -> None:
    click(app, *screen(app, vid))
    assert app.selection.vertices == {vid}, (vid, app.selection.vertices)


def select_on_side(app: Application, side: int):
    vid = first_visible(app, side_vertices(app, side))
    select(app, vid)
    return vid


def symmetry_to(app: Application, axis) -> None:
    for _ in range(4):
        if current_axis(app.scene.mesh) == axis:
            return
        assert app.key_press(SHIFT_S)
    assert current_axis(app.scene.mesh) == axis


def open_preview(asset: str = "man_with_shoes_basemesh", side: int = 0):
    app = make_app(asset)
    symmetry_to(app, "X")
    source = select_on_side(app, side)
    assert app.key_press(ALT_M) is True
    assert app.resymmetrize_preview is not None
    return app, source


def state_snapshot(app: Application) -> tuple:
    """Model, selection, history and constraint - what the preview never changes."""
    selection = app.selection
    return (
        selection.mode,
        frozenset(selection.vertices),
        frozenset(selection.edges),
        frozenset(selection.faces),
        len(app.history),
        app.history.can_undo(),
        app.history.can_redo(),
        app.scene.mesh.export_state(),
        app.axis_constraint,
    )


def hint(app: Application) -> str:
    return f"{RESYM_PREVIEW_HINT} | {plan_summary(app.resymmetrize_preview, 'Alt+M')}"


@pytest.fixture
def previewing():
    """man_with_shoes, symmetry X (partial, 54 without partner), a vertex on side 0 clicked, the key
    → preview with 27 moves (Lab README slice 5, steps 1-4)."""
    app, source = open_preview("man_with_shoes_basemesh", side=0)
    assert len(app.resymmetrize_preview.moves) == 27
    return app, source


@pytest.fixture
def cube_preview():
    """subd_cube, symmetry X, a vertex on side 0, preview open (0 changes)."""
    return open_preview("subd_cube", side=0)


# -- key and wiring -------------------------------------------------------------------------------


def test_default_key_is_alt_m_and_m_stays_free():
    """`PROVISIONAL` (AD-013 A5): bare M is the Morph Lab bridge in `src/main.py` (window level)."""
    bindings = Application().bindings
    assert bindings.command_for(ALT_M) == commands.RESYMMETRIZE
    assert bindings.command_for(_key("m")) is None


def test_open_sets_the_owner_pauses_the_hover_and_posts_the_summary(previewing):
    app, _source = previewing
    assert app.interaction_owner == "resymmetrize"
    assert app.selection.hovered is None
    assert app.hover_suspended is False  # the host hook is not used by the app's own preview
    assert len(app.history) == 1  # only the Shift+S
    assert app.status_message == plan_summary(app.resymmetrize_preview, "Alt+M")


def test_plan_is_computed_once_when_opening(previewing, monkeypatch):
    app, _source = previewing
    plan = app.resymmetrize_preview
    monkeypatch.setattr(application_module, "plan_resymmetrize", lambda *a, **k: pytest.fail("recomputed"))
    app.pointer_scroll(WHEEL_UP)
    app.key_press(W)
    assert app.resymmetrize_preview is plan
    assert app.key_press(ALT_M) is True
    assert app.resymmetrize_preview is None


# -- execute from either side (§7) ------------------------------------------------------------------


@pytest.mark.parametrize("source_side", [0, 1])
def test_man_with_shoes_from_either_side_becomes_valid(source_side):
    app = make_app("man_with_shoes_basemesh")
    symmetry_to(app, "X")
    mesh = app.scene.mesh
    assert len(symmetry_report(mesh).unpaired) == 54
    source_before = {v: mesh.vertex_position(v) for v in side_vertices(app, source_side)}
    state_before = mesh.export_state()
    history_before = len(app.history)

    source = select_on_side(app, source_side)
    assert app.key_press(ALT_M) is True and app.resymmetrize_preview is not None
    assert app.key_press(ALT_M) is True and app.resymmetrize_preview is None
    assert app.interaction_owner is None

    report = symmetry_report(mesh)
    assert report.state is SymmetryState.VALID
    assert report.unpaired == frozenset()
    assert len(app.history) == history_before + 1
    assert all(repr(mesh.vertex_position(v)) == repr(p) for v, p in source_before.items())
    partners = topology_report(mesh).pairing.partners
    for vid in side_vertices(app, 1 - source_side):
        if vid in partners:
            assert mesh.vertex_position(vid) == mirror_position(mesh.vertex_position(partners[vid]), *PLANE)

    assert app.key_press(CTRL_Z) is True
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.selection.vertices == {source}


def test_seam_vertex_moved_off_plane_ends_exactly_on_plane():
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    mesh = app.scene.mesh
    seam_vid = seam_vertices(app)[0]
    _x, y, z = mesh.vertex_position(seam_vid)

    def nudge():
        mesh.set_vertex_position(seam_vid, (0.3, y, z))
        return {seam_vid}

    assert app.apply_mesh_change("test: seam off the plane", nudge)
    assert symmetry_state(mesh) is SymmetryState.VIOLATED

    select_on_side(app, 0)
    assert app.key_press(ALT_M) is True
    assert [c.vertex for c in app.resymmetrize_preview.seam_moves] == [seam_vid]
    assert app.resymmetrize_preview.moves == ()
    assert app.key_press(ALT_M) is True
    assert mesh.vertex_position(seam_vid) == (0.0, y, z)
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_execute_is_one_mesh_delta_step_with_the_plan_description(previewing):
    app, source = previewing
    plan = app.resymmetrize_preview
    history = len(app.history)
    assert app.key_press(ALT_M) is True
    assert len(app.history) == history + 1
    assert app.history._undo_stack[-1].description == f"Re-Symmetrize {plan.source_label} → {plan.target_label}"
    for change in plan.changes:
        assert app.scene.mesh.vertex_position(change.vertex) == change.after
    assert app.status_message == "Re-Symmetrize ausgeführt: 27 Änderungen"
    assert app.selection.vertices == {source}
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID


def test_ctrl_z_restores_mesh_and_selection_then_redo(previewing):
    app, source = previewing
    before = app.scene.mesh.export_state()
    assert app.key_press(ALT_M)
    after = app.scene.mesh.export_state()
    select(app, first_visible(app, side_vertices(app, 1)))
    assert app.key_press(CTRL_Z) is True
    assert app.scene.mesh.export_state() == before
    assert app.selection.vertices == {source}
    assert symmetry_state(app.scene.mesh) is SymmetryState.PARTIAL
    assert app.key_press(CTRL_Y) is True
    assert app.scene.mesh.export_state() == after
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID


def test_zero_changes_preview_then_key_creates_no_history_entry(cube_preview):
    app, _source = cube_preview
    assert app.resymmetrize_preview.is_empty
    assert "0 Änderungen" in app.status_message
    state = app.scene.mesh.export_state()
    history = len(app.history)
    assert app.key_press(ALT_M) is True
    assert app.resymmetrize_preview is None
    assert len(app.history) == history
    assert app.scene.mesh.export_state() == state
    assert app.status_message == "Re-Symmetrize: 0 Änderungen — kein Schritt"
    assert app.key_press(CTRL_Z)  # takes back the Shift+S, not Re-Symmetrize
    assert current_axis(app.scene.mesh) is None


def test_esc_leaves_mesh_unchanged_and_no_history(previewing):
    app, _source = previewing
    snapshot = state_snapshot(app)
    assert app.key_press(ESC) is True
    assert app.resymmetrize_preview is None
    assert app.interaction_owner is None
    assert state_snapshot(app) == snapshot
    assert app.status_message == "Re-Symmetrize abgebrochen"


def test_status_line_shows_direction_counts_and_the_bound_key(previewing):
    app, _source = previewing
    plan = app.resymmetrize_preview
    text = app.status_message
    assert f"Quelle {plan.source_label} → Ziel {plan.target_label}" in text
    assert "bewegt 27" in text
    assert "Alt+M = ausführen, ESC = abbrechen" in text


def test_a_rebound_key_executes_and_is_named():
    app = make_app("subd_cube")
    app.bindings.bind(ALT_M, None)
    app.bindings.bind(_key("j"), commands.RESYMMETRIZE)
    symmetry_to(app, "X")
    select_on_side(app, 0)
    assert app.key_press(ALT_M) is False
    assert app.key_press(_key("j")) is True
    assert "J = ausführen" in app.status_message
    assert app.key_press(_key("j")) is True
    assert app.resymmetrize_preview is None


# -- refusals (E15) -----------------------------------------------------------------------------------


def _assert_refused(app: Application, text: str) -> None:
    snapshot = state_snapshot(app)
    serial = app.status_serial
    assert app.key_press(ALT_M) is False
    assert app.resymmetrize_preview is None
    assert app.interaction_owner is None
    assert app.status_serial == serial + 1
    assert app.status_message == text
    assert state_snapshot(app) == snapshot


def test_rejected_when_symmetry_off():
    app = make_app("subd_cube")
    select(app, first_visible(app, app.scene.mesh.all_vertex_ids()))
    _assert_refused(app, "Re-Symmetrize: Symmetrie aus")


def test_rejected_without_selection():
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    _assert_refused(app, "Re-Symmetrize: keine Auswahl")


def test_rejected_with_two_selected_vertices():
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    a = first_visible(app, side_vertices(app, 0))
    b = first_visible(app, [v for v in side_vertices(app, 0) if v != a])
    select(app, a)
    click(app, *screen(app, b), SHIFT_LMB)
    assert app.selection.vertices == {a, b}
    _assert_refused(app, "Re-Symmetrize: genau einen Vertex auswählen")


def test_rejected_for_seam_vertex():
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    select(app, first_visible(app, seam_vertices(app)))
    _assert_refused(app, "Re-Symmetrize: Seam-Vertex gewählt — Quellseite unklar")


def test_rejected_without_seam_edges():
    """subd_cube on Y has 0 seam edges (Slice 3): nothing to walk from. Until A3 this read "Seam
    teilt das Mesh in 1 Teile"; the early refusal skips the topology walk (gollum: 0.8 s)."""
    app = make_app("subd_cube")
    symmetry_to(app, "Y")
    select(app, first_visible(app, app.scene.mesh.all_vertex_ids()))
    _assert_refused(app, "Re-Symmetrize: keine Seam auf der Ebene — nichts zu spiegeln")


def test_rejected_when_seam_does_not_split_into_two():
    """A seam with a gap: the mesh stays one component (Lab README, Slice 5 finding)."""
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    mesh = app.scene.mesh
    definition = mesh.symmetry_definition
    keep = frozenset(sorted(definition.seam_edges)[:-1])
    mesh.symmetry_definition = type(definition)(definition.plane_point, definition.plane_normal, keep)
    select_on_side(app, 0)
    _assert_refused(app, "Re-Symmetrize: Seam teilt das Mesh in 1 Teile (nötig: genau 2)")


def test_rejected_in_object_mode():
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    assert app.key_press(_key("4"))
    serial = app.status_serial
    assert app.key_press(ALT_M) is False
    assert app.status_serial == serial + 1
    assert "Alt+M" in app.status_message
    assert app.resymmetrize_preview is None


def test_face_mode_has_no_vertex_selection():
    """N5 of the Lab: in Face mode there is no vertex selection, so the key refuses like the old
    dispatcher (`selection.vertices`)."""
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    assert app.key_press(THREE)
    _assert_refused(app, "Re-Symmetrize: keine Auswahl")


@pytest.mark.parametrize("running", [False, True], ids=["armed", "running"])
def test_ignored_while_move_armed_or_dragging(running):
    """Like Shift+S (AD-SYM-04 R-4): silently ignored while W/E/R is held - the preview does not open."""
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    select_on_side(app, 0)
    assert app.key_press(W)
    if running:
        app.pointer_motion(400, 300, 8.0, 2.0)
        assert app.transform_interacting
    assert app.key_press(ALT_M) is False
    assert app.resymmetrize_preview is None
    assert app.interaction_owner == "transform"
    assert app.key_press(ESC)
    assert app.transform_command is None


def test_ignored_during_a_knife_session():
    app = make_app("subd_cube")
    app.pointer_motion(*MISS)
    assert app.key_press(C) and app.knife_active
    assert app.key_press(ALT_M) is False
    assert app.resymmetrize_preview is None
    assert app.key_press(ESC)


# -- the preview owns the keys, clicks and the hover -----------------------------------------------


def test_navigation_allowed_during_preview(previewing):
    app, source = previewing
    camera = app.camera
    before = (camera.yaw, camera.pitch, camera.distance, tuple(camera.target))
    x, y = screen(app, source)
    app.pointer_press(ALT_LMB, x, y)
    app.pointer_drag(20, 10, x + 20, y + 10)
    app.pointer_release("LEFT", x + 20, y + 10)
    app.pointer_scroll(WHEEL_UP)
    assert (camera.yaw, camera.pitch, camera.distance, tuple(camera.target)) != before
    assert app.resymmetrize_preview is not None


def test_click_pressed_before_the_key_does_not_select_during_preview():
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    source = select_on_side(app, 0)
    other = first_visible(app, side_vertices(app, 1))
    x, y = screen(app, other)
    app.pointer_press(LMB, x, y)
    assert app.key_press(ALT_M) and app.resymmetrize_preview is not None
    assert app.pointer_release("LEFT", x, y) is False
    assert app.selection.vertices == {source}
    assert app.status_message == hint(app)


@pytest.mark.parametrize("inp", [SHIFT_S, W, CTRL_Z, CTRL_Y], ids=["shift_s", "w", "ctrl_z", "ctrl_y"])
def test_other_keys_are_ignored_during_preview(previewing, inp):
    app, _source = previewing
    snapshot = state_snapshot(app)
    plan = app.resymmetrize_preview
    assert app.key_press(inp) is False
    app.key_release(inp)
    assert app.resymmetrize_preview is plan
    assert app.status_message == hint(app)
    assert app.transform_command is None
    assert state_snapshot(app) == snapshot


def test_select_is_ignored_during_preview(previewing):
    app, _source = previewing
    snapshot = state_snapshot(app)
    other = first_visible(app, side_vertices(app, 1))
    assert click(app, *screen(app, other)) is False
    assert state_snapshot(app) == snapshot
    assert app.status_message == hint(app)
    assert app.resymmetrize_preview is not None


REFUSED_KEYS = [W, E, R, C, CTRL_Z, CTRL_Y, ONE, TWO, THREE, X, SHIFT_X, ALT_A, SHIFT_S]


@pytest.mark.parametrize("inp", REFUSED_KEYS, ids=lambda i: "+".join(sorted(i.modifiers) + [i.value]))
def test_refused_keys_post_the_hint_visibly(cube_preview, inp):
    """T-R3 of the Lab's preview row: False, `status_serial` + 1, the hint; twice → +2."""
    app, _source = cube_preview
    snapshot = state_snapshot(app)
    serial = app.status_serial
    for n in (1, 2):
        assert app.key_press(inp) is False
        assert app.status_serial == serial + n
        assert app.status_message == hint(app)
        app.key_release(inp)
    assert state_snapshot(app) == snapshot
    assert app.interaction_owner == "resymmetrize"


@pytest.mark.parametrize("inp", [LMB, SHIFT_LMB], ids=["select", "select_add"])
def test_refused_clicks_post_the_hint_visibly(cube_preview, inp):
    app, _source = cube_preview
    other = first_visible(app, side_vertices(app, 1))
    snapshot = state_snapshot(app)
    serial = app.status_serial
    for n in (1, 2):
        assert click(app, *screen(app, other), inp) is False
        assert app.status_serial == serial + n
        assert app.status_message == hint(app)
    assert state_snapshot(app) == snapshot


def test_soft_steps_drag_selection_and_tweak_do_nothing(cube_preview):
    app, source = cube_preview
    snapshot = state_snapshot(app)
    soft = app.soft_settings
    assert app.pointer_scroll(SHIFT_WHEEL_UP) is False
    assert app.soft_settings == soft
    x, y = screen(app, source)
    for inp in (LMB, CTRL_LMB):
        app.pointer_press(inp, x, y)
        app.pointer_drag(40, 25, x + 40, y + 25)
        app.pointer_drag(40, 25, x + 80, y + 50)
        app.pointer_release("LEFT", x + 80, y + 50)
        assert app.selection_box is None and app.transform_command is None
    assert state_snapshot(app) == snapshot
    assert app.resymmetrize_preview is not None


@pytest.mark.parametrize("inp", [D, SHIFT_D], ids=["d", "shift_d"])
def test_display_commands_pass_the_preview(previewing, inp):
    app, _source = previewing
    display = (app.display.mode, app.display.show_edges)
    assert app.key_press(inp) is True
    assert (app.display.mode, app.display.show_edges) != display
    assert app.resymmetrize_preview is not None


def test_ctrl_z_and_w_refused_mid_orbit_then_esc_keeps_the_orbit():
    """T-R2c of the Lab (F1): preview open with a non-empty history, an orbit running; Ctrl+Z and W are
    refused; Esc closes the preview mid-orbit and the orbit continues."""
    app = make_app("man_with_shoes_basemesh")
    symmetry_to(app, "X")
    source = select_on_side(app, 0)
    assert app.key_press(W)
    app.pointer_motion(400, 300, 6.0, 3.0)
    assert app.key_release(W)
    assert len(app.history) == 2
    assert app.key_press(ALT_M) and app.resymmetrize_preview is not None

    x, y = screen(app, source)
    app.pointer_press(ALT_LMB, x, y)
    app.pointer_drag(10, 0, x + 10, y)
    assert app.pointer.active
    snapshot = state_snapshot(app)
    assert app.key_press(CTRL_Z) is False
    assert state_snapshot(app) == snapshot
    assert app.key_press(W) is False
    assert app.transform_command is None

    assert app.key_press(ESC) is True
    assert app.resymmetrize_preview is None and app.pointer.active
    yaw = app.camera.yaw
    app.pointer_drag(10, 0, x + 20, y)
    assert app.camera.yaw != yaw
    app.pointer_release("LEFT", x + 20, y)
    assert state_snapshot(app) == snapshot


def test_shift_s_then_w_then_esc_leaves_no_armed_move(previewing):
    """N2 regression of the Lab: Shift+S and W are refused under the preview; Esc closes only it."""
    app, _source = previewing
    assert app.key_press(SHIFT_S) is False
    assert current_axis(app.scene.mesh) == "X"
    assert app.key_press(W) is False
    assert app.key_press(ESC) is True
    assert app.resymmetrize_preview is None
    assert app.transform_command is None
    app.key_release(W)
    assert app.transform_command is None
    assert app.interaction_owner is None


def test_hover_paused_while_open_and_repicked_after(cube_preview):
    app, _source = cube_preview
    target = first_visible(app, side_vertices(app, 1))
    app.pointer_motion(*screen(app, target))
    assert app.selection.hovered is None
    app.pointer_scroll(WHEEL_UP)  # a zoom re-picks, but not under the preview
    assert app.selection.hovered is None
    app.pointer_motion(*screen(app, target))
    assert app.selection.hovered is None
    assert app.key_press(ESC)
    assert app.selection.hovered == target


def test_hover_comes_back_after_execute(cube_preview):
    app, _source = cube_preview
    target = first_visible(app, side_vertices(app, 1))
    app.pointer_motion(*screen(app, target))
    assert app.selection.hovered is None
    assert app.key_press(ALT_M)  # empty plan: no transaction, the close re-picks
    assert app.selection.hovered == target
    assert isinstance(app.selection.hovered, VertexId)


def test_host_entries_refuse_while_open(previewing, tmp_path):
    """Everything that refuses "while the <owner> interaction runs" names the preview (save, object
    adds); `apply_mesh_change` raises before anything changes (D3)."""
    app, _source = previewing
    snapshot = state_snapshot(app)
    assert app.save_scene_file(tmp_path / "x.mirai.json") is False
    assert app.status_message == "Save scene: not while the resymmetrize interaction runs"
    assert app.add_primitive("cube") is None
    with pytest.raises(RuntimeError, match="resymmetrize"):
        app.apply_mesh_change("x", lambda: set())
    assert state_snapshot(app) == snapshot
    assert app.selection.mode is SelectionMode.VERTEX


def test_paired_state_unaffected_by_preview(previewing):
    app, _source = previewing
    display = app.symmetry_display
    app.viewport.sync()
    assert len(display.report.unpaired) == 54


# -- overlay ----------------------------------------------------------------------------------------


def _sink(app: Application) -> GLSymmetryOverlay:
    return app.symmetry_display.sink


def test_preview_layers_present_while_open_and_empty_after_execute(previewing):
    app, _source = previewing
    plan = app.resymmetrize_preview
    sink = _sink(app)
    assert app.symmetry_display.dirty
    app.viewport.sync()
    moves = [c.before for c in plan.moves]
    assert sink.points(sink_module.RESYM_MOVE_LAYER) == moves
    assert sink.segments(sink_module.RESYM_MOVE_LINE_LAYER) == [(c.before, c.after) for c in plan.moves]
    assert sink.points(sink_module.RESYM_SEAM_LAYER) == [c.before for c in plan.seam_moves]
    assert len(sink.points(sink_module.RESYM_KEEP_LAYER)) == len(plan.unmatched)
    assert app.key_press(ALT_M)
    app.viewport.sync()
    for layer in sink_module.PREVIEW_POINT_LAYERS:
        assert sink.points(layer) == []
    for layer in sink_module.PREVIEW_LINE_LAYERS:
        assert sink.segments(layer) == []


def test_preview_layers_empty_after_esc(previewing):
    app, _source = previewing
    app.viewport.sync()
    assert _sink(app).points(sink_module.RESYM_MOVE_LAYER)
    assert app.key_press(ESC)
    app.viewport.sync()
    assert _sink(app).points(sink_module.RESYM_MOVE_LAYER) == []


def test_load_scene_closes_nothing_left_open():
    app, _source = open_preview("subd_cube")
    app.load_scene("obj", obj_path=asset_path("subd_cube"), symmetry_overlay_type=GLSymmetryOverlay)
    assert app.resymmetrize_preview is None
    assert app.interaction_owner is None


# -- T-R2g: random input under the preview ----------------------------------------------------------


def _bound_keys(app: Application) -> list:
    """Every key the default bindings resolve in GLOBAL, without the Re-Symmetrize key and Esc."""
    keys = {
        inp
        for (_ctx, inp) in app.bindings._defaults
        if inp.kind == "key" and app.bindings.command_for(inp) not in (None, commands.RESYMMETRIZE, commands.CANCEL)
    }
    return sorted(keys, key=lambda i: (i.value, sorted(i.modifiers)))


UNBOUND_KEYS = [_key("q"), _key("b"), _key("enter"), _key("z", "ctrl", "shift"), _key("m")]
MODIFIERS = [(), ("shift",), ("ctrl",), ("alt",), ("alt", "shift")]
BUTTONS = ["LEFT", "LEFT", "LEFT", "RIGHT", "MIDDLE"]


def _random_event(rng, app: Application, keys: list, held: set) -> None:
    targets = [screen(app, v) for v in sorted(app.scene.mesh.all_vertex_ids(), key=int)]
    r = rng.random()
    if r < 0.35:
        inp = rng.choice(keys)
        app.key_press(inp)
        held.add(inp)
    elif r < 0.45 and held:
        inp = rng.choice(sorted(held, key=lambda i: (i.value, sorted(i.modifiers))))
        held.discard(inp)
        app.key_release(inp)
    elif r < 0.58:
        x, y = rng.choice(targets) if rng.random() < 0.7 else (rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
        app.pointer_press(Input("mouse", rng.choice(BUTTONS), frozenset(rng.choice(MODIFIERS))), x, y)
    elif r < 0.68:
        d = rng.choice([1, 2, 10, 30])
        app.pointer_drag(rng.choice([-d, d]), rng.choice([-d, 0, d]), rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
    elif r < 0.78:
        app.pointer_release(rng.choice(["LEFT", "RIGHT", "MIDDLE"]), rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
    elif r < 0.92:
        x, y = rng.choice(targets) if rng.random() < 0.6 else (rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT))
        app.pointer_motion(x, y, rng.uniform(-8, 8), rng.uniform(-8, 8))
    elif r < 0.97:
        app.pointer_scroll(Input("wheel", rng.choice(["UP", "DOWN"]), frozenset(rng.choice(MODIFIERS[:3]))))
    else:
        app.pointer_leave()


@pytest.mark.parametrize("seed", range(12))
def test_random_input_under_the_preview_changes_nothing(seed):
    rng = random.Random(seed)
    app = make_app("subd_cube")
    symmetry_to(app, "X")
    if seed % 2:
        app.key_press(X)  # a constraint before the key may stay (only read)
    source = first_visible(app, side_vertices(app, rng.randint(0, 1)))
    click(app, *screen(app, source))
    assert app.key_press(ALT_M) is True
    plan = app.resymmetrize_preview
    before = state_snapshot(app)
    keys = _bound_keys(app) + UNBOUND_KEYS
    held: set = set()
    for step in range(300):
        _random_event(rng, app, keys, held)
        where = f"seed {seed}, event {step}"
        assert app.resymmetrize_preview is plan, where
        assert app.interaction_owner == "resymmetrize", where
        assert app.tool_manager.active_tool is None, where
        assert app.selection.hovered is None, where
        assert app.selection_box is None and app.selection_lasso is None, where
        assert state_snapshot(app) == before, where
    for inp in held:
        app.key_release(inp)
    while app.pointer.active:
        app.pointer_release(app.pointer.active_button, 0, 0)
    assert app.key_press(ESC) is True
    assert app.resymmetrize_preview is None
    assert state_snapshot(app) == before
