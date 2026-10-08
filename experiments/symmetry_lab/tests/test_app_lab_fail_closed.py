"""Fail-closed BLOCK-Zeile, Kontext-Ablehnung über das Lab, MARK-Warnung aus den Deklarationen
(AD-SYM-03 Slice 3a; AD-013, Addendum „2026-10-08, H2-Amendment G-2").

Headless über `lab_key_press` und die öffentlichen Einstiege von `Application`. Die echte
Deklarationstabelle (`mirai.symmetry_declarations`) ist in 3a leer; wo ein deklarierter
Kontext oder Befehl gebraucht wird, patcht `declare` sie (Slice 3b trägt die ersten echten ein).

Benannte Tests des Amendments (die IDs stehen in den Testnamen):

- T-FC1  fail-closed: jeder Befehl außerhalb von `NON_OPERATION`, Deklarationen, Interim,
         Transform-Allow-List wird sichtbar abgelehnt (inkl. der sechs unverdrahteten)
- T-FC2  jeder `NON_OPERATION`-Befehl verhält sich wie bei Symmetrie aus
- T-FC3  die Zeile ist eine Funktion der Deklarationen (und der `supports_symmetry`-Flags)
- T-FC4  `C` über das Lab: deklarierter Kontext läuft, undeklarierter wird benannt abgelehnt,
         dasselbe Gate-Objekt vor und nach jedem Druck (keine Zeile pro Taste)
- T-FC5  MARK: die Knife-Warnzeile steht genau, solange KNIFE undeklariert ist
- T-R1d+ die Start-Liste nennt `refused_contexts`, `NON_OPERATION`, `INTERIM_ONE_SIDED`
- T-R2h+ die installierte Zeile samt `refused_contexts` folgt Undo/Redo

T-R4a+ steht in `test_app_lab_boundary.py`. Zusätzlich: das Interim (Delete/Dissolve laufen
einseitig unter Symmetrie + BLOCK) und seine Sichtbarkeit.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from core import RotateOperation, SelectionMode
from mirai import symmetry_declarations as declarations
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.topology.contextual_c import CContext

from symmetry_lab.lab_app import (
    BLOCK_NOT_ALLOWED_TEXT,
    CONTEXT_NAMES,
    INTERIM_ONE_SIDED,
    KNIFE_ONE_SIDED_TEXT,
    NON_OPERATION,
    ROW_MARK,
    TRANSFORM_OPERATIONS,
    GateMode,
    block_row,
    block_text,
    e5_warning_text,
    gate_row_for,
    gate_rows,
    startup_listing,
)
from symmetry_lab.lab_symmetry import current_axis

from ._app_lab_support import (  # noqa: F401
    C,
    CTRL_Y,
    CTRL_Z,
    ESC,
    HEIGHT,
    MISS,
    SHIFT_B,
    SHIFT_S,
    WIDTH,
    W,
    click,
    forbid_lab_calls,
    make_lab,
    press,
    screen,
    visible,
)

LMB = Input("mouse", "LEFT")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
CTRL_LMB = Input("mouse", "LEFT", frozenset({"ctrl"}))
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
ENTER = Input("key", "enter")
USER_KEY = Input("key", "f12")


def command_constants() -> frozenset[str]:
    return frozenset(
        value for name, value in vars(cmd).items() if name.isupper() and isinstance(value, str)
    )


def declare(monkeypatch, contexts=(), removal=()) -> None:
    """Patcht die (in 3a leere) Deklarationstabelle; `declared_*` lesen bei jedem Aufruf."""
    monkeypatch.setattr(
        declarations,
        "C_CONTEXT_COORDINATORS",
        MappingProxyType({ctx: object() for ctx in contexts}),
    )
    monkeypatch.setattr(
        declarations,
        "REMOVAL_COORDINATORS",
        MappingProxyType({command: object() for command in removal}),
    )


def symmetric_lab():
    """subd_cube, Symmetrie X über Shift+S, E5-Modus BLOCK (Default)."""
    app, lab = make_lab()
    assert lab.gate_mode is GateMode.BLOCK
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    return app, lab


def snapshot(app) -> tuple:
    s = app.selection
    return (
        app.scene.mesh.export_state(),
        len(app.history),
        s.mode,
        frozenset(s.vertices),
        frozenset(s.edges),
        frozenset(s.faces),
    )


# -- Auswahl-Helfer für C-Kontexte (Vertex/Edge-IDs direkt, nur +X-Seite) ----------------------


def _plus_x_quad(app):
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > 1e-9 for v in vids):
            return vids
    raise AssertionError("keine Quad-Face ganz auf der +X-Seite")


def _edge_between(app, a, b):
    mesh = app.scene.mesh
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def select_context(app, ctx: CContext) -> None:
    """Eine einseitige Auswahl (kein Spiegelpaar), die wörtlich zu `ctx` auflöst."""
    a, b, c, d = _plus_x_quad(app)
    s = app.selection
    s.clear()
    app.pointer_motion(*MISS)
    if ctx is CContext.SPLIT:
        s.mode = SelectionMode.EDGE
        s.edges = {_edge_between(app, a, b)}
    elif ctx is CContext.EDGE_CONNECT:
        s.mode = SelectionMode.EDGE
        s.edges = {_edge_between(app, a, b), _edge_between(app, c, d)}
    elif ctx is CContext.VERTEX_CONNECT:
        s.mode = SelectionMode.VERTEX
        s.vertices = {a, c}
    elif ctx is CContext.NONE:
        s.mode = SelectionMode.VERTEX
        s.vertices = {a}
    else:
        s.mode = SelectionMode.VERTEX


# == T-FC1 =======================================================================================


def refused_by_the_row() -> list[str]:
    """Jeder Befehl, den die BLOCK-Zeile bei heutigen (leeren) Deklarationen ablehnen muss."""
    spared = (
        NON_OPERATION
        | INTERIM_ONE_SIDED
        | declarations.declared_removal_commands()
        | frozenset(TRANSFORM_OPERATIONS)
    )
    return sorted(command_constants() - spared)


def test_t_fc1_the_refused_set_contains_the_six_unwired_commands():
    refused = set(refused_by_the_row())
    six = {
        cmd.SPLIT_EDGE,
        cmd.COLLAPSE,
        cmd.LOOP_INSERT,
        cmd.LOOP_SLIDE,
        cmd.EXTRUDE,
        cmd.ARTICULATION_RESTORE,
    }
    assert six <= refused
    assert {cmd.EDGE_LOOP, cmd.EDGE_RING, cmd.CONNECT} <= refused  # bewusst nicht in NON_OPERATION
    assert not refused & NON_OPERATION
    assert not refused & INTERIM_ONE_SIDED


@pytest.mark.parametrize("command", refused_by_the_row())
def test_t_fc1_unlisted_commands_are_refused_visibly_under_block(command):
    """Symmetrie an, BLOCK: ein per User-Binding auf GLOBAL gelegter Befehl außerhalb von
    NON_OPERATION/Deklarationen/Interim → `lab_key_press` False, Status gepostet
    (`status_serial` + 1), Mesh, History und Auswahl unverändert, Gate dasselbe Objekt."""
    app, lab = symmetric_lab()
    assert app.bindings.command_for(USER_KEY) is None
    app.bindings.bind(USER_KEY, command)
    before = snapshot(app)
    gate = app.command_gate
    serial = app.status_serial
    expected = block_text("C") if command == cmd.CONNECT else BLOCK_NOT_ALLOWED_TEXT
    assert press(app, lab, USER_KEY) is False
    assert app.status_serial == serial + 1
    assert app.status_message == expected
    assert snapshot(app) == before
    assert app.command_gate is gate
    assert app.interaction_owner is None


@pytest.mark.parametrize("command", refused_by_the_row())
def test_t_fc1_the_same_commands_are_silent_without_symmetry(command):
    """Gegenprobe: mit Symmetrie aus gibt es keine Ablehnung (die Zeile ist `None`)."""
    app, lab = make_lab()
    app.bindings.bind(USER_KEY, command)
    press(app, lab, USER_KEY)
    assert app.command_gate is None
    assert app.status_message not in (BLOCK_NOT_ALLOWED_TEXT, block_text("C"))


# == T-FC2 =======================================================================================


def _script(app, lab):
    """Ein Ablauf über jede Gruppe von NON_OPERATION; liefert pro Schritt (Rückgabe, Status)."""
    v0, v1 = visible(app)[:2]
    p0, p1 = screen(app, v0), screen(app, v1)
    app.set_status("")  # die Meldung von Shift+S gehört nicht zum Ablauf
    log = []

    def step(label, fn):
        result = fn()
        s = app.selection
        log.append((label, bool(result), app.status_message, s.mode, frozenset(s.vertices)))

    step("Select", lambda: click(app, *p0, LMB))
    step("SelectAdd", lambda: click(app, *p1, SHIFT_LMB))
    step("SelectRemove", lambda: click(app, *p0, CTRL_LMB))
    step("SelectToggle", lambda: click(app, *p0, ALT_LMB))
    step("Move arm", lambda: press(app, lab, W))
    step("Move step", lambda: app.pointer_motion(400, 300, 12.0, 7.0))
    step("Move commit", lambda: app.key_release(W))
    step("Undo", lambda: press(app, lab, CTRL_Z))
    step("Redo", lambda: press(app, lab, CTRL_Y))
    step("Select again", lambda: click(app, *p0, LMB))
    step("Move arm 2", lambda: press(app, lab, W))
    step("Cancel", lambda: press(app, lab, ESC))
    for label, key in (
        ("SetEdgeMode", "2"),
        ("SetFaceMode", "3"),
        ("SetVertexMode", "1"),
        ("AxisX", "x"),
        ("AxisY", "y"),
        ("AxisZ", "z"),
    ):
        step(label, lambda key=key: press(app, lab, Input("key", key)))
    for label, key in (("PlaneYZ", "x"), ("PlaneXZ", "y"), ("PlaneXY", "z"), ("Display", "d"), ("Wireframe", "d")):
        step(label, lambda key=key: press(app, lab, Input("key", key, frozenset({"shift"}))))
    step("ClearSelection", lambda: press(app, lab, Input("key", "a", frozenset({"alt"}))))
    step("Display", lambda: press(app, lab, Input("key", "d")))
    return log


def test_t_fc2_non_operation_commands_behave_as_with_symmetry_off():
    off_app, off_lab = make_lab()
    on_app, on_lab = symmetric_lab()
    off_log = _script(off_app, off_lab)
    on_log = _script(on_app, on_lab)
    assert on_log == off_log
    refusals = {BLOCK_NOT_ALLOWED_TEXT, block_text("C")}
    assert not any(entry[2] in refusals for entry in on_log)
    assert on_app.command_gate == block_row().gate  # die Zeile blieb die ganze Zeit installiert


# == Interim =====================================================================================


@pytest.mark.parametrize(
    "key",
    [Input("key", "delete"), Input("key", "backspace"), Input("key", "backspace", frozenset({"ctrl"}))],
    ids=["delete", "dissolve", "dissolve_no_cleanup"],
)
def test_interim_removal_commands_still_run_one_sided_under_block(key):
    """Akzeptiertes Interim (Manu, 2026-10-06): Delete/Dissolve/DissolveNoCleanup laufen unter
    Symmetrie + BLOCK weiter, bis Slice 3b ihre Koordinatoren bringt — nicht abgelehnt."""
    app, lab = symmetric_lab()
    assert INTERIM_ONE_SIDED == {cmd.DELETE, cmd.DISSOLVE, cmd.DISSOLVE_NO_CLEANUP}
    gate = block_row().gate
    assert all(gate.refusal(command) is None for command in INTERIM_ONE_SIDED)
    a, b, c, d = _plus_x_quad(app)
    app.selection.clear()
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = {_edge_between(app, a, b)}
    serial = app.status_serial
    press(app, lab, key)
    assert app.status_message not in (BLOCK_NOT_ALLOWED_TEXT, block_text("C"))
    assert app.status_serial > serial  # die App hat geantwortet (Ergebnis oder eigener Hinweis)


# == T-FC3 =======================================================================================


def test_t_fc3_row_with_no_declarations():
    gate = block_row().gate
    assert dict(gate.refused) == {cmd.CONNECT: block_text("C")}
    assert gate.allowed == NON_OPERATION | INTERIM_ONE_SIDED | frozenset(TRANSFORM_OPERATIONS)
    assert cmd.CONNECT not in gate.allowed
    assert gate.not_allowed_text == BLOCK_NOT_ALLOWED_TEXT
    assert dict(gate.refused_contexts) == {
        CContext.SPLIT: block_text("Split"),
        CContext.EDGE_CONNECT: block_text("Edge Connect"),
        CContext.VERTEX_CONNECT: block_text("Vertex Connect"),
        CContext.KNIFE: block_text("Knife"),
    }
    assert CContext.NONE not in gate.refused_contexts
    assert set(CONTEXT_NAMES) == set(gate.refused_contexts)


def test_t_fc3_row_follows_the_declarations(monkeypatch):
    base = block_row()
    assert base == block_row()  # gleiche Deklarationen → gleiche (`==`) Zeile

    declare(monkeypatch, contexts=[CContext.EDGE_CONNECT, CContext.VERTEX_CONNECT])
    row = block_row()
    assert row != base
    gate = row.gate
    assert dict(gate.refused) == {}  # ein C-Kontext ist deklariert → Connect geht durch
    assert cmd.CONNECT in gate.allowed
    assert dict(gate.refused_contexts) == {
        CContext.SPLIT: block_text("Split"),
        CContext.KNIFE: block_text("Knife"),
    }
    assert row == block_row()

    declare(monkeypatch, contexts=list(CONTEXT_NAMES))
    assert dict(block_row().gate.refused_contexts) == {}

    declare(monkeypatch, contexts=[], removal=[cmd.COLLAPSE])  # Stellvertreter für einen deklarierten Befehl
    assert cmd.COLLAPSE in block_row().gate.allowed
    assert cmd.COLLAPSE not in base.gate.allowed
    assert dict(block_row().gate.refused) == {cmd.CONNECT: block_text("C")}

    declare(monkeypatch)
    assert block_row() == base


def test_t_fc3_row_follows_the_supports_symmetry_flags(monkeypatch):
    monkeypatch.setattr(RotateOperation, "supports_symmetry", False)
    gate = block_row().gate
    assert gate.refused[cmd.ROTATE] == block_text("Rotate")
    assert cmd.ROTATE not in gate.allowed
    assert cmd.MOVE in gate.allowed and cmd.SCALE in gate.allowed


def test_t_fc3_the_row_partitions_every_command(monkeypatch):
    """Jeder Befehl ist durch die Zeile entweder durchgelassen oder abgelehnt, nie beides
    offen; abgelehnt genau das Komplement der Allow-List plus die benannten."""
    declare(monkeypatch, contexts=[CContext.EDGE_CONNECT])
    gate = block_row().gate
    for command in command_constants():
        text = gate.refusal(command)
        if command in gate.allowed and command not in gate.refused:
            assert text is None, command
        else:
            assert text in (BLOCK_NOT_ALLOWED_TEXT, *gate.refused.values()), command


def test_t_fc3_other_rows_do_not_depend_on_declarations(monkeypatch):
    before = gate_rows()
    declare(monkeypatch, contexts=list(CONTEXT_NAMES), removal=[cmd.DELETE])
    after = gate_rows()
    off, mark, _block, preview = after
    assert (off, mark, preview) == (before[0], before[1], before[3])
    assert off.gate is None and mark.gate is None


# == T-FC4 =======================================================================================


def test_t_fc4_c_runs_on_a_declared_context_and_is_named_on_the_others(monkeypatch):
    """Vertex Connect ist deklariert (Stellvertreter-Deklaration, 3a hat keinen Koordinator): `C`
    geht durchs Gate und läuft wie bisher einseitig. Split, Edge Connect, Knife und die leere
    Auswahl werden mit ihrem Namen abgelehnt. Das Gate-Objekt bleibt vor und nach jedem Druck
    dasselbe (keine Zeile pro Taste)."""
    declare(monkeypatch, contexts=[CContext.VERTEX_CONNECT])
    app, lab = symmetric_lab()
    gate = app.command_gate
    assert gate == block_row().gate and cmd.CONNECT in gate.allowed

    refusals = {
        CContext.SPLIT: block_text("Split"),
        CContext.EDGE_CONNECT: block_text("Edge Connect"),
        CContext.KNIFE: block_text("Knife"),
    }
    for ctx, text in refusals.items():
        select_context(app, ctx)
        before = snapshot(app)
        serial = app.status_serial
        for n in (1, 2):
            assert press(app, lab, C) is False
            assert app.status_serial == serial + n
            assert app.status_message == text
        assert snapshot(app) == before
        assert not app.knife_active
        assert app.command_gate is gate
        assert app.interaction_owner is None

    select_context(app, CContext.NONE)
    assert press(app, lab, C) is False
    assert app.status_message == "C: nothing to do here"  # die eigene Meldung der App bleibt
    assert app.command_gate is gate

    select_context(app, CContext.VERTEX_CONNECT)
    history = len(app.history)
    assert press(app, lab, C) is True
    assert app.status_message == "Vertex Connect"
    assert len(app.history) == history + 1
    assert app.command_gate is gate


def test_t_fc4_declared_knife_starts_a_session_and_the_row_stays(monkeypatch):
    declare(monkeypatch, contexts=[CContext.KNIFE])
    app, lab = symmetric_lab()
    gate = app.command_gate
    select_context(app, CContext.KNIFE)
    assert press(app, lab, C) is True
    assert app.knife_active
    assert app.command_gate is gate  # `sync_gate` überspringt während der Session
    assert press(app, lab, ESC) is True
    assert not app.knife_active
    assert app.command_gate is gate


def test_t_fc4_without_declarations_c_is_refused_by_identity_as_before():
    app, lab = symmetric_lab()
    select_context(app, CContext.KNIFE)
    serial = app.status_serial
    assert press(app, lab, C) is False
    assert (app.status_serial, app.status_message) == (serial + 1, block_text("C"))
    assert not app.knife_active


def test_t_fc4_a_mirror_edge_pair_is_one_intent_under_mark_and_named_under_block():
    """Die angekündigte MARK-Folge der Kanonisierung (Amendment § Proposal 1, Review-Probe P5):
    Kante plus Spiegelkante ist ein einseitiger Split der einen Kante (statt „Keine verbindbaren
    Kanten"); unter BLOCK ist dasselbe `C` per Identität abgelehnt, die Auswahl bleibt zweiseitig."""
    app, lab = symmetric_lab()
    mesh = app.scene.mesh
    a, b, _c, _d = _plus_x_quad(app)
    edge = _edge_between(app, a, b)
    from mirai.symmetry_coordination import build_index  # nur Test, nicht Lab-Code

    partner = build_index(mesh).edge_partner(edge)
    assert partner is not None and partner != edge
    app.selection.clear()
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = {edge, partner}

    before = snapshot(app)
    assert press(app, lab, C) is False  # BLOCK, nichts deklariert: Identität
    assert app.status_message == block_text("C")
    assert snapshot(app) == before

    assert press(app, lab, SHIFT_B)  # MARK
    vertices = len(mesh.all_vertex_ids())
    assert press(app, lab, C) is True
    assert app.status_message == "Split"
    assert len(mesh.all_vertex_ids()) == vertices + 1  # eine Kante, einseitig
    (new_vertex,) = app.selection.vertices
    assert mesh.vertex_position(new_vertex)[0] > 0.0


# == T-FC5 =======================================================================================


def _mark_lab():
    app, lab = make_lab()
    assert press(app, lab, SHIFT_B) and lab.gate_mode is GateMode.MARK
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    return app, lab


def test_t_fc5_knife_warning_only_while_knife_is_undeclared(monkeypatch):
    app, lab = _mark_lab()
    assert app.command_gate is ROW_MARK.gate is None  # MARK-Zeile bleibt None
    select_context(app, CContext.KNIFE)
    assert press(app, lab, C) is True and app.knife_active
    assert e5_warning_text(lab) == KNIFE_ONE_SIDED_TEXT
    declare(monkeypatch, contexts=[CContext.KNIFE])
    assert e5_warning_text(lab) == ""  # dieselbe Quelle wie die BLOCK-Zeile
    declare(monkeypatch, contexts=[CContext.SPLIT, CContext.EDGE_CONNECT, CContext.VERTEX_CONNECT])
    assert e5_warning_text(lab) == KNIFE_ONE_SIDED_TEXT  # andere Kontexte ändern daran nichts
    declare(monkeypatch)
    assert press(app, lab, ESC) is True
    assert e5_warning_text(lab) == ""
    assert app.command_gate is None


def test_t_fc5_declared_knife_session_has_no_warning_line_in_mark(monkeypatch):
    declare(monkeypatch, contexts=[CContext.KNIFE])
    app, lab = _mark_lab()
    select_context(app, CContext.KNIFE)
    assert press(app, lab, C) is True and app.knife_active
    assert e5_warning_text(lab) == ""
    assert app.command_gate is None


def test_t_fc5_immediate_undeclared_operations_get_no_warning_line():
    """Ein sofortiger undeklarierter Kontext (Split) ist keine laufende Interaktion."""
    app, lab = _mark_lab()
    select_context(app, CContext.SPLIT)
    assert press(app, lab, C) is True
    assert e5_warning_text(lab) == ""


# == T-R1d+ ======================================================================================


def test_t_r1d_plus_listing_has_contexts_non_operation_and_interim(monkeypatch):
    lines = startup_listing()
    text = "\n".join(lines)
    for row in gate_rows():
        assert row.describe() in text
    for context, refusal in block_row().gate.refused_contexts.items():
        assert CONTEXT_NAMES[context] in block_row().describe()
        assert repr(refusal) in text
    assert "C-Kontext Split abgelehnt" in text
    assert "C-Kontext Knife abgelehnt" in text

    non_operation = next(line for line in lines if line.startswith("NON_OPERATION"))
    for command in NON_OPERATION:
        assert command in non_operation
    assert cmd.EDGE_LOOP not in non_operation and cmd.EDGE_RING not in non_operation
    interim = next(line for line in lines if line.startswith("INTERIM_ONE_SIDED"))
    assert "accepted interim, Manu 2026-10-06; removed in slice 3b" in interim
    for command in INTERIM_ONE_SIDED:
        assert command in interim
    declarations_line = next(line for line in lines if line.startswith("Deklarationen"))
    assert "C-Kontexte keine" in declarations_line and "Removal keine" in declarations_line

    declare(monkeypatch, contexts=[CContext.EDGE_CONNECT])
    patched = "\n".join(startup_listing())
    assert "C-Kontext Edge Connect abgelehnt" not in patched  # die Liste folgt den Deklarationen
    assert "C-Kontexte Edge Connect" in patched


# == T-R2h+ ======================================================================================


def test_t_r2h_plus_installed_row_incl_contexts_follows_undo_redo(monkeypatch):
    declare(monkeypatch, contexts=[CContext.EDGE_CONNECT])
    app, lab = make_lab()
    assert lab.gate_mode is GateMode.BLOCK

    def check(expected_axis) -> None:
        assert lab.axis == expected_axis == current_axis(app.scene.mesh)
        row = gate_row_for(expected_axis, lab.gate_mode)
        assert app.command_gate == row.gate
        if expected_axis is None:
            assert app.command_gate is None
        else:
            assert dict(app.command_gate.refused_contexts) == {
                CContext.SPLIT: block_text("Split"),
                CContext.VERTEX_CONNECT: block_text("Vertex Connect"),
                CContext.KNIFE: block_text("Knife"),
            }

    check(None)
    axes = [None]
    for _ in range(4):  # X, Y, Z, aus
        assert press(app, lab, SHIFT_S)
        axes.append(lab.axis)
        check(lab.axis)
    assert axes == [None, "X", "Y", "Z", None]
    for expected in reversed(axes[:-1]):
        assert press(app, lab, CTRL_Z) is True
        check(expected)
    for expected in axes[1:]:
        assert press(app, lab, CTRL_Y) is True
        check(expected)
