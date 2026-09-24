"""Hover-Ziel für Move + Ziel-Regel (Handoff Slice 4 §2 A3/A4/E7/E8/E9, §7).

Echte Production-`Application`, -`OrbitCamera` und `pick_nearest_vertex`,
`subd_cube` mit X-Symmetrie; kein GL-Kontext.
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
Q = Input("key", "q")
ESC = Input("key", "ESCAPE")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
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


def screen_pos(app, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), W, H)


def hover_on(dispatcher, app, vid):
    x, y = screen_pos(app, vid)
    dispatcher.motion(x, y)
    assert dispatcher.hover_vertex == vid


def paired_vertices(app):
    """Alle Vertex-IDs im Zustand PAIRED, aufsteigend sortiert."""
    corr = vertex_correspondence(app.scene.mesh)
    return sorted(
        (v for v, c in corr.items() if c.state is CorrespondenceState.PAIRED), key=int
    )


def paired_vertex(app):
    corr = vertex_correspondence(app.scene.mesh)
    vid = paired_vertices(app)[0]
    return vid, corr[vid].partner


def drag_move(dispatcher, drags=DRAGS):
    dispatcher.press(LMB)
    for dx, dy in drags:
        dispatcher.drag(dx, dy)


# -- Ziel-Regel (A4) ------------------------------------------------------------


def test_selection_wins_over_hover(app, dispatcher):
    mesh = app.scene.mesh
    sel_vid, sel_partner = paired_vertex(app)
    corr = vertex_correspondence(mesh)
    hover_vid = next(
        v
        for v in paired_vertices(app)
        if v not in (sel_vid, sel_partner) and corr[v].partner not in (sel_vid, sel_partner)
    )
    app.scene.selection.set({sel_vid})
    hover_on(dispatcher, app, hover_vid)

    assert dispatcher.key(Q) is True
    assert dispatcher.move_target_label == "Auswahl"
    drag_move(dispatcher)
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {sel_vid, sel_partner}
    dispatcher.release("LEFT", 0, 0)
    assert app.scene.selection.vertices == {sel_vid}


def test_hover_target_moves_when_selection_empty(app, dispatcher):
    mesh = app.scene.mesh
    vid, partner = paired_vertex(app)
    assert app.scene.selection.is_empty()
    hover_on(dispatcher, app, vid)
    history_before = len(app.history)
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)

    assert dispatcher.key(Q) is True
    assert dispatcher.move_target_label == f"Hover v{int(vid)}"
    drag_move(dispatcher)
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    dispatcher.release("LEFT", 0, 0)

    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and q1 != q0
    assert mirror_position(p1, ORIGIN, AXIS_NORMALS["X"]) == q1
    assert len(app.history) == history_before + 1
    # E8: das Hover-Ziel berührt scene.selection nicht — vorher und nachher leer.
    assert app.scene.selection.is_empty()
    assert dispatcher.move_state is MoveState.READY


def test_q_rejected_when_selection_and_hover_both_empty(app, dispatcher):
    assert app.scene.selection.is_empty()
    assert dispatcher.hover_vertex is None
    assert dispatcher.key(Q) is True
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    assert dispatcher.move_target_label is None
    assert "kein Hover" in dispatcher.message


# -- E7: Ziel wird bei Q festgelegt und bleibt fest ------------------------------


def test_target_fixed_at_q_press_later_hover_change_does_not_retarget(app, dispatcher):
    mesh = app.scene.mesh
    vid, partner = paired_vertex(app)
    other_vid = next(v for v in paired_vertices(app) if v not in (vid, partner))

    hover_on(dispatcher, app, vid)
    assert dispatcher.key(Q) is True
    assert dispatcher.move_target_label == f"Hover v{int(vid)}"

    hover_on(dispatcher, app, other_vid)  # Maus bewegt sich vor dem LMB-Press
    assert dispatcher.move_target_label == f"Hover v{int(vid)}"  # unverändert (E7)

    other_before = mesh.vertex_position(other_vid)
    drag_move(dispatcher)
    tool = app.tool_manager.active_tool
    assert tool.moves == {vid, partner}  # nicht other_vid
    dispatcher.release("LEFT", 0, 0)
    assert mesh.vertex_position(other_vid) == other_before  # unbewegt


# -- Cancel mit Hover-Ziel --------------------------------------------------------


def test_esc_during_drag_with_hover_target_restores_exactly(app, dispatcher):
    mesh = app.scene.mesh
    vid, _partner = paired_vertex(app)
    hover_on(dispatcher, app, vid)
    state_before = mesh.export_state()
    history_before = len(app.history)

    dispatcher.key(Q)
    drag_move(dispatcher)
    assert mesh.export_state() != state_before
    assert dispatcher.key(ESC) is True

    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.scene.selection.is_empty()
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None


# -- Hover-Update nur im Leerlauf / bei scharfem Move (E9) ------------------------


def test_hover_does_not_update_during_camera_drag(app, dispatcher):
    mesh = app.scene.mesh
    vid, _ = paired_vertex(app)
    other_vid = next(v for v in mesh.all_vertex_ids() if v != vid)
    hover_on(dispatcher, app, vid)

    dispatcher.press(ALT_LMB)
    ox, oy = screen_pos(app, other_vid)
    dispatcher.motion(ox, oy)
    assert dispatcher.hover_vertex == vid  # während Orbit-Drag unverändert
    dispatcher.drag(5, 5)
    dispatcher.motion(ox, oy)
    assert dispatcher.hover_vertex == vid
    dispatcher.release("LEFT", 0, 0)

    dispatcher.motion(ox, oy)
    assert dispatcher.hover_vertex == other_vid  # nach Release wieder aktiv


def test_hover_does_not_update_during_move_drag(app, dispatcher):
    mesh = app.scene.mesh
    vid, partner = paired_vertex(app)
    other_vid = next(v for v in mesh.all_vertex_ids() if v not in (vid, partner))
    app.scene.selection.set({vid})
    hover_on(dispatcher, app, partner)

    dispatcher.key(Q)
    drag_move(dispatcher, drags=[(3, 3)])
    assert dispatcher.move_state is MoveState.DRAGGING

    ox, oy = screen_pos(app, other_vid)
    dispatcher.motion(ox, oy)
    assert dispatcher.hover_vertex == partner  # unverändert während des Move-Drags

    dispatcher.release("LEFT", 0, 0)
    dispatcher.motion(ox, oy)
    assert dispatcher.hover_vertex == other_vid  # nach Release wieder aktiv


def test_hover_marks_change_only_when_vertex_id_changes(app, dispatcher):
    mesh = app.scene.mesh
    vid = min(mesh.all_vertex_ids())
    x, y = screen_pos(app, vid)
    dispatcher.motion(x, y)
    assert Change.HOVER in dispatcher.take_changes()
    dispatcher.motion(x, y)
    assert Change.HOVER not in dispatcher.take_changes()


# -- Statuszeile (Scope §4.2) -----------------------------------------------------


def test_status_shows_move_target_label():
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, "subd_cube")
    d = LabDispatcher(app, W, H)
    vid = min(app.scene.mesh.all_vertex_ids())
    x, y = screen_pos(app, vid)
    d.motion(x, y)
    d.key(Q)
    text = status_text(app, "subd_cube", d, symmetry_report(app.scene.mesh))
    assert f"Move: scharf (Hover v{int(vid)})" in text
