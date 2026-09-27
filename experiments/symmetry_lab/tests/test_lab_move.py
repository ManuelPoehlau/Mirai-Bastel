"""Symmetrisches Move über den Dispatcher, ohne Fenster (Handoff Slice 3 §4.2/§4.4/§4.5/§7).

Bedienung seit 2026-09-27 wie die Production-App (WP-06 B3, AD-016
hold-key-hover): W halten + Maus bewegen (keine Maustaste) bewegt live,
Loslassen von W committet, Antippen ohne Bewegung ist ein No-op.

Echte Production-`Application` (`tool_manager`, `MoveTool`, `HistoryStack`)
und -`OrbitCamera`, `subd_cube` mit X-Symmetrie (18 gepaarte + 8
Seam-Vertices); kein GL-Kontext.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.interaction.tools.move import MoveTool
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

from symmetry_lab.lab_bindings import apply_lab_bindings
from symmetry_lab.lab_dispatch import Change, LabDispatcher, MoveState
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_status import status_text
from symmetry_lab.lab_symmetry import AXIS_NORMALS, ORIGIN, current_axis, symmetry_report

W, H = 1280, 800
LMB = Input("mouse", "LEFT")
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
KEY_W = Input("key", "w")
ESC = Input("key", "ESCAPE")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
DRAGS = [(6, 2), (5, -3), (4, 7)]


@pytest.fixture
def app():
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, "subd_cube")
    return app


@pytest.fixture
def dispatcher(app):
    d = LabDispatcher(app, W, H)
    d.key(SHIFT_S)  # aus → X
    assert current_axis(app.scene.mesh) == "X"
    d.take_changes()
    return d


def vertex_in_state(app, state):
    corr = vertex_correspondence(app.scene.mesh)
    return min(v for v, c in corr.items() if c.state is state)


def paired_vertex(app):
    vid = vertex_in_state(app, CorrespondenceState.PAIRED)
    return vid, vertex_correspondence(app.scene.mesh)[vid].partner


def move_mouse(dispatcher, drags=DRAGS, start=(640.0, 400.0)):
    """Mausbewegung ohne gedrückte Taste, während W gehalten wird."""
    x, y = start
    for dx, dy in drags:
        x, y = x + dx, y + dy
        dispatcher.motion(x, y, dx, dy)


# -- Symmetrisches Move --------------------------------------------------------


def test_symmetric_move_one_history_entry_and_exact_undo(app, dispatcher):
    mesh = app.scene.mesh
    vid, partner = paired_vertex(app)
    app.scene.selection.set({vid})
    history_before = len(app.history)
    state_before = mesh.export_state()
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)

    assert dispatcher.key(KEY_W) is True
    assert dispatcher.move_state is MoveState.ARMED
    move_mouse(dispatcher)
    assert dispatcher.move_state is MoveState.DRAGGING
    # MoveTool löst die Symmetrie selbst aus dem Mesh auf (nicht das Lab).
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert dispatcher.key_release(KEY_W) is True

    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and q1 != q0
    assert mirror_position(p1, ORIGIN, AXIS_NORMALS["X"]) == q1
    assert vertex_correspondence(mesh)[vid].partner == partner
    assert len(app.history) == history_before + 1

    dispatcher.key(CTRL_Z)
    assert mesh.vertex_position(vid) == p0
    assert mesh.vertex_position(partner) == q0
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before


def test_move_without_symmetry_moves_only_the_selection(app, dispatcher):
    dispatcher.key(SHIFT_S)
    dispatcher.key(SHIFT_S)
    dispatcher.key(SHIFT_S)  # X → Y → Z → aus
    assert app.scene.mesh.symmetry_definition is None
    vid = min(app.scene.mesh.all_vertex_ids())
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    assert app.tool_manager.active_tool.moves == {vid}
    dispatcher.key_release(KEY_W)


def test_seam_vertex_stays_exactly_on_plane(app, dispatcher):
    mesh = app.scene.mesh
    vid = vertex_in_state(app, CorrespondenceState.SEAM)
    app.scene.selection.set({vid})
    p0 = mesh.vertex_position(vid)
    dispatcher.key(KEY_W)
    move_mouse(dispatcher, DRAGS * 3)
    dispatcher.key_release(KEY_W)
    p1 = mesh.vertex_position(vid)
    assert p1 != p0  # nicht trivial: der Vertex hat sich in der Ebene bewegt
    assert p1[0] == 0.0
    assert symmetry_report(mesh).state.value == "valid"


def test_undo_takes_back_exactly_one_action_each(app, dispatcher):
    # Symmetrie-Schritt (Fixture) + Move → zwei Einträge, je ein Undo pro Handlung.
    mesh = app.scene.mesh
    vid, _partner = paired_vertex(app)
    app.scene.selection.set({vid})
    after_symmetry = mesh.export_state()
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    dispatcher.key_release(KEY_W)
    assert len(app.history) == 2

    dispatcher.key(CTRL_Z)
    assert mesh.export_state() == after_symmetry
    dispatcher.key(CTRL_Z)
    assert mesh.symmetry_definition is None
    assert len(app.history) == 0

    dispatcher.key(CTRL_Y)
    assert mesh.export_state() == after_symmetry


def test_undo_clears_selection_and_disarms(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    assert dispatcher.key(CTRL_Z) is True
    assert app.scene.selection.is_empty()
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    assert Change.MESH in dispatcher.take_changes()


# -- One-shot (E5) und ToolManager-Lifecycle (E6) --------------------------------


def test_after_commit_move_is_disarmed(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    dispatcher.key_release(KEY_W)
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    # Nächster LMB-Klick ist wieder Select, kein Move.
    dispatcher.press(LMB)
    assert dispatcher.active_command == "Select"


def test_tap_without_motion_is_a_noop(app, dispatcher):
    mesh = app.scene.mesh
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    state_before = mesh.export_state()
    history_before = len(app.history)
    dispatcher.key(KEY_W)
    assert dispatcher.key_release(KEY_W) is True
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    assert "angetippt" in dispatcher.message


def test_single_pixel_motion_starts_the_move(app, dispatcher):
    mesh = app.scene.mesh
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    before = mesh.vertex_position(vid)
    dispatcher.key(KEY_W)
    dispatcher.motion(640.0, 400.0, 0, 0)  # Nullschritt zählt nicht
    assert dispatcher.move_state is MoveState.ARMED
    dispatcher.motion(641.0, 400.0, 1, 0)
    assert dispatcher.move_state is MoveState.DRAGGING
    assert mesh.vertex_position(vid) != before


def test_lmb_while_armed_neither_moves_nor_selects(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    dispatcher.press(LMB)
    assert dispatcher.active_command is None
    assert dispatcher.release("LEFT", 0, 0) is False
    assert dispatcher.move_state is MoveState.ARMED
    assert app.scene.selection.vertices == {vid}


def test_release_with_changed_modifiers_still_commits(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    history_before = len(app.history)
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    assert dispatcher.key_release(Input("key", "w", frozenset({"alt"}))) is True
    assert len(app.history) == history_before + 1
    assert dispatcher.move_state is MoveState.READY


def test_release_of_other_key_does_not_commit(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    assert dispatcher.key_release(Input("key", "e")) is False
    assert dispatcher.move_state is MoveState.DRAGGING


def test_second_w_press_while_armed_keeps_target_and_tool(app, dispatcher):
    vid, partner = paired_vertex(app)
    other = next(v for v in app.scene.mesh.all_vertex_ids() if v not in (vid, partner))
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    tool = app.tool_manager.active_tool
    app.scene.selection.set({other})
    assert dispatcher.key(KEY_W) is True  # z. B. Key-Repeat
    assert app.tool_manager.active_tool is tool
    assert dispatcher.move_target_label == "Auswahl"
    move_mouse(dispatcher)
    assert tool.moves == {vid, partner}


def test_q_is_unbound_in_the_lab(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    assert dispatcher.key(Input("key", "q")) is False
    assert dispatcher.move_state is MoveState.READY


def test_w_without_selection_does_not_arm(app, dispatcher):
    assert app.scene.selection.is_empty()
    assert dispatcher.key(KEY_W) is True
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    assert "keine Auswahl" in dispatcher.message


def test_navigation_still_works_while_armed(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    yaw = app.camera.yaw
    dispatcher.press(ALT_LMB)
    assert dispatcher.active_command == "Orbit"
    dispatcher.drag(20, 0)
    dispatcher.release("LEFT", 0, 0)
    assert app.camera.yaw != yaw
    target = app.camera.target
    dispatcher.press(SHIFT_LMB)
    assert dispatcher.active_command == "Pan"
    dispatcher.drag(15, 0)
    dispatcher.release("LEFT", 0, 0)
    assert app.camera.target != target
    assert dispatcher.move_state is MoveState.ARMED
    assert len(app.history) == 1  # nur der Symmetrie-Schritt


def test_camera_gesture_during_move_wins(app, dispatcher):
    mesh = app.scene.mesh
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    live = mesh.export_state()
    target = app.camera.target
    dispatcher.press(Input("mouse", "MIDDLE"))
    assert dispatcher.active_command == "Pan"
    dispatcher.drag(15, 0)
    dispatcher.motion(700.0, 400.0, 15, 0)  # (theoretisch) — bewegt nichts
    dispatcher.release("MIDDLE", 0, 0)
    assert app.camera.target != target
    assert mesh.export_state() == live
    assert dispatcher.move_state is MoveState.DRAGGING
    move_mouse(dispatcher, drags=[(4, 4)])
    assert mesh.export_state() != live
    dispatcher.key_release(KEY_W)
    assert dispatcher.move_state is MoveState.READY


# -- Abbruch (ESC) --------------------------------------------------------------


def test_esc_during_drag_restores_exactly_without_history(app, dispatcher):
    mesh = app.scene.mesh
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    state_before = mesh.export_state()
    history_before = len(app.history)
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    assert mesh.export_state() != state_before
    assert dispatcher.key(ESC) is True
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    # Das spätere Loslassen von W bewirkt nichts mehr.
    assert dispatcher.key_release(KEY_W) is False
    assert mesh.export_state() == state_before


def test_esc_while_only_armed_disarms(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    assert dispatcher.key(ESC) is True
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None


def test_esc_when_idle_is_not_handled(dispatcher):
    assert dispatcher.key(ESC) is False


def test_unrelated_keys_are_not_handled(dispatcher):
    assert dispatcher.key(Input("key", "f")) is False
    assert dispatcher.key(None) is False


# -- Randfälle während des Drags ----------------------------------------------------


@pytest.mark.parametrize("inp", [SHIFT_S, CTRL_Z, CTRL_Y, KEY_W])
def test_keys_during_drag_are_ignored(app, dispatcher, inp):
    mesh = app.scene.mesh
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    definition = mesh.symmetry_definition
    history_len = len(app.history)
    live = mesh.export_state()
    assert dispatcher.key(inp) is True
    assert mesh.symmetry_definition == definition
    assert len(app.history) == history_len
    assert mesh.export_state() == live
    assert dispatcher.move_state is MoveState.DRAGGING
    assert app.scene.selection.vertices == {vid}


# -- Anzeige-Rückmeldung ------------------------------------------------------------


def test_move_drag_marks_mesh_changed(app, dispatcher):
    vid, _ = paired_vertex(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_W)
    dispatcher.take_changes()
    dispatcher.motion(643.0, 403.0, 3, 3)
    assert Change.MESH in dispatcher.take_changes()


def test_status_text_shows_plane_state_unpaired_move_and_selection():
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, "man_with_shoes_basemesh")
    d = LabDispatcher(app, W, H)
    report = symmetry_report(app.scene.mesh)
    assert "Symmetrie: aus (off)" in status_text(app, "man", d, report)
    d.key(SHIFT_S)
    vid = min(app.scene.mesh.all_vertex_ids())
    app.scene.selection.set({vid})
    d.key(KEY_W)
    text = status_text(app, "man", d, symmetry_report(app.scene.mesh))
    assert "Symmetrie: X (partial)" in text
    assert "ohne Partner: 54" in text
    assert "Move: scharf" in text
    assert f"Auswahl: v{int(vid)}" in text
