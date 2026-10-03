"""Der Lab-Fenster-Schritt `lab_key_press` gegen die echte `Application`.

AD-013 H2 addendum, § Required tests, Lab-Seite (Slice 1b, ohne Vorschau):
T-R2a, T-R2b, T-R2f, T-R2h, T-R3 (Zeilen von 1b), T-R4c über den Lab-Pfad.
Alles headless über `lab_key_press` und die öffentlichen Einstiege von
`Application`; T-R4b (`forbid_lab_calls`) ist in jedem Test aktiv.
"""

from __future__ import annotations

import pytest

from mirai.application import CommandGate
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input

from symmetry_lab.lab_app import (
    CONNECT_REFUSED_TEXT,
    ROW_SYMMETRY_ON,
    gate_row_for,
)
from symmetry_lab.lab_symmetry import current_axis

from ._app_lab_support import (  # noqa: F401
    C,
    CTRL_Y,
    CTRL_Z,
    E,
    ESC,
    M,
    MISS,
    SHIFT_B,
    SHIFT_S,
    W,
    arm_and_move,
    click,
    forbid_lab_calls,
    lab_app,
    press,
    screen,
    start_knife,
    visible,
)


X = Input("key", "x")


def _gate_matches_mesh(app) -> bool:
    return app.command_gate is gate_row_for(current_axis(app.scene.mesh)).gate


# -- T-R2a ------------------------------------------------------------------------


def test_m_during_armed_and_running_move_is_refused(lab_app):
    """T-R2a: W scharf, M → False, Status gepostet, `transform_command == MOVE`;
    W loslassen committet genau einen History-Eintrag."""
    app, lab = lab_app
    a = visible(app)[0]
    click(app, *screen(app, a))
    assert press(app, lab, W)
    serial = app.status_serial
    assert press(app, lab, M) is False  # nur scharf
    assert app.status_serial == serial + 1
    assert app.status_message == "Re-Symmetrize (M) abgelehnt — Transform läuft"
    assert app.transform_command == cmd.MOVE

    app.pointer_motion(400, 300, 12.0, 7.0)
    assert app.transform_interacting
    assert press(app, lab, M) is False  # läuft
    assert app.status_serial == serial + 2
    assert app.transform_command == cmd.MOVE

    assert app.key_release(W)
    assert len(app.history) == 1
    assert app.transform_command is None


# -- T-R2b ------------------------------------------------------------------------


def test_shift_s_during_knife_is_refused_and_the_session_keeps_running(lab_app):
    """T-R2b: Symmetrie **aus** (die 1b-Zeile würde C ablehnen): C mit leerer
    Auswahl startet den Knife; Shift+S → abgelehnt, `knife_active` bleibt True;
    danach E → Stift angehoben."""
    app, lab = lab_app
    assert lab.axis is None
    start_knife(app, lab)
    a = visible(app)[0]
    click(app, *screen(app, a))
    assert app.knife_render_data.start_point is not None

    serial = app.status_serial
    assert press(app, lab, SHIFT_S) is False
    assert app.status_serial == serial + 1
    assert app.status_message == "Symmetrie (Shift+S) abgelehnt — Knife-Session läuft"
    assert app.knife_active
    assert lab.axis is None
    assert app.command_gate is None

    assert press(app, lab, E)
    assert app.knife_active
    assert app.knife_render_data.start_point is None


# -- T-R2f ------------------------------------------------------------------------


def test_esc_without_preview_still_reaches_application(lab_app):
    """T-R2f: **keine Vorschau**, über `lab_key_press`: W scharf, Esc → entschärft,
    Status `Move disarmed`; Symmetrie aus, C mit leerer Auswahl, Esc → Knife
    beendet. Ein Lab, das Cancel immer abfinge, fiele hier durch."""
    app, lab = lab_app
    a = visible(app)[0]
    click(app, *screen(app, a))
    assert press(app, lab, W)
    assert app.transform_command == cmd.MOVE
    assert press(app, lab, ESC) is True
    assert app.transform_command is None
    assert app.status_message == "Move disarmed"

    start_knife(app, lab)
    assert press(app, lab, ESC) is True
    assert app.knife_active is False


def test_esc_cancels_a_running_move_exactly(lab_app):
    """T-R2f (laufender Move): Esc über den Lab-Pfad stellt exakt wieder her, ohne History."""
    app, lab = lab_app
    a = visible(app)[0]
    click(app, *screen(app, a))
    before = app.scene.mesh.export_state()
    arm_and_move(app, lab)
    assert app.scene.mesh.export_state() != before
    assert press(app, lab, ESC) is True
    assert app.scene.mesh.export_state() == before
    assert len(app.history) == 0


# -- T-R2h ------------------------------------------------------------------------


def _c_refused_exactly_when_on(app, lab) -> None:
    on = lab.axis is not None
    app.pointer_motion(*MISS)
    app.selection.clear()
    history = len(app.history)
    serial = app.status_serial
    result = press(app, lab, C)
    if on:
        assert result is False
        assert app.status_serial == serial + 1
        assert app.status_message == CONNECT_REFUSED_TEXT
        assert not app.knife_active
    else:
        assert result is True
        assert app.knife_active
        assert press(app, lab, ESC) is True  # Session ohne History beenden
        assert not app.knife_active
    assert len(app.history) == history


def test_gate_row_follows_symmetry_definition_over_undo_redo(lab_app):
    """T-R2h: Symmetrie an (C abgelehnt) → Shift+S schaltet durch, aus und wieder
    an → Ctrl+Z/Ctrl+Y über die Zyklus-Schritte → die Gate-Zeile passt nach jedem
    Schritt zu `mesh.symmetry_definition`; C ist genau dann abgelehnt, wenn die
    Symmetrie an ist."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)  # X
    assert app.command_gate is ROW_SYMMETRY_ON.gate
    _c_refused_exactly_when_on(app, lab)

    axes = ["X"]
    for _ in range(5):  # Y, Z, aus, X, Y
        assert press(app, lab, SHIFT_S)
        axes.append(lab.axis)
        assert _gate_matches_mesh(app)
        _c_refused_exactly_when_on(app, lab)
    assert axes == ["X", "Y", "Z", None, "X", "Y"]
    assert len(app.history) == 6

    for expected in reversed([None] + axes[:-1]):
        assert press(app, lab, CTRL_Z) is True
        assert lab.axis == expected
        assert _gate_matches_mesh(app)
        _c_refused_exactly_when_on(app, lab)
    assert not app.history.can_undo()

    for expected in axes:
        assert press(app, lab, CTRL_Y) is True
        assert lab.axis == expected
        assert _gate_matches_mesh(app)
        _c_refused_exactly_when_on(app, lab)


def test_gate_is_not_reinstalled_while_a_transform_owns_the_keys(lab_app):
    """H2-R2: während `interaction_owner` gesetzt ist, schreibt das Lab das Gate
    nicht — auch nicht nach einem weitergeleiteten Tastendruck."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    a = visible(app)[0]
    click(app, *screen(app, a))
    assert press(app, lab, W)
    sentinel = CommandGate()  # lehnt nichts ab; macht nur ein Neuschreiben sichtbar
    app.command_gate = sentinel
    assert press(app, lab, X) is True  # X-Constraint, weitergeleitet
    assert app.command_gate is sentinel
    app.command_gate = ROW_SYMMETRY_ON.gate
    assert press(app, lab, ESC)
    assert _gate_matches_mesh(app)


# -- T-R3 -------------------------------------------------------------------------


def _armed(app, lab):
    a = visible(app)[0]
    click(app, *screen(app, a))
    assert press(app, lab, W)


def _running(app, lab):
    a = visible(app)[0]
    click(app, *screen(app, a))
    arm_and_move(app, lab)


def _symmetry_on(app, lab):
    assert press(app, lab, SHIFT_S)


def _idle(app, lab):
    pass


REFUSALS = [
    ("C_under_symmetry", _symmetry_on, C, CONNECT_REFUSED_TEXT),
    ("ShiftS_transform_armed", _armed, SHIFT_S, "Symmetrie (Shift+S) abgelehnt — Transform läuft"),
    ("ShiftS_transform_running", _running, SHIFT_S, "Symmetrie (Shift+S) abgelehnt — Transform läuft"),
    ("ShiftS_knife", start_knife, SHIFT_S, "Symmetrie (Shift+S) abgelehnt — Knife-Session läuft"),
    # Seit Slice 3 die Ablehnungen des alten Labs (README Slice 5, Schritt 12).
    ("M_idle", _idle, M, "Re-Symmetrize: Symmetrie aus"),
    ("M_symmetry_on", _symmetry_on, M, "Re-Symmetrize: keine Auswahl"),
    ("ShiftB_idle", _idle, SHIFT_B, "E5-Modus (Shift+B): noch nicht verfügbar (Slice 4)"),
    ("ShiftB_knife", start_knife, SHIFT_B, "E5-Modus (Shift+B) abgelehnt — Knife-Session läuft"),
]


@pytest.mark.parametrize(
    "setup,inp,text", [r[1:] for r in REFUSALS], ids=[r[0] for r in REFUSALS]
)
def test_refusals_are_visible_and_counted(lab_app, setup, inp, text):
    """T-R3 (Zeilen von 1b, Tasten — 1b lehnt keinen Klick ab): Rückgabe False,
    `status_serial` + 1, `status_message` = Text der Zeile; zweimal dieselbe
    Ablehnung → zwei Inkremente. Mesh, History, Gate und Owner bleiben."""
    app, lab = lab_app
    setup(app, lab)
    state = app.scene.mesh.export_state()
    history = len(app.history)
    gate = app.command_gate
    owner = app.interaction_owner
    serial = app.status_serial
    for n in (1, 2):
        assert press(app, lab, inp) is False
        assert app.status_serial == serial + n
        assert app.status_message == text
    assert app.scene.mesh.export_state() == state
    assert len(app.history) == history
    assert app.command_gate is gate
    assert app.interaction_owner == owner


# -- T-R4c ------------------------------------------------------------------------


def test_mirror_alignment_through_the_lab_path(lab_app):
    """T-R4c (Probe P3 über den Lab-Pfad): A wählen → W-Move → B wählen → Shift+S
    (Lab-Commit über `apply_mesh_change`) → Ctrl+Z → Auswahl {B}; Ctrl+Z → {A}."""
    app, lab = lab_app
    a, b = visible(app)[:2]
    click(app, *screen(app, a))
    assert app.selection.vertices == {a}
    arm_and_move(app, lab)
    assert app.key_release(W)
    moved_state = app.scene.mesh.export_state()
    click(app, *screen(app, b))
    assert app.selection.vertices == {b}

    assert press(app, lab, SHIFT_S)
    assert lab.axis == "X"
    assert len(app.history) == 2

    assert press(app, lab, CTRL_Z)
    assert app.selection.vertices == {b}
    assert lab.axis is None
    assert app.scene.mesh.export_state() == moved_state
    assert app.command_gate is None

    assert press(app, lab, CTRL_Z)
    assert app.selection.vertices == {a}
    assert not app.history.can_undo()
