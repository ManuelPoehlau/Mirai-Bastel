"""Symmetrisches Rotate/Scale im Lab (WP-SYM-LAB-02 S2), headless über den Dispatcher.

Der Lab-Behelf-Pivot aus S1 ist entfernt: der Pivot (Auswahl ∪ Partner) kommt vom Tool.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

from symmetry_lab.lab_bindings import apply_lab_bindings
from symmetry_lab.lab_dispatch import GateMode, LabDispatcher, MoveState
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_status import status_text
from symmetry_lab.lab_symmetry import AXIS_NORMALS, ORIGIN, symmetry_report

W, H = 1280, 800
KEY_E = Input("key", "e")
KEY_R = Input("key", "r")
KEY_X = Input("key", "x")
KEY_Y = Input("key", "y")
KEY_Z = Input("key", "z")
ESC = Input("key", "ESCAPE")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
DRAGS = [(40, 2), (30, -3), (20, 7)]


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
    d.take_changes()
    return d


def vertex_in_state(app, state):
    corr = vertex_correspondence(app.scene.mesh)
    return min(v for v, c in corr.items() if c.state is state)


def paired(app):
    vid = vertex_in_state(app, CorrespondenceState.PAIRED)
    return vid, vertex_correspondence(app.scene.mesh)[vid].partner


def same_side_pair(app, vid):
    """Ein zweiter gepaarter Vertex auf derselben Seite wie `vid` und sein Partner.
    Rotate/Scale brauchen seit dem Pivot pro Seite (Artist-Verdikt 2026-10-03) eine
    Gruppe: ein einzelner Vertex dreht/skaliert um sich selbst."""
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    side = mesh.vertex_position(vid)[0] > 0
    for w in sorted(mesh.all_vertex_ids(), key=int):
        c = corr[w]
        if w != vid and c.state is CorrespondenceState.PAIRED and (mesh.vertex_position(w)[0] > 0) == side:
            return w, c.partner
    raise AssertionError("kein zweiter gepaarter Vertex auf derselben Seite")


def move_mouse(d):
    x, y = 640.0, 400.0
    for dx, dy in DRAGS:
        x, y = x + dx, y + dy
        d.motion(x, y, dx, dy)


def mirrored_ok(app, vid, partner):
    mesh = app.scene.mesh
    return mesh.vertex_position(partner) == mirror_position(
        mesh.vertex_position(vid), ORIGIN, AXIS_NORMALS["X"]
    )


@pytest.mark.parametrize("key,label", [(KEY_E, "Rotate"), (KEY_R, "Scale")])
def test_single_vertex_runs_symmetric_one_undo_step(app, dispatcher, key, label):
    """Seit dem Pivot pro Seite (2026-10-03) mit einer einseitigen Zwei-Vertex-Gruppe."""
    mesh = app.scene.mesh
    vid, partner = paired(app)
    other, other_partner = same_side_pair(app, vid)
    app.scene.selection.set({vid, other})
    state0, before = mesh.export_state(), len(app.history)
    p0 = mesh.vertex_position(vid)

    assert dispatcher.key(key) is True
    assert dispatcher.message.startswith(f"{label} scharf")  # kein Gate, keine Warnung
    assert dispatcher.one_sided_active is False
    move_mouse(dispatcher)
    assert dispatcher.move_state is MoveState.DRAGGING
    dispatcher.key_release(key)

    assert mesh.vertex_position(vid) != p0
    assert mirrored_ok(app, vid, partner)
    assert mirrored_ok(app, other, other_partner)
    assert vertex_correspondence(mesh)[vid].partner == partner  # Paar bleibt PAIRED
    assert dispatcher.message == f"{label} übernommen"
    assert len(app.history) == before + 1
    dispatcher.key(CTRL_Z)
    assert mesh.export_state() == state0
    assert len(app.history) == before


@pytest.mark.parametrize("key", [KEY_E, KEY_R])
def test_cancel_leaves_no_history(app, dispatcher, key):
    mesh = app.scene.mesh
    vid, _ = paired(app)
    app.scene.selection.set({vid})
    state0, before = mesh.export_state(), len(app.history)
    dispatcher.key(key)
    move_mouse(dispatcher)
    dispatcher.key(ESC)
    assert mesh.export_state() == state0
    assert len(app.history) == before


def test_constraint_keys_toggle_and_show_in_status(app, dispatcher):
    assert dispatcher.axis_constraint is None
    dispatcher.key(KEY_X)
    assert dispatcher.axis_constraint == "x"
    assert "Constraint: X" in status_text(
        app, "subd_cube", dispatcher, symmetry_report(app.scene.mesh)
    )
    dispatcher.key(KEY_Y)
    assert dispatcher.axis_constraint == "y"
    dispatcher.key(KEY_Y)
    assert dispatcher.axis_constraint is None


def test_constraints_x_y_z_all_keep_the_pair_mirrored(app, dispatcher):
    vid, partner = paired(app)
    for key in (KEY_X, KEY_Y, KEY_Z):
        dispatcher.key(key)
        app.scene.selection.set({vid})
        dispatcher.key(KEY_E)
        move_mouse(dispatcher)
        dispatcher.key_release(KEY_E)
        assert mirrored_ok(app, vid, partner)
        dispatcher.key(key)  # Constraint wieder frei


def _hold(dispatcher, key):
    dispatcher.key(key)
    move_mouse(dispatcher)
    dispatcher.key_release(key)


def test_seam_vertex_rotate_x_allowed(app, dispatcher):
    # Ein einzelner Seam-Vertex ist sein eigener Pivot: erlaubt, aber nichts zu bewegen.
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    app.scene.selection.set({seam})
    dispatcher.key(KEY_X)
    _hold(dispatcher, KEY_E)
    assert "abgelehnt" not in dispatcher.message
    assert mesh.vertex_position(seam)[0] == 0.0


@pytest.mark.parametrize("constraint_key", [KEY_Y, KEY_Z, None])
def test_seam_vertex_rotate_other_axes_refused_with_message(app, dispatcher, constraint_key):
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    app.scene.selection.set({seam})
    if constraint_key is not None:  # None: Constraint frei = Bildachse (nicht ∥ Normale)
        dispatcher.key(constraint_key)
    state, before = mesh.export_state(), len(app.history)
    dispatcher.key(KEY_E)
    move_mouse(dispatcher)
    assert dispatcher.move_state is MoveState.READY  # nie scharf geblieben
    assert "Rotate: abgelehnt" in dispatcher.message and "Seam" in dispatcher.message
    assert mesh.export_state() == state and len(app.history) == before
    dispatcher.key_release(KEY_E)
    assert mesh.export_state() == state


def test_seam_vertex_scale_allowed_and_on_plane(app, dispatcher):
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    app.scene.selection.set({seam})
    _hold(dispatcher, KEY_R)
    assert "abgelehnt" not in dispatcher.message
    assert mesh.vertex_position(seam)[0] == 0.0


def test_move_and_gate_unchanged(app, dispatcher):
    KEY_W = Input("key", "w")
    vid, partner = paired(app)
    app.scene.selection.set({vid})
    dispatcher.key(KEY_X)  # Constraint beeinflusst Move im Lab nicht
    dispatcher.key(KEY_W)
    move_mouse(dispatcher)
    assert app.tool_manager.active_tool.moves == {vid, partner}
    dispatcher.key_release(KEY_W)
    assert mirrored_ok(app, vid, partner)
    assert dispatcher.gate_mode is GateMode.MARK  # Gate-Code bleibt, E5-Verdikt offen
