"""E5-Gate MARK/BLOCK auf dem App-Pfad (WP-SYM-LAB-03 Slice 4), jetzt mit C.

Port der 13 Tests aus `test_lab_gate.py` (altes Lab, in Slice 5 gelöscht) auf
`lab_key_press` und die öffentlichen Einstiege von `Application`, plus die neuen
Fälle des Slice-4-Briefs: Shift+B, C unter MARK (sofortiges C und Knife-Session)
und BLOCK, die Erklärung `supports_symmetry`, Cancel, T-R3 für die BLOCK-Zeile,
Start-Liste. T-R2h über Undo/Redo in BLOCK steht in `test_app_lab_keys.py`.

Vertrag: AD-013, Addendum H2 (Gate-Tabelle, H2-R2: außerhalb der Vorschau lehnt
das Gate nur ab, was eine Interaktion startet oder das Mesh ändert, nie Cancel;
das Lab schreibt nichts, solange `interaction_owner` gesetzt ist). E5 selbst ist
offen (AD-SYM-02 §4) — die Tests belegen nur, dass beide Varianten vergleichbar
sind.

Ein nicht spiegelndes Transform-Tool gibt es heute nicht (W/E/R erklären
`supports_symmetry`). Wie im alten Lab simulieren die Tests es per Monkeypatch
des Klassenattributs (`unsupported`). Das Gate ist ein Lab-Versprechen über
Warnung und Ablehnung: die Bewegung selbst bleibt die des `src`-Tools, das die
Erklärung nicht liest (es spiegelt weiter, sobald eine Definition gesetzt ist).

Abweichung vom alten Lab (Port von `test_mark_hides_partner_marker_only_while_armed`):
das alte Lab blendete während eines einseitigen Transforms den Partner-Marker aus;
auf dem App-Pfad trägt die E5-Warnzeile im HUD die Markierung, die Partner-Marker
bleiben (der Brief verlangt nur die HUD-Zeile).
"""

from __future__ import annotations

import pytest

from core import MoveOperation, RotateOperation, ScaleOperation
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetry import CorrespondenceState, SymmetryState, vertex_correspondence
from mirai.topology.knife_pick import knife_pick

from symmetry_lab.lab_app import (
    KNIFE_ONE_SIDED_TEXT,
    ROW_MARK,
    ROW_PREVIEW,
    ROW_SYMMETRY_OFF,
    GateMode,
    block_row,
    block_text,
    e5_warning_text,
    gate_rows,
    hud_text,
    one_sided_text,
    startup_listing,
)
from symmetry_lab.lab_overlays import UNPAIRED_LAYER

from ._app_lab_support import (  # noqa: F401
    C,
    CTRL_Y,
    CTRL_Z,
    E,
    ESC,
    HEIGHT,
    M,
    MISS,
    SHIFT_B,
    SHIFT_S,
    WIDTH,
    W,
    click,
    forbid_lab_calls,
    lab_app,
    make_lab,
    press,
    screen,
    visible,
)

R = Input("key", "r")
ENTER = Input("key", "enter")
KEY_EDGE_MODE = Input("key", "2")
LMB = Input("mouse", "LEFT")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
DRAGS = [(60, 2), (50, -3), (40, 7)]
LABELS = {E: "Rotate", R: "Scale", W: "Move"}


@pytest.fixture
def unsupported(monkeypatch):
    """Wie `test_lab_gate.unsupported`: Rotate/Scale erklären keine Symmetrie."""
    monkeypatch.setattr(RotateOperation, "supports_symmetry", False)
    monkeypatch.setattr(ScaleOperation, "supports_symmetry", False)


@pytest.fixture
def symmetric():
    """subd_cube, Symmetrie X über Shift+S, E5-Modus MARK über Shift+B (Default ist
    seit Slice 5 BLOCK; die Tests der Ports gehen von MARK aus und schalten selbst
    um, wie in Slice 4)."""
    app, lab = make_lab()
    assert lab.gate_mode is GateMode.BLOCK
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    set_mode(app, lab, GateMode.MARK)
    return app, lab


def paired(app):
    """Ein sichtbarer gepaarter Vertex und sein Partner."""
    corr = vertex_correspondence(app.scene.mesh)
    vid = next(v for v in visible(app) if corr[v].state is CorrespondenceState.PAIRED)
    return vid, corr[vid].partner


def select(app, vid) -> None:
    click(app, *screen(app, vid))
    assert app.selection.vertices == {vid}


def move_mouse(app) -> None:
    x, y = 400.0, 300.0
    for dx, dy in DRAGS:
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, float(dx), float(dy))


def symmetry_off(app, lab) -> None:
    for _ in range(3):
        assert press(app, lab, SHIFT_S)
    assert lab.axis is None


def set_mode(app, lab, mode: GateMode) -> None:
    """E5-Modus über Shift+B (nur drücken, wenn er nicht schon gilt)."""
    if lab.gate_mode is not mode:
        assert press(app, lab, SHIFT_B)
    assert lab.gate_mode is mode


def to_block(app, lab) -> None:
    set_mode(app, lab, GateMode.BLOCK)


def hud(app, lab) -> str:
    return hud_text(app, "subd_cube", lab.report, lab.gate_mode)


def side_edge(app, lab):
    """Eine sichtbare Edge mit beiden Enden auf der +X-Seite (nicht auf der Seam),
    per Klick im Edge-Modus gewählt: ihr Split erzeugt einen Vertex abseits der
    Ebene, dessen Partner-Edge nicht mitgeteilt wird."""
    mesh = app.scene.mesh
    assert press(app, lab, KEY_EDGE_MODE)
    for eid in sorted(mesh.all_edge_ids(), key=int):
        a, b = mesh.edge_vertices(eid)
        pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
        if pa[0] <= 1e-9 or pb[0] <= 1e-9:
            continue
        mid = tuple((p + q) / 2 for p, q in zip(pa, pb))
        click(app, *app.camera.project_to_screen(mid, WIDTH, HEIGHT))
        if app.selection.edges == {eid}:
            return eid
    raise AssertionError("keine anklickbare Edge auf der +X-Seite")


def one_side_diagonal(app):
    """Zwei diagonale Vertices einer Quad-Face ganz auf der +X-Seite, die der
    Knife als Vertex trifft (Klickziele für einen einseitigen Schnitt)."""
    mesh = app.scene.mesh

    def hits(vid) -> bool:
        target = knife_pick(app.camera, mesh, *screen(app, vid), WIDTH, HEIGHT)
        return target.get("kind") == "vertex" and target.get("vertex_id") == vid

    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) != 4 or any(mesh.vertex_position(v)[0] <= 1e-9 for v in vids):
            continue
        if hits(vids[0]) and hits(vids[2]):
            return vids[0], vids[2]
    raise AssertionError("keine einseitige Quad-Face mit sichtbarer Diagonale")


def knife_click(app, vid) -> None:
    pos = screen(app, vid)
    app.pointer_motion(*pos)
    app.pointer_press(LMB, *pos)
    assert app.pointer_release("LEFT", *pos)


def begin_knife(app, lab) -> None:
    """C mit leerer Auswahl über den Lab-Pfad (wie `_app_lab_support.start_knife`)."""
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert press(app, lab, C) is True
    assert app.knife_active


# == Port von test_lab_gate.py (13) ===================================================

# -- Symmetrie aus: wie Production -------------------------------------------------------


@pytest.mark.parametrize("key", [E, R], ids=["rotate", "scale"])
def test_symmetry_off_commit_cancel_and_tap(lab_app, key):
    """Port: ohne Symmetrie laufen E/R wie in der App — Commit (ein Undo-Schritt),
    Esc (exakt zurück, keine History), Antippen (nichts)."""
    app, lab = lab_app
    assert lab.axis is None
    mesh = app.scene.mesh
    ids = visible(app)[:3]  # drei Vertices: um ihren Mittelpunkt ändert E/R etwas
    before = len(app.history)
    state0 = mesh.export_state()

    select(app, ids[0])
    for vid in ids[1:]:
        click(app, *screen(app, vid), SHIFT_LMB)
    assert app.selection.vertices == set(ids)
    assert press(app, lab, key) is True
    assert app.transform_command is not None and not app.transform_interacting
    move_mouse(app)
    assert app.transform_interacting
    assert app.key_release(key) is True
    assert app.status_message.startswith(f"{LABELS[key]} committed")
    assert mesh.export_state() != state0
    assert len(app.history) == before + 1
    assert press(app, lab, CTRL_Z) is True
    assert mesh.export_state() == state0
    assert len(app.history) == before

    assert press(app, lab, key)  # Abbruch (Undo stellt die Auswahl wieder her)
    move_mouse(app)
    assert press(app, lab, ESC) is True
    assert mesh.export_state() == state0
    assert app.transform_command is None
    assert len(app.history) == before

    assert press(app, lab, key)  # Antippen
    assert app.key_release(key) is True
    assert app.status_message.startswith(f"{LABELS[key]}: tool set (no motion")
    assert len(app.history) == before
    assert e5_warning_text(lab) == ""


def test_symmetry_off_no_target_rejected(lab_app):
    """Port: keine Auswahl, kein Hover → die App lehnt E ab (ihr Text)."""
    app, lab = lab_app
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert press(app, lab, E) is False
    assert app.transform_command is None
    assert app.status_message.startswith("Rotate: nothing to rotate")


# -- MARK ---------------------------------------------------------------------------------


@pytest.mark.parametrize("key", [E, R], ids=["rotate", "scale"])
def test_mark_runs_with_the_one_sided_warning_and_one_undo_step(symmetric, unsupported, key):
    """Port: MARK lässt das nicht spiegelnde Tool laufen; die HUD-Warnzeile trägt
    die Meldung des alten Labs, solange es scharf ist oder läuft; die HUD-Zeile
    zeigt `E5: MARK`; ein Undo-Schritt. Kein Status vom Lab während der
    Interaktion (H2-R2): die Statuszeile ist die der App."""
    app, lab = symmetric
    mesh = app.scene.mesh
    vid, _partner = paired(app)
    select(app, vid)
    # Zwei Vertices einer Seite: seit dem Pivot pro Seite (2026-10-03) dreht/skaliert
    # ein einzelner Vertex um sich selbst.
    corr = vertex_correspondence(mesh)
    side = mesh.vertex_position(vid)[0] > 0
    other = next(
        v for v in visible(app)
        if v != vid
        and corr[v].state is CorrespondenceState.PAIRED
        and (mesh.vertex_position(v)[0] > 0) == side
    )
    app.selection.set({vid, other})
    app.viewport.on_selection_changed()
    before = len(app.history)
    state0 = mesh.export_state()
    p0 = mesh.vertex_position(vid)

    assert press(app, lab, key) is True
    assert e5_warning_text(lab) == one_sided_text(LABELS[key])
    app_status = app.status_message
    move_mouse(app)
    assert app.transform_interacting
    assert e5_warning_text(lab) == one_sided_text(LABELS[key])
    assert " | E5: MARK | " in hud(app, lab)
    assert app.status_message == app_status  # das Lab schreibt nichts
    assert app.key_release(key)

    assert e5_warning_text(lab) == ""
    assert mesh.vertex_position(vid) != p0
    assert len(app.history) == before + 1
    assert press(app, lab, CTRL_Z)
    assert mesh.export_state() == state0
    assert len(app.history) == before


def test_mark_warning_only_while_armed(symmetric, unsupported):
    """Port von `test_mark_hides_partner_marker_only_while_armed`: die Warnung gilt
    genau, solange der Transform scharf ist (vorher und nach Esc leer)."""
    app, lab = symmetric
    vid, _ = paired(app)
    select(app, vid)
    assert e5_warning_text(lab) == ""
    assert press(app, lab, E)
    assert e5_warning_text(lab) == one_sided_text("Rotate")
    assert press(app, lab, ESC)
    assert app.transform_command is None
    assert e5_warning_text(lab) == ""


# -- BLOCK --------------------------------------------------------------------------------


@pytest.mark.parametrize("key", [E, R], ids=["rotate", "scale"])
def test_block_refuses_to_arm_and_leaves_no_history(symmetric, unsupported, key):
    """Port: BLOCK lehnt das nicht spiegelnde Tool über das App-Gate ab (Text des
    alten Labs), nichts wird scharf, Maus und Loslassen bewirken nichts."""
    app, lab = symmetric
    to_block(app, lab)
    mesh = app.scene.mesh
    vid, _ = paired(app)
    select(app, vid)
    before = len(app.history)
    state0 = mesh.export_state()
    serial = app.status_serial

    assert press(app, lab, key) is False
    assert app.status_serial == serial + 1
    assert app.status_message == block_text(LABELS[key])
    assert app.status_message.startswith(f"Symmetrie aktiv — {LABELS[key]} spiegelt nicht")
    assert app.transform_command is None and app.interaction_owner is None
    move_mouse(app)
    assert app.key_release(key) is False
    assert mesh.export_state() == state0
    assert len(app.history) == before
    assert " | E5: BLOCK | " in hud(app, lab)


def test_block_does_not_apply_with_symmetry_off(lab_app, unsupported):
    """Port: ohne Symmetrie ist der Modus egal — E wird auch in BLOCK scharf."""
    app, lab = lab_app
    to_block(app, lab)
    assert app.command_gate is None
    select(app, visible(app)[0])
    assert press(app, lab, E) is True
    assert app.transform_command == cmd.ROTATE
    assert press(app, lab, ESC)


# -- Unverändert: Move, Modus-Schalter -------------------------------------------------------


@pytest.mark.parametrize("mode_presses", [0, 1], ids=["mark", "block"])
def test_move_unchanged_in_both_modes(symmetric, mode_presses):
    """Port: W spiegelt (Erklärung gesetzt) — in beiden Modi scharf, ohne Warnung,
    Partner bewegt sich mit, ein Undo-Schritt."""
    app, lab = symmetric
    for _ in range(mode_presses):
        assert press(app, lab, SHIFT_B)
    mesh = app.scene.mesh
    vid, partner = paired(app)
    select(app, vid)
    before = len(app.history)
    q0 = mesh.vertex_position(partner)
    assert press(app, lab, W) is True
    assert app.status_message.startswith("Move:")
    assert e5_warning_text(lab) == ""
    move_mouse(app)
    assert mesh.vertex_position(partner) != q0
    assert app.key_release(W)
    assert len(app.history) == before + 1


def test_mode_switch_is_lab_state_only(symmetric):
    """Port: Shift+B schaltet MARK ↔ BLOCK mit `E5-Modus: …`, ändert weder Mesh
    noch History; Ctrl+Z nimmt danach den letzten echten Schritt zurück."""
    app, lab = symmetric
    mesh = app.scene.mesh
    vid, _ = paired(app)
    select(app, vid)
    assert press(app, lab, W)
    move_mouse(app)
    assert app.key_release(W)
    history, state = len(app.history), mesh.export_state()
    can = (app.history.can_undo(), app.history.can_redo())

    assert press(app, lab, SHIFT_B) is True
    assert lab.gate_mode is GateMode.BLOCK
    assert app.status_message == "E5-Modus: BLOCK"
    assert app.command_gate == block_row().gate
    assert press(app, lab, SHIFT_B) is True
    assert lab.gate_mode is GateMode.MARK
    assert app.status_message == "E5-Modus: MARK"
    assert app.command_gate is ROW_MARK.gate
    assert (len(app.history), mesh.export_state()) == (history, state)
    assert (app.history.can_undo(), app.history.can_redo()) == can

    assert press(app, lab, CTRL_Z)  # Undo bleibt unbeeinflusst: nimmt den Move zurück
    assert len(app.history) == history - 1
    assert lab.axis == "X" and lab.gate_mode is GateMode.MARK


# -- Klassenattribut, keine Tool-Liste ------------------------------------------------------


def test_gate_reads_class_attribute(symmetric, monkeypatch):
    """Port: das Gate liest `supports_symmetry` an der Operation — kein Tool-Name."""
    app, lab = symmetric
    assert RotateOperation.supports_symmetry is True
    assert MoveOperation.supports_symmetry is True
    vid, _ = paired(app)
    select(app, vid)

    assert press(app, lab, E)
    assert e5_warning_text(lab) == ""
    assert press(app, lab, ESC)

    monkeypatch.setattr(RotateOperation, "supports_symmetry", False)
    assert press(app, lab, E)
    assert e5_warning_text(lab) == one_sided_text("Rotate")
    assert press(app, lab, ESC)

    monkeypatch.setattr(MoveOperation, "supports_symmetry", False)
    to_block(app, lab)
    assert press(app, lab, W) is False
    assert app.transform_command is None
    assert app.status_message.startswith("Symmetrie aktiv — Move spiegelt nicht")


# == Neu in Slice 4 ======================================================================

# -- Shift+B -----------------------------------------------------------------------------


def test_shift_b_toggles_without_history_or_mesh_change(lab_app):
    """Shift+B ab dem Default BLOCK (Slice 5): → MARK → BLOCK → MARK → BLOCK, True,
    `E5-Modus: <M>`; kein History-Eintrag, kein Mesh-Change — auch bei Symmetrie aus
    (die Zeile bleibt „aus")."""
    app, lab = lab_app
    assert lab.gate_mode is GateMode.BLOCK
    state = app.scene.mesh.export_state()
    for expected in (GateMode.MARK, GateMode.BLOCK, GateMode.MARK, GateMode.BLOCK):
        serial = app.status_serial
        assert press(app, lab, SHIFT_B) is True
        assert lab.gate_mode is expected
        assert app.status_serial == serial + 1
        assert app.status_message == f"E5-Modus: {expected.value}"
        assert app.command_gate is None
    assert len(app.history) == 0 and not app.history.can_undo()
    assert app.scene.mesh.export_state() == state
    # Der Modus gilt ab dem nächsten Symmetrie-Wechsel.
    assert press(app, lab, SHIFT_S)
    assert app.command_gate == block_row().gate
    assert len(app.history) == 1


def _armed(app, lab):
    select(app, paired(app)[0])
    assert press(app, lab, W)


def _running(app, lab):
    _armed(app, lab)
    move_mouse(app)
    assert app.transform_interacting


@pytest.mark.parametrize(
    "setup,owner",
    [(_armed, "Transform läuft"), (_running, "Transform läuft"), (begin_knife, "Knife-Session läuft")],
    ids=["armed", "running", "knife"],
)
def test_shift_b_is_refused_while_application_owns_the_keys(symmetric, setup, owner):
    """Shift+B während eines Transforms oder einer Knife-Session: abgelehnt
    (False, Status + 1), Modus, Gate und Interaktion bleiben (H2-R2)."""
    app, lab = symmetric
    setup(app, lab)
    gate, current = app.command_gate, app.interaction_owner
    serial = app.status_serial
    assert press(app, lab, SHIFT_B) is False
    assert app.status_serial == serial + 1
    assert app.status_message == f"E5-Modus (Shift+B) abgelehnt — {owner}"
    assert lab.gate_mode is GateMode.MARK
    assert app.command_gate is gate
    assert app.interaction_owner == current


def test_shift_b_is_refused_while_the_preview_is_open(symmetric):
    """Shift+B bei offener Re-Symmetrize-Vorschau: abgelehnt, die Vorschau-Zeile bleibt."""
    app, lab = symmetric
    select(app, paired(app)[0])
    assert press(app, lab, M) and lab.preview_open
    assert press(app, lab, SHIFT_B) is False
    assert lab.gate_mode is GateMode.MARK
    assert app.command_gate is ROW_PREVIEW.gate
    assert press(app, lab, ESC) and not lab.preview_open
    assert app.command_gate is ROW_MARK.gate


def test_hud_shows_the_mode_only_while_symmetry_is_on(lab_app):
    app, lab = lab_app
    assert "E5:" not in hud(app, lab)
    assert press(app, lab, SHIFT_B)  # Default BLOCK → MARK
    assert "E5:" not in hud(app, lab)
    assert press(app, lab, SHIFT_S)
    assert " | E5: MARK | " in hud(app, lab)
    assert press(app, lab, SHIFT_B)
    assert " | E5: BLOCK | " in hud(app, lab)
    assert press(app, lab, CTRL_Z)  # Undo des Shift+S: Symmetrie aus
    assert "E5:" not in hud(app, lab)
    # Ohne Modus-Argument (Slice-2-Aufrufer) bleibt die Zeile wie bisher.
    assert press(app, lab, CTRL_Y)
    assert "E5:" not in hud_text(app, "subd_cube", lab.report)


# -- C unter Symmetrie, MARK ---------------------------------------------------------------


def test_c_with_a_selection_under_mark_runs_one_sided(symmetric):
    """MARK, Edge gewählt, C → Split der App: ein History-Eintrag, einseitig (nur
    ein neuer Vertex, die Partner-Edge bleibt), der neue Vertex ist ohne Partner
    und erscheint magenta im Zustands-Overlay; die Symmetrie degradiert zu
    `partial`. Die Statuszeile ist die der App (`Split`), das Lab überschreibt sie
    nicht; keine Warnzeile (keine laufende Interaktion)."""
    app, lab = symmetric
    mesh = app.scene.mesh
    _plane, _lines, state_overlay = lab.overlays
    side_edge(app, lab)
    app.viewport.sync()
    assert state_overlay.points(UNPAIRED_LAYER) == []
    vertices = len(mesh.all_vertex_ids())
    before = len(app.history)

    assert press(app, lab, C) is True
    assert app.status_message == "Split"
    assert len(app.history) == before + 1
    assert len(mesh.all_vertex_ids()) == vertices + 1
    (new_vid,) = app.selection.vertices
    report = lab.report
    assert report.state is SymmetryState.PARTIAL
    assert new_vid in report.unpaired
    app.viewport.sync()
    assert mesh.vertex_position(new_vid) in state_overlay.points(UNPAIRED_LAYER)
    assert e5_warning_text(lab) == ""
    assert app.command_gate is ROW_MARK.gate

    assert press(app, lab, CTRL_Z)
    assert len(mesh.all_vertex_ids()) == vertices
    assert lab.report.state is SymmetryState.VALID


def test_c_with_empty_selection_under_mark_starts_a_knife_with_the_warning_line(symmetric):
    """MARK, leere Auswahl, C → Knife-Session; die HUD-Warnzeile steht, solange sie
    läuft, und ist nach Esc weg. Das Lab schreibt keinen Status (H2-R2)."""
    app, lab = symmetric
    assert e5_warning_text(lab) == ""
    begin_knife(app, lab)
    assert e5_warning_text(lab) == KNIFE_ONE_SIDED_TEXT
    status = (app.status_message, app.status_serial)
    assert press(app, lab, ESC) is True
    assert not app.knife_active
    assert e5_warning_text(lab) == ""
    assert app.status_message == "Knife cancelled"
    assert app.status_serial == status[1] + 1
    assert len(app.history) == 1  # nur das Shift+S


def test_knife_commit_under_mark_is_one_history_entry(symmetric):
    """MARK: einseitiger Knife-Schnitt (Diagonale einer +X-Face), Enter → genau ein
    History-Eintrag und genau eine neue Edge (die gespiegelte Face bleibt ungeschnitten);
    Warnzeile bis zum Commit, danach weg."""
    app, lab = symmetric
    a, b = one_side_diagonal(app)
    before = len(app.history)
    edges = len(app.scene.mesh.all_edge_ids())
    begin_knife(app, lab)
    knife_click(app, a)
    knife_click(app, b)
    assert e5_warning_text(lab) == KNIFE_ONE_SIDED_TEXT
    assert press(app, lab, ENTER) is True
    assert not app.knife_active
    assert len(app.history) == before + 1
    assert len(app.scene.mesh.all_edge_ids()) == edges + 1  # einseitig: eine neue Edge
    assert e5_warning_text(lab) == ""
    assert app.command_gate is ROW_MARK.gate


# -- C unter Symmetrie, BLOCK; C ohne Symmetrie ----------------------------------------------


@pytest.mark.parametrize("with_selection", [True, False], ids=["selection", "empty"])
def test_c_under_block_is_refused(symmetric, with_selection):
    """BLOCK: C → False, Status = Text des alten Labs, `status_serial` + 1; kein
    History-Eintrag, keine Knife-Session, Mesh unverändert."""
    app, lab = symmetric
    to_block(app, lab)
    if with_selection:
        side_edge(app, lab)
    else:
        app.pointer_motion(*MISS)
        app.selection.clear()
    state = app.scene.mesh.export_state()
    before = len(app.history)
    serial = app.status_serial
    assert press(app, lab, C) is False
    assert app.status_serial == serial + 1
    assert app.status_message == block_text("C")
    assert app.status_message == "Symmetrie aktiv — C spiegelt nicht (BLOCK: C nicht gestartet)"
    assert not app.knife_active
    assert len(app.history) == before
    assert app.scene.mesh.export_state() == state


@pytest.mark.parametrize("mode", [GateMode.MARK, GateMode.BLOCK], ids=["mark", "block"])
def test_c_with_symmetry_off_runs_in_both_modes(lab_app, mode):
    app, lab = lab_app
    set_mode(app, lab, mode)
    begin_knife(app, lab)
    assert e5_warning_text(lab) == ""  # ohne Symmetrie nichts einseitig
    assert press(app, lab, ESC)
    vertices = len(app.scene.mesh.all_vertex_ids())
    side_edge(app, lab)
    assert press(app, lab, C) is True
    assert app.status_message == "Split"
    assert len(app.scene.mesh.all_vertex_ids()) == vertices + 1


# -- Erklärung: abgeleitet, nie hart codiert ------------------------------------------------


def test_block_row_is_derived_from_the_declarations(monkeypatch):
    """Die BLOCK-Zeile = C + jedes Transform-Command ohne Erklärung, bei jeder
    Ableitung neu gelesen: heute nur C."""
    assert set(block_row().gate.refused) == {cmd.CONNECT}
    monkeypatch.setattr(ScaleOperation, "supports_symmetry", False)
    assert dict(block_row().gate.refused) == {
        cmd.CONNECT: block_text("C"),
        cmd.SCALE: block_text("Scale"),
    }
    assert block_row() == block_row()  # gleiche Erklärungen → gleiche Zeile (sync_gate: ==)


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_block_never_refuses_unpatched_transforms(symmetric, key):
    """W/E/R erklären `supports_symmetry`: BLOCK lässt sie unter Symmetrie laufen."""
    app, lab = symmetric
    to_block(app, lab)
    select(app, paired(app)[0])
    assert press(app, lab, key) is True
    assert app.transform_command is not None
    assert e5_warning_text(lab) == ""
    assert press(app, lab, ESC)


@pytest.mark.parametrize("key", [E, R], ids=["rotate", "scale"])
def test_patched_declaration_refuses_in_block_and_warns_in_mark(symmetric, monkeypatch, key):
    """Mit `supports_symmetry = False` an genau einer Operation: BLOCK lehnt genau
    dieses Command ab, MARK schaltet es mit der „läuft einseitig"-Warnzeile scharf."""
    app, lab = symmetric
    operation = RotateOperation if key is E else ScaleOperation
    monkeypatch.setattr(operation, "supports_symmetry", False)
    select(app, paired(app)[0])

    assert press(app, lab, key) is True  # MARK
    assert e5_warning_text(lab) == one_sided_text(LABELS[key])
    assert press(app, lab, ESC)

    to_block(app, lab)
    assert press(app, lab, key) is False
    assert app.status_message == block_text(LABELS[key])
    other = R if key is E else E
    assert press(app, lab, other) is True  # die andere erklärt weiter
    assert press(app, lab, ESC)


# -- Cancel, T-R3 (BLOCK), Start-Liste ------------------------------------------------------


@pytest.mark.parametrize("patched", [False, True], ids=["declared", "all_unsupported"])
def test_gate_never_refuses_cancel_outside_the_preview(monkeypatch, patched):
    """H2-R2: außerhalb der Vorschau lehnt keine Zeile `Cancel` ab — auch nicht,
    wenn keine Operation Symmetrie erklärt."""
    if patched:
        for operation in (MoveOperation, RotateOperation, ScaleOperation):
            monkeypatch.setattr(operation, "supports_symmetry", False)
    for row in gate_rows():
        if row is ROW_PREVIEW:
            continue
        assert row.gate is None or row.gate.refusal(cmd.CANCEL) is None, row.state
    assert set(block_row().gate.refused) <= {cmd.CONNECT, cmd.MOVE, cmd.ROTATE, cmd.SCALE}


def test_esc_under_block_still_cancels_a_running_move(symmetric):
    """Verhalten zu H2-R2: in BLOCK beendet Esc einen laufenden Move exakt."""
    app, lab = symmetric
    to_block(app, lab)
    select(app, paired(app)[0])
    state = app.scene.mesh.export_state()
    assert press(app, lab, W)
    move_mouse(app)
    assert press(app, lab, ESC) is True
    assert app.transform_command is None
    assert app.scene.mesh.export_state() == state


def _block_c_empty(app, lab):
    to_block(app, lab)
    app.pointer_motion(*MISS)
    app.selection.clear()


def _block_c_edge(app, lab):
    to_block(app, lab)
    side_edge(app, lab)


def _block_rotate_unsupported(app, lab):
    to_block(app, lab)
    select(app, paired(app)[0])


BLOCK_REFUSALS = [
    ("C_empty", _block_c_empty, C, block_text("C"), False),
    ("C_edge", _block_c_edge, C, block_text("C"), False),
    ("E_unsupported", _block_rotate_unsupported, E, block_text("Rotate"), True),
    ("R_unsupported", _block_rotate_unsupported, R, block_text("Scale"), True),
]


@pytest.mark.parametrize(
    "setup,inp,text,patch", [r[1:] for r in BLOCK_REFUSALS], ids=[r[0] for r in BLOCK_REFUSALS]
)
def test_t_r3_block_row_refusals_are_visible_and_counted(symmetric, monkeypatch, setup, inp, text, patch):
    """T-R3 (BLOCK-Zeile, Tasten — die Zeile lehnt keinen Klick ab): Rückgabe
    False, `status_serial` + 1, Text der Zeile; zweimal → +2. Mesh, History,
    Auswahl, Gate und Owner bleiben."""
    if patch:
        monkeypatch.setattr(RotateOperation, "supports_symmetry", False)
        monkeypatch.setattr(ScaleOperation, "supports_symmetry", False)
    app, lab = symmetric
    setup(app, lab)
    snapshot = (
        app.scene.mesh.export_state(),
        len(app.history),
        frozenset(app.selection.vertices),
        frozenset(app.selection.edges),
    )
    gate = app.command_gate
    serial = app.status_serial
    for n in (1, 2):
        assert press(app, lab, inp) is False
        assert app.status_serial == serial + n
        assert app.status_message == text
        app.key_release(inp)
    assert (
        app.scene.mesh.export_state(),
        len(app.history),
        frozenset(app.selection.vertices),
        frozenset(app.selection.edges),
    ) == snapshot
    assert app.command_gate is gate
    assert app.interaction_owner is None


def test_startup_listing_has_the_e5_rows_and_shift_b():
    """H2-R3: die Start-Liste nennt Shift+B und die Zeilen MARK und BLOCK; die
    Slice-1b-Zeile „C abgelehnt" gibt es nicht mehr."""
    lines = startup_listing()
    text = "\n".join(lines)
    assert "key:Shift+b -> SymmetryGateMode" in text
    assert any("E5-Modus (Shift+B: BLOCK <-> MARK, Default BLOCK" in line for line in lines)
    assert ROW_SYMMETRY_OFF.describe() in text
    assert ROW_MARK.describe() in text
    assert block_row().describe() in text
    assert block_text("C") in block_row().describe()
    assert "Slice 1, vor E5" not in text
    assert "C spiegelt nicht'" not in text  # kein alter 1b-Text ohne BLOCK-Zusatz
