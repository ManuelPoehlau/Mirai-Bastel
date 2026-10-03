"""Re-Symmetrize-Vorschau auf dem App-Pfad (WP-SYM-LAB-03 Slice 3).

Vertrag: AD-013, Addendum H2 (Gate-Tabelle „preview open", D1, H2-R2/R3, Required
tests). Verhalten: README „Manuelle Prüfung Slice 5" (KEEP 2026-09-25). Headless
wie `_app_lab_support`; alle Eingaben über `lab_key_press` und die öffentlichen
Eingänge von `Application`.

- T-R2c   F1-Sequenz: Vorschau offen, Alt+LMB + 10 px Drag, Ctrl+Z → False, History
          unverändert, Status; W → `transform_command is None`
- T-R2e   Vorschau offen: App-Commands (Tasten und Klick) abgelehnt, Owner bleibt
          None; Shift+S/Shift+B abgelehnt bei unverändertem Gate; Esc → True,
          Vorschau zu, kein History-Eintrag, Gate + Hover-Flag zurück
- N2      Regression der CLAUDE-002-Probe N2: M → Shift+S → W → Esc lässt kein
          scharfes Move zurück
- T-R3    Vorschau-Zeilen: jede abgelehnte Taste und jeder abgelehnte Klick → False,
          `status_serial` + 1, Text; zweimal → zwei Inkremente
- T-H     Lab-Ebene: Vorschau offen → Hover None; Bewegung über einem Vertex → None;
          zu → am Cursor neu gepickt (Face-Modus vor der Vorschau: N5)
- Ausführen über H3, Overlay, Vorschau-Zeile, Start-Liste, Fenster zu

Die Ports der Dispatcher-Tests aus `test_lab_resymmetrize.py` (Plan §4.4) stehen in
`test_app_lab_resymmetrize.py`.
"""

from __future__ import annotations

import pytest

from core import FaceId, SelectionMode, VertexId
from mirai.interaction import commands as cmd
from mirai.symmetry import SymmetryState, symmetry_state

from symmetry_lab.lab_app import (
    CANCEL_PREVIEW_LINE,
    DISPLAY_COMMANDS,
    PREVIEW_HINT,
    ROW_MARK,
    ROW_PREVIEW,
    ROW_SYMMETRY_OFF,
    block_row,
    gate_row_for,
    gate_rows,
    lab_key_press,
    startup_listing,
)
from symmetry_lab.lab_overlays import (
    AMBIGUOUS_LAYER,
    HOVER_PARTNER_LAYER,
    RESYM_KEEP_LAYER,
    RESYM_MOVE_LAYER,
    RESYM_MOVE_LINE_LAYER,
    RESYM_SEAM_LAYER,
    RESYM_SEAM_LINE_LAYER,
    SEAM_LAYER,
    SELECTION_PARTNER_LAYER,
    UNPAIRED_LAYER,
    ResymPreviewLineOverlay,
    SymmetryPlaneOverlay,
    SymmetryStateOverlay,
)
from symmetry_lab.run import run_lab

from ._app_lab_preview_support import (
    ALT_A,
    ALT_LMB,
    D,
    ONE,
    R,
    SHIFT_D,
    SHIFT_LMB,
    SHIFT_X,
    THREE,
    TWO,
    WHEEL_UP,
    X,
    first_visible,
    open_preview,
    select,
    select_on_side,
    side_vertices,
    state_snapshot,
    symmetry_to,
)
from ._app_lab_support import (  # noqa: F401
    CTRL_Y,
    CTRL_Z,
    ESC,
    LMB,
    M,
    SHIFT_B,
    SHIFT_S,
    C,
    E,
    W,
    click,
    forbid_lab_calls,
    make_lab,
    press,
    screen,
)


def _assert_closed_on_symmetry_row(app, lab) -> None:
    assert not lab.preview_open
    # Slice 4: die Zeile hängt auch am E5-Modus; BLOCK wird je Ableitung neu gebaut (==).
    assert app.command_gate == gate_row_for(lab.axis, lab.gate_mode).gate
    assert app.hover_suspended is False


@pytest.fixture
def previewing():
    """man_with_shoes, Symmetrie X (partial, 54 ohne Partner), Vertex auf Seite 0
    geklickt, M → Vorschau mit 27 Moves (README Slice 5, Schritte 1–4)."""
    app, lab, source = open_preview("man_with_shoes_basemesh", side=0)
    assert len(lab.preview.moves) == 27
    return app, lab, source


@pytest.fixture
def cube_preview():
    """subd_cube, Symmetrie X, Vertex auf Seite 0, Vorschau offen (0 Änderungen)."""
    return open_preview("subd_cube", side=0)


# -- Öffnen (README Schritte 4–5) ---------------------------------------------------


def test_m_opens_the_preview_with_gate_row_and_paused_hover(previewing):
    app, lab, _source = previewing
    assert app.command_gate is ROW_PREVIEW.gate
    assert ROW_PREVIEW.gate.allowed == DISPLAY_COMMANDS
    assert ROW_PREVIEW.gate.not_allowed_text == PREVIEW_HINT == "Vorschau aktiv — Befehl ignoriert"
    assert app.hover_suspended is True
    assert app.selection.hovered is None
    assert app.interaction_owner is None
    assert len(app.history) == 1  # nur das Shift+S
    # Wie das alte Lab: die Statusmeldung wird geleert, die Vorschau-Zeile spricht.
    assert app.status_message == ""


def test_plan_is_computed_once_when_opening(previewing, monkeypatch):
    """Der Plan wird beim Öffnen gerechnet und bis zum Ausführen nicht neu."""
    import symmetry_lab.lab_app as lab_app_module

    app, lab, _source = previewing
    plan = lab.preview
    monkeypatch.setattr(
        lab_app_module, "plan_resymmetrize", lambda *a, **k: pytest.fail("neu gerechnet")
    )
    app.pointer_scroll(WHEEL_UP)
    press(app, lab, W)
    assert lab.preview is plan
    assert press(app, lab, M) is True
    assert not lab.preview_open


# -- Ausführen (README Schritte 6–7, 10; M/M/Esc selbst: test_app_lab_resymmetrize) ----


def test_ctrl_z_restores_mesh_and_selection_then_redo(previewing):
    """README Schritt 7: Ctrl+Z → wieder partial (ein Schritt), Ctrl+Y → valid; die
    App stellt dabei die Auswahl wieder her (H3, Selektions-Spiegel)."""
    app, lab, source = previewing
    before = app.scene.mesh.export_state()
    assert press(app, lab, M)
    after = app.scene.mesh.export_state()
    select(app, first_visible(app, side_vertices(app, 1)))
    assert press(app, lab, CTRL_Z) is True
    assert app.scene.mesh.export_state() == before
    assert app.selection.vertices == {source}
    assert symmetry_state(app.scene.mesh) is SymmetryState.PARTIAL
    assert lab.axis == "X" and app.command_gate == block_row().gate  # E5-Default BLOCK
    assert press(app, lab, CTRL_Y) is True
    assert app.scene.mesh.export_state() == after
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID


def test_execute_goes_through_apply_mesh_change(previewing, monkeypatch):
    """H3: genau ein `apply_mesh_change`; `mutate` setzt die Positionen des Plans
    und gibt die bewegten IDs zurück."""
    app, lab, _source = previewing
    plan = lab.preview
    calls = []
    original = type(app).apply_mesh_change

    def recording(self, description, mutate):
        def wrapped():
            moved = mutate()
            calls.append((description, moved))
            return moved

        return original(self, description, wrapped)

    monkeypatch.setattr(type(app), "apply_mesh_change", recording)
    assert press(app, lab, M)
    assert len(calls) == 1
    description, moved = calls[0]
    assert description == f"Re-Symmetrize {plan.source_label} → {plan.target_label}"
    assert moved == {c.vertex for c in plan.changes}
    for change in plan.changes:
        assert app.scene.mesh.vertex_position(change.vertex) == change.after


# -- Esc (D1, README Schritt 8) ---------------------------------------------------------


def test_esc_does_not_reach_application_while_the_preview_is_open(previewing):
    """D1: das Lab nimmt das aufgelöste `Cancel` nur bei offener Vorschau."""
    app, lab, _source = previewing
    forwarded = []
    assert lab_key_press(app, lab, ESC, forward=forwarded.append) is True
    assert forwarded == []
    # Ohne Vorschau geht Esc unverändert weiter (T-R2f bleibt grün).
    assert lab_key_press(app, lab, ESC, forward=lambda i: forwarded.append(i) or False) is False
    assert forwarded == [ESC]


# -- T-R2c (F1) -------------------------------------------------------------------------


def test_t_r2c_ctrl_z_and_w_refused_mid_orbit_under_the_preview():
    """T-R2c (F1, probe P1): Vorschau offen mit nicht-leerer History; Alt+LMB +
    10 px Drag (Orbit läuft) → Ctrl+Z → False, History unverändert, Status
    gepostet; W → kein Transform. Esc mitten im Orbit schließt die Vorschau, der
    Orbit läuft weiter."""
    app, lab = make_lab("man_with_shoes_basemesh")
    symmetry_to(app, lab, "X")
    source = select_on_side(app, 0)
    assert press(app, lab, W)
    app.pointer_motion(400, 300, 6.0, 3.0)
    assert app.key_release(W)
    assert len(app.history) == 2
    assert app.selection.vertices == {source}  # die App behält die Auswahl nach dem Commit
    assert press(app, lab, M) and lab.preview_open

    x, y = screen(app, source)
    app.pointer_press(ALT_LMB, x, y)
    app.pointer_drag(10, 0, x + 10, y)
    assert app.pointer.active
    snapshot = state_snapshot(app)
    serial = app.status_serial
    assert lab_key_press(app, lab, CTRL_Z) is False
    assert app.status_serial == serial + 1
    assert app.status_message == PREVIEW_HINT
    assert state_snapshot(app) == snapshot
    assert lab_key_press(app, lab, W) is False
    assert app.transform_command is None
    assert app.interaction_owner is None

    assert lab_key_press(app, lab, ESC) is True
    assert not lab.preview_open and app.pointer.active
    yaw = app.camera.yaw
    app.pointer_drag(10, 0, x + 20, y)
    assert app.camera.yaw != yaw
    app.pointer_release("LEFT", x + 20, y)
    assert state_snapshot(app) == snapshot


# -- T-R2e (D1, N2) ----------------------------------------------------------------------

REFUSED_APP_KEYS = [W, E, R, C, CTRL_Z, CTRL_Y, ONE, TWO, THREE, X, SHIFT_X, ALT_A]


def test_t_r2e_everything_refused_then_esc_restores_the_symmetry_row(previewing):
    """T-R2e: W, E, R, C, Ctrl+Z, 1/2/3, X, Alt+A und ein Auswahl-Klick abgelehnt,
    `interaction_owner` bleibt None; Shift+S und Shift+B abgelehnt, `command_gate`
    unverändert (Vorschau-Zeile); Esc → True, Vorschau zu, kein History-Eintrag,
    Gate und Hover-Flag zurück auf die Zeile des Symmetrie-Zustands."""
    app, lab, _source = previewing
    snapshot = state_snapshot(app)
    other = first_visible(app, side_vertices(app, 1))
    for inp in REFUSED_APP_KEYS:
        assert lab_key_press(app, lab, inp) is False, inp
        assert app.interaction_owner is None, inp
        app.key_release(inp)
    for inp in (LMB, SHIFT_LMB):
        assert click(app, *screen(app, other), inp) is False
        assert app.interaction_owner is None
    assert state_snapshot(app) == snapshot
    for inp in (SHIFT_S, SHIFT_B):
        assert lab_key_press(app, lab, inp) is False
        assert app.command_gate is ROW_PREVIEW.gate
        assert lab.preview_open
    assert lab.axis == "X"
    assert lab_key_press(app, lab, ESC) is True
    _assert_closed_on_symmetry_row(app, lab)
    assert state_snapshot(app) == snapshot


@pytest.mark.parametrize("inp", [D, SHIFT_D], ids=["d", "shift_d"])
def test_display_commands_pass_the_preview(previewing, inp):
    """Gate-Zeile „preview open": nur Anzeige-Commands gehen durch."""
    app, lab, _source = previewing
    display = (app.display.mode, app.display.show_edges)
    assert lab_key_press(app, lab, inp) is True
    assert (app.display.mode, app.display.show_edges) != display
    assert lab.preview_open and app.command_gate is ROW_PREVIEW.gate


def test_n2_shift_s_then_w_then_esc_leaves_no_armed_move(previewing):
    """N2-Regression (Probe CLAUDE-002 N2): M → Shift+S → W → Esc. Shift+S wird
    abgelehnt und schreibt keine Zeile, also wird W nicht scharf; Esc schließt die
    Vorschau, kein Move bleibt scharf."""
    app, lab, _source = previewing
    assert lab_key_press(app, lab, SHIFT_S) is False
    assert app.command_gate is ROW_PREVIEW.gate
    assert lab_key_press(app, lab, W) is False
    assert app.interaction_owner is None
    assert lab_key_press(app, lab, ESC) is True
    assert not lab.preview_open
    assert app.transform_command is None
    assert app.interaction_owner is None
    app.key_release(W)
    assert app.transform_command is None


def test_installing_another_row_while_the_preview_is_open_asserts(previewing):
    """H2-R2 (N2): eine andere Zeile als die Vorschau-Zeile bei offener Vorschau
    ist ein Programmierfehler; `sync_gate` installiert dann gar nichts."""
    app, lab, _source = previewing
    for row in (ROW_SYMMETRY_OFF, ROW_MARK, block_row()):
        with pytest.raises(AssertionError, match="H2-R2"):
            lab._install_row(row)
    assert lab.sync_gate() is False
    assert app.command_gate is ROW_PREVIEW.gate


# -- T-R3 (Vorschau-Zeilen) ----------------------------------------------------------------

PREVIEW_REFUSED_KEYS = REFUSED_APP_KEYS + [SHIFT_S, SHIFT_B]


@pytest.mark.parametrize("inp", PREVIEW_REFUSED_KEYS, ids=lambda i: "+".join(sorted(i.modifiers) + [i.value]))
def test_t_r3_preview_row_refuses_keys_visibly(cube_preview, inp):
    """T-R3: Rückgabe False, `status_serial` + 1, Text der Zeile; zweimal → +2."""
    app, lab, _source = cube_preview
    snapshot = state_snapshot(app)
    serial = app.status_serial
    for n in (1, 2):
        assert lab_key_press(app, lab, inp) is False
        assert app.status_serial == serial + n
        assert app.status_message == PREVIEW_HINT
        app.key_release(inp)
    assert state_snapshot(app) == snapshot
    assert lab.preview_open and app.command_gate is ROW_PREVIEW.gate


@pytest.mark.parametrize("inp", [LMB, SHIFT_LMB], ids=["select", "select_add"])
def test_t_r3_preview_row_refuses_clicks_visibly(cube_preview, inp):
    app, lab, _source = cube_preview
    other = first_visible(app, side_vertices(app, 1))
    snapshot = state_snapshot(app)
    serial = app.status_serial
    for n in (1, 2):
        assert click(app, *screen(app, other), inp) is False
        assert app.status_serial == serial + n
        assert app.status_message == PREVIEW_HINT
    assert state_snapshot(app) == snapshot


# -- T-H (Lab-Ebene) -----------------------------------------------------------------------


def test_t_h_hover_paused_while_open_and_repicked_after(cube_preview):
    """Port von `test_hover_paused_during_preview`: Vorschau offen → Hover None;
    Bewegung über einem Vertex → None; Esc → am Cursor neu gepickt."""
    app, lab, _source = cube_preview
    target = first_visible(app, side_vertices(app, 1))
    x, y = screen(app, target)
    app.pointer_motion(x, y)
    assert app.selection.hovered is None
    app.pointer_scroll(WHEEL_UP)  # Probe P2: Zoom pickt neu, aber nicht unter der Vorschau
    assert app.selection.hovered is None
    x, y = screen(app, target)
    app.pointer_motion(x, y)
    assert app.selection.hovered is None
    assert press(app, lab, ESC)
    assert app.selection.hovered == target


def test_t_h_face_mode_before_the_preview():
    """T-H und N5 auf dem Lab-Pfad: im Face-Modus gibt es keine Vertex-Auswahl, M
    lehnt also ab wie der alte Dispatcher (`selection.vertices`), ohne das
    Hover-Flag anzufassen. Unter einer offenen Vorschau ist 3 abgelehnt, der Hover
    bleibt aus; nach Esc kommt er zurück, und im Face-Modus wieder als Face."""
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    assert press(app, lab, THREE)
    assert app.selection.mode is SelectionMode.FACE
    # Face-Modus, keine Vertex-Auswahl → M abgelehnt wie im alten Lab.
    assert press(app, lab, M) is False
    assert app.status_message == "Re-Symmetrize: keine Auswahl"
    assert app.hover_suspended is False
    assert press(app, lab, ONE)
    select_on_side(app, 0)
    assert press(app, lab, M) and lab.preview_open
    assert press(app, lab, THREE) is False
    assert app.selection.mode is SelectionMode.VERTEX
    x, y = screen(app, first_visible(app, side_vertices(app, 1)))
    app.pointer_motion(x, y)
    assert app.selection.hovered is None
    assert press(app, lab, ESC)
    assert isinstance(app.selection.hovered, VertexId)
    assert press(app, lab, THREE)
    app.pointer_motion(x, y)
    assert isinstance(app.selection.hovered, FaceId)


# -- Overlay (H1) ----------------------------------------------------------------------------


def _preview_overlays(lab) -> tuple[ResymPreviewLineOverlay, SymmetryStateOverlay]:
    plane, lines, state = lab.overlays
    assert isinstance(plane, SymmetryPlaneOverlay)
    assert isinstance(lines, ResymPreviewLineOverlay)
    assert isinstance(state, SymmetryStateOverlay)
    return lines, state


def test_preview_layers_present_while_open_and_empty_after_execute(previewing):
    app, lab, _source = previewing
    plan = lab.preview
    lines, state = _preview_overlays(lab)
    app.viewport.sync()
    mesh = app.scene.mesh
    assert state.points(RESYM_MOVE_LAYER) == [c.before for c in plan.moves]
    assert lines.segments(RESYM_MOVE_LINE_LAYER) == [(c.before, c.after) for c in plan.moves]
    assert state.points(RESYM_SEAM_LAYER) == [c.before for c in plan.seam_moves]
    assert lines.segments(RESYM_SEAM_LINE_LAYER) == [(c.before, c.after) for c in plan.seam_moves]
    assert state.points(RESYM_KEEP_LAYER) == [
        mesh.vertex_position(v) for v in sorted(plan.unmatched, key=int)
    ]
    assert press(app, lab, M)
    app.viewport.sync()
    for layer in (RESYM_MOVE_LAYER, RESYM_SEAM_LAYER, RESYM_KEEP_LAYER):
        assert state.points(layer) == []
    for layer in (RESYM_MOVE_LINE_LAYER, RESYM_SEAM_LINE_LAYER):
        assert lines.segments(layer) == []


def test_preview_layers_empty_after_esc(previewing):
    app, lab, _source = previewing
    lines, state = _preview_overlays(lab)
    app.viewport.sync()
    assert state.points(RESYM_MOVE_LAYER)
    assert press(app, lab, ESC)
    app.viewport.sync()
    assert state.points(RESYM_MOVE_LAYER) == []
    assert lines.segments(RESYM_MOVE_LINE_LAYER) == []


def test_seam_and_keep_layers_follow_the_plan():
    """Seam-Vertex neben der Ebene (hellgrün + Linie) über `apply_mesh_change` als
    Testvorbereitung, wie `test_seam_vertex_moved_off_plane_ends_exactly_on_plane`."""
    from ._app_lab_preview_support import seam_vertices

    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    seam = seam_vertices(app)[0]
    x, y, z = app.scene.mesh.vertex_position(seam)

    def nudge():
        app.scene.mesh.set_vertex_position(seam, (0.3, y, z))
        return {seam}

    assert app.apply_mesh_change("test: Seam neben die Ebene", nudge)
    select_on_side(app, 0)
    assert press(app, lab, M)
    lines, state = _preview_overlays(lab)
    app.viewport.sync()
    assert state.points(RESYM_SEAM_LAYER) == [(0.3, y, z)]
    assert lines.segments(RESYM_SEAM_LINE_LAYER) == [((0.3, y, z), (0.0, y, z))]


def test_preview_point_layers_sit_between_state_and_partner_markers():
    """Reihenfolge des alten Renderers: Zustand → Vorschau → Hover-Partner →
    Auswahl-Partner (README „Zeichenreihenfolge")."""
    assert SymmetryStateOverlay.LAYERS == (
        SEAM_LAYER,
        UNPAIRED_LAYER,
        AMBIGUOUS_LAYER,
        RESYM_MOVE_LAYER,
        RESYM_SEAM_LAYER,
        RESYM_KEEP_LAYER,
        HOVER_PARTNER_LAYER,
        SELECTION_PARTNER_LAYER,
    )
    assert ResymPreviewLineOverlay.NO_DEPTH_LAYERS == frozenset(ResymPreviewLineOverlay.LAYERS)


def test_preview_overlays_are_drawn_before_the_app_points(previewing, monkeypatch):
    app, lab, _source = previewing
    plane, lines, state = lab.overlays
    log = []

    class AppPoints:
        def set_points(self, layer, positions):
            pass

        def draw(self, camera_uniforms):
            log.append("app points")

    app.viewport.point_overlay = AppPoints()
    monkeypatch.setattr(plane, "draw", lambda uniforms: log.append("lab plane"))
    monkeypatch.setattr(lines, "draw", lambda uniforms: log.append("lab preview lines"))
    monkeypatch.setattr(state, "draw", lambda uniforms: log.append("lab points"))
    app.viewport.sync()
    app.viewport.render()
    assert log == ["lab plane", "lab preview lines", "lab points", "app points"]


#: Die Farbwerte des alten Renderers (`lab_render.py`, gelöscht in WP-SYM-LAB-03 Slice 5;
#: Stand `065508c`). Bis Slice 5 las der Test sie per AST aus der Datei.
OLD_RENDERER_COLOURS = {
    "RESYM_MOVE_COLOR": (0.25, 0.5, 1.0, 1.0),
    "RESYM_SEAM_COLOR": (0.75, 1.0, 0.1, 1.0),
    "RESYM_KEEP_COLOR": (1.0, 0.55, 0.55, 1.0),
}


def test_preview_colours_are_the_old_renderers():
    """README-Legende: blau / hellgrün / hellrot — Werte des alten `lab_render.py`."""
    colours = OLD_RENDERER_COLOURS
    styles = SymmetryStateOverlay.LAYER_STYLES
    assert styles[RESYM_MOVE_LAYER][0] == colours["RESYM_MOVE_COLOR"]
    assert styles[RESYM_SEAM_LAYER][0] == colours["RESYM_SEAM_COLOR"]
    assert styles[RESYM_KEEP_LAYER][0] == colours["RESYM_KEEP_COLOR"]
    lines = ResymPreviewLineOverlay.LAYER_STYLES
    assert lines[RESYM_MOVE_LINE_LAYER][0] == colours["RESYM_MOVE_COLOR"]
    assert lines[RESYM_SEAM_LINE_LAYER][0] == colours["RESYM_SEAM_COLOR"]


# -- Start-Liste (H2-R3, N8), Fenster zu ------------------------------------------------------


def test_startup_listing_contains_the_preview_row_and_the_esc_line():
    lines = startup_listing()
    text = "\n".join(lines)
    assert ROW_PREVIEW in gate_rows()
    assert ROW_PREVIEW.describe() in text
    assert PREVIEW_HINT in ROW_PREVIEW.describe()
    assert "hover_suspended" in ROW_PREVIEW.describe()
    assert CANCEL_PREVIEW_LINE == "Cancel (Esc): closes the Re-Symmetrize preview while it is open"
    assert any(line.strip() == CANCEL_PREVIEW_LINE for line in lines)
    for command in DISPLAY_COMMANDS:
        assert command in ROW_PREVIEW.describe()
    assert cmd.MOVE not in ROW_PREVIEW.gate.allowed


def test_closing_the_window_ends_the_preview(previewing):
    """H2-R2: die Vorschau endet mit dem Fenster; `run_lab` setzt Gate und
    Hover-Flag zurück, wenn der Event-Loop zurückkehrt (auch bei einem Fehler)."""
    app, lab, _source = previewing

    class FakeMain:
        def run(self, window, app):
            assert lab.preview_open

    run_lab(object(), app, lab, FakeMain())
    _assert_closed_on_symmetry_row(app, lab)

    assert press(app, lab, M)  # wieder offen (Auswahl ist noch da)

    class FailingMain:
        def run(self, window, app):
            raise RuntimeError("loop died")

    with pytest.raises(RuntimeError):
        run_lab(object(), app, lab, FailingMain())
    _assert_closed_on_symmetry_row(app, lab)
