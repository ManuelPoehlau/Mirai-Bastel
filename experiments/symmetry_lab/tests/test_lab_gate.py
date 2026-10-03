"""E5-Gate (WP-SYM-LAB-02 S1): Rotate/Scale unter Symmetrie, MARK vs. BLOCK, ohne Fenster.

Pattern wie `test_lab_move.py`. Gelesen wird `supports_symmetry` an der Operation-Klasse
(AD-SYM-02 §2.3); der Monkeypatch-Test belegt, dass keine Tool-Liste dahintersteckt.
"""

from __future__ import annotations

import pytest

from core import MoveOperation, RotateOperation, ScaleOperation
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.symmetry import CorrespondenceState, vertex_correspondence

from symmetry_lab.lab_bindings import apply_lab_bindings
from symmetry_lab.lab_dispatch import GateMode, LabDispatcher, MoveState
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_status import status_text
from symmetry_lab.lab_symmetry import symmetry_report

W, H = 1280, 800
KEY_W = Input("key", "w")
KEY_E = Input("key", "e")
KEY_R = Input("key", "r")
ESC = Input("key", "ESCAPE")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
SHIFT_B = Input("key", "b", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
DRAGS = [(60, 2), (50, -3), (40, 7)]
WARNING = "Symmetrie aktiv — {} spiegelt nicht (läuft einseitig)"


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


def paired(app):
    corr = vertex_correspondence(app.scene.mesh)
    vid = min(v for v, c in corr.items() if c.state is CorrespondenceState.PAIRED)
    return vid, corr[vid].partner


def move_mouse(d):
    x, y = 640.0, 400.0
    for dx, dy in DRAGS:
        x, y = x + dx, y + dy
        d.motion(x, y, dx, dy)


def symmetry_off(d):
    d.key(SHIFT_S)
    d.key(SHIFT_S)
    d.key(SHIFT_S)
    assert d.app.scene.mesh.symmetry_definition is None


def run(app, d, key, vid):
    app.scene.selection.set({vid})
    assert d.key(key) is True
    move_mouse(d)
    return d.key_release(key)


# -- Symmetrie aus: wie Production --------------------------------------------


@pytest.mark.parametrize("key,label", [(KEY_E, "Rotate"), (KEY_R, "Scale")])
def test_symmetry_off_commit_cancel_and_tap(app, dispatcher, key, label):
    symmetry_off(dispatcher)
    mesh = app.scene.mesh
    ids = sorted(mesh.all_vertex_ids(), key=int)[:3]
    app.scene.selection.set(set(ids))
    before = len(app.history)
    state0 = mesh.export_state()

    assert dispatcher.key(key) is True
    assert dispatcher.move_state is MoveState.ARMED
    assert dispatcher.message == f"{label} scharf — Maus bewegen, {key.value.upper()} loslassen übernimmt"
    move_mouse(dispatcher)
    assert dispatcher.move_state is MoveState.DRAGGING
    assert dispatcher.key_release(key) is True
    assert dispatcher.message == f"{label} übernommen"
    assert mesh.export_state() != state0
    assert len(app.history) == before + 1
    dispatcher.key(CTRL_Z)
    assert mesh.export_state() == state0
    assert len(app.history) == before

    app.scene.selection.set(set(ids))  # Undo leert die Auswahl
    dispatcher.key(key)  # Abbruch
    move_mouse(dispatcher)
    dispatcher.key(ESC)
    assert mesh.export_state() == state0
    assert len(app.history) == before
    assert dispatcher.message == f"{label} abgebrochen"

    app.scene.selection.set(set(ids))
    dispatcher.key(key)  # Antippen
    dispatcher.key_release(key)
    assert dispatcher.message == f"{label}: nur angetippt — nichts bewegt"
    assert len(app.history) == before


def test_symmetry_off_no_target_rejected(app, dispatcher):
    symmetry_off(dispatcher)
    app.scene.selection.clear()
    dispatcher.key(KEY_E)
    assert dispatcher.move_state is MoveState.READY
    assert "Rotate: keine Auswahl" in dispatcher.message


# -- MARK -----------------------------------------------------------------------


@pytest.mark.parametrize("key,label", [(KEY_E, "Rotate"), (KEY_R, "Scale")])
def test_mark_runs_one_sided_with_message_and_one_undo_step(app, dispatcher, key, label):
    mesh = app.scene.mesh
    vid, partner = paired(app)
    others = sorted((v for v in mesh.all_vertex_ids() if v not in (vid, partner)), key=int)[:2]
    app.scene.selection.set({vid, *others})
    before = len(app.history)
    state0 = mesh.export_state()
    q0 = mesh.vertex_position(partner)
    p0 = mesh.vertex_position(vid)

    dispatcher.key(key)
    move_mouse(dispatcher)
    assert dispatcher.move_state is MoveState.DRAGGING
    assert dispatcher.message == WARNING.format(label)
    text = status_text(app, "subd_cube", dispatcher, symmetry_report(mesh))
    assert WARNING.format(label) in text and "E5: MARK" in text
    dispatcher.key_release(key)

    assert mesh.vertex_position(vid) != p0
    assert mesh.vertex_position(partner) == q0
    assert dispatcher.message.endswith("(einseitig)")
    assert len(app.history) == before + 1
    dispatcher.key(CTRL_Z)
    assert mesh.export_state() == state0
    assert len(app.history) == before


def test_mark_hides_partner_marker_only_while_armed(app, dispatcher):
    vid, _ = paired(app)
    app.scene.selection.set({vid})
    assert dispatcher.one_sided_active is False
    dispatcher.key(KEY_E)
    assert dispatcher.one_sided_active is True
    dispatcher.key(ESC)
    assert dispatcher.one_sided_active is False


# -- BLOCK ----------------------------------------------------------------------


@pytest.mark.parametrize("key,label", [(KEY_E, "Rotate"), (KEY_R, "Scale")])
def test_block_refuses_to_arm_and_leaves_no_history(app, dispatcher, key, label):
    dispatcher.key(SHIFT_B)
    assert dispatcher.gate_mode is GateMode.BLOCK
    mesh = app.scene.mesh
    vid, _ = paired(app)
    app.scene.selection.set({vid})
    before = len(app.history)
    state0 = mesh.export_state()

    assert dispatcher.key(key) is True
    assert dispatcher.move_state is MoveState.READY
    assert app.tool_manager.active_tool is None
    assert dispatcher.message.startswith(f"Symmetrie aktiv — {label} spiegelt nicht")
    move_mouse(dispatcher)
    dispatcher.key_release(key)
    assert mesh.export_state() == state0
    assert len(app.history) == before
    assert "E5: BLOCK" in status_text(app, "subd_cube", dispatcher, symmetry_report(mesh))


def test_block_does_not_apply_with_symmetry_off(app, dispatcher):
    symmetry_off(dispatcher)
    dispatcher.key(SHIFT_B)
    app.scene.selection.set({min(app.scene.mesh.all_vertex_ids())})
    dispatcher.key(KEY_E)
    assert dispatcher.move_state is MoveState.ARMED
    dispatcher.key(ESC)


# -- Unverändert: Move, Modus-Schalter -------------------------------------------


@pytest.mark.parametrize("mode_presses", [0, 1])
def test_move_unchanged_in_both_modes(app, dispatcher, mode_presses):
    for _ in range(mode_presses):
        dispatcher.key(SHIFT_B)
    mesh = app.scene.mesh
    vid, partner = paired(app)
    app.scene.selection.set({vid})
    before = len(app.history)
    dispatcher.key(KEY_W)
    assert dispatcher.message.startswith("Move scharf")
    assert dispatcher.one_sided_active is False
    move_mouse(dispatcher)
    assert app.tool_manager.active_tool.moves == {vid, partner}
    dispatcher.key_release(KEY_W)
    assert len(app.history) == before + 1


def test_mode_switch_is_lab_state_only(app, dispatcher):
    mesh = app.scene.mesh
    vid, _ = paired(app)
    app.scene.selection.set({vid})
    run_ok = run(app, dispatcher, KEY_W, vid)
    assert run_ok
    history, state = len(app.history), mesh.export_state()
    assert dispatcher.gate_mode is GateMode.MARK
    dispatcher.key(SHIFT_B)
    assert dispatcher.gate_mode is GateMode.BLOCK
    assert dispatcher.message == "E5-Modus: BLOCK"
    dispatcher.key(SHIFT_B)
    assert dispatcher.gate_mode is GateMode.MARK
    assert (len(app.history), mesh.export_state()) == (history, state)
    dispatcher.key(CTRL_Z)  # Undo bleibt unbeeinflusst
    assert len(app.history) == history - 1


# -- Klassenattribut, keine Tool-Liste ------------------------------------------


def test_gate_reads_class_attribute(app, dispatcher, monkeypatch):
    assert RotateOperation.supports_symmetry is False and ScaleOperation.supports_symmetry is False
    assert MoveOperation.supports_symmetry is True
    mesh = app.scene.mesh
    vid, partner = paired(app)
    app.scene.selection.set({vid})

    # Rotate gilt als unterstützend → kein Gate, keine Warnung.
    monkeypatch.setattr(RotateOperation, "supports_symmetry", True)
    dispatcher.key(KEY_E)
    assert dispatcher.message.startswith("Rotate scharf")
    assert dispatcher.one_sided_active is False
    dispatcher.key(ESC)

    # Move gilt als nicht unterstützend → Gate greift, BLOCK verweigert W.
    monkeypatch.setattr(MoveOperation, "supports_symmetry", False)
    dispatcher.key(SHIFT_B)
    dispatcher.key(KEY_W)
    assert dispatcher.move_state is MoveState.READY
    assert dispatcher.message.startswith("Symmetrie aktiv — Move spiegelt nicht")
