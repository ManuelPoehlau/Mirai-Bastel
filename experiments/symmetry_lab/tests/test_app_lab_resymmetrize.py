"""Ports der Dispatcher-Tests aus `test_lab_resymmetrize.py` auf den App-Pfad
(WP-SYM-LAB-03 Slice 3, Plan §4.4).

Die Originale und die reinen Tests (`plan_resymmetrize`, `apply_plan`,
`plan_summary`, `resym_preview_data`) bleiben unverändert in `test_lab_resymmetrize.py`
bis Slice 5. Hier läuft dasselbe Verhalten über `lab_key_press` und die öffentlichen
Eingänge von `Application` statt über `LabDispatcher`; Auswahl per Klick statt
`selection.set`. Gleicher Name = gleiche Aussage wie das Original. Zuordnung:

| Original (`LabDispatcher`) | hier bzw. |
|---|---|
| `test_man_with_shoes_from_either_side_becomes_valid[0,1]` | gleich |
| `test_seam_vertex_moved_off_plane_ends_exactly_on_plane` | gleich (Seam über `apply_mesh_change` verschoben) |
| `test_rejected_when_symmetry_off` / `_without_selection` / `_for_seam_vertex` / `_when_seam_does_not_split_into_two` | gleich (Texte des alten Labs) |
| `test_rejected_while_move_armed`, `_while_move_dragging` | `test_rejected_while_move_armed_or_dragging[armed,running]` (Owner-Ablehnung, H2-R2) |
| `test_m_esc_leaves_mesh_unchanged_and_no_history` | gleich |
| `test_m_m_executes_with_one_history_entry` | gleich |
| `test_other_keys_are_ignored_during_preview[Shift+S,W,Ctrl+Z,Ctrl+Y]` | gleich (Rückgabe jetzt False, H2-R3) |
| `test_select_is_ignored_during_preview` | gleich |
| `test_click_pressed_before_m_does_not_select_during_preview` | gleich |
| `test_navigation_allowed_during_preview` | gleich |
| `test_hover_paused_during_preview` | `test_app_lab_preview.py::test_t_h_hover_paused_while_open_and_repicked_after` |
| `test_zero_changes_preview_then_m_creates_no_history_entry` | gleich |
| `test_status_line_shows_direction_counts_and_keys` | gleich (`lab_app.preview_text`) |
| `test_preview_draw_data` | `test_app_lab_preview.py::test_preview_layers_present_while_open_and_empty_after_execute` |
| `test_paired_state_unaffected_by_preview` | gleich |

Neu ohne Original: `test_rejected_with_two_selected_vertices` (der dritte Grund des
alten Dispatchers, dort ungetestet).
"""

from __future__ import annotations

import pytest

from mirai.symmetry import SymmetryState, mirror_position, symmetry_state

from symmetry_lab.lab_app import (
    PREVIEW_HINT,
    ROW_SYMMETRY_OFF,
    ROW_SYMMETRY_ON,
    lab_key_press,
    preview_text,
)
from symmetry_lab.lab_resymmetrize import plan_summary
from symmetry_lab.lab_symmetry import symmetry_report
from symmetry_lab.lab_topology import topology_report

from ._app_lab_preview_support import (
    ALT_LMB,
    SHIFT_LMB,
    WHEEL_UP,
    first_visible,
    open_preview,
    seam_vertices,
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
    SHIFT_S,
    W,
    click,
    forbid_lab_calls,
    make_lab,
    press,
    screen,
    visible,
)

PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def _assert_closed_on_symmetry_row(app, lab) -> None:
    assert not lab.preview_open
    row = ROW_SYMMETRY_ON if lab.axis is not None else ROW_SYMMETRY_OFF
    assert app.command_gate is row.gate
    assert app.hover_suspended is False


@pytest.fixture
def previewing():
    """man_with_shoes, Symmetrie X, Vertex auf Seite 0 geklickt, Vorschau offen
    (27 Moves) — wie die Fixture `previewing` des Originals."""
    app, lab, source = open_preview("man_with_shoes_basemesh", side=0)
    assert len(lab.preview.moves) == 27
    return app, lab, source


@pytest.fixture
def cube_preview():
    return open_preview("subd_cube", side=0)


# -- man_with_shoes: von jeder Seite aus (§7) ------------------------------------


@pytest.mark.parametrize("source_side", [0, 1])
def test_man_with_shoes_from_either_side_becomes_valid(source_side):
    app, lab = make_lab("man_with_shoes_basemesh")
    symmetry_to(app, lab, "X")
    mesh = app.scene.mesh
    assert len(symmetry_report(mesh).unpaired) == 54
    source_vertices = side_vertices(app, source_side)
    source_before = {v: mesh.vertex_position(v) for v in source_vertices}
    state_before = mesh.export_state()
    history_before = len(app.history)

    source = select_on_side(app, source_side)
    assert press(app, lab, M) is True and lab.preview_open
    assert press(app, lab, M) is True and not lab.preview_open

    report = symmetry_report(mesh)
    assert report.state is SymmetryState.VALID
    assert report.unpaired == frozenset()
    assert len(app.history) == history_before + 1
    # Quellseite bitgenau unverändert (E13)
    assert all(repr(mesh.vertex_position(v)) == repr(p) for v, p in source_before.items())
    partners = topology_report(mesh).pairing.partners
    for vid in side_vertices(app, 1 - source_side):
        if vid in partners:
            assert mesh.vertex_position(vid) == mirror_position(
                mesh.vertex_position(partners[vid]), *PLANE
            )

    assert press(app, lab, CTRL_Z) is True
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.selection.vertices == {source}


# -- Seam (E13) ---------------------------------------------------------------------


def test_seam_vertex_moved_off_plane_ends_exactly_on_plane():
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    mesh = app.scene.mesh
    seam_vid = seam_vertices(app)[0]
    _x, y, z = mesh.vertex_position(seam_vid)

    def nudge():
        mesh.set_vertex_position(seam_vid, (0.3, y, z))
        return {seam_vid}

    # Testvorbereitung über den öffentlichen Eingang (das Original schrieb direkt).
    assert app.apply_mesh_change("test: Seam neben die Ebene", nudge)
    assert symmetry_state(mesh) is SymmetryState.VIOLATED

    select_on_side(app, 0)
    assert press(app, lab, M) is True
    assert [c.vertex for c in lab.preview.seam_moves] == [seam_vid]
    assert lab.preview.moves == ()
    assert press(app, lab, M) is True
    assert mesh.vertex_position(seam_vid) == (0.0, y, z)
    assert symmetry_state(mesh) is SymmetryState.VALID


# -- Ablehnungen (E15, README Slice 5 Schritt 12) --------------------------------------


def _assert_refused(app, lab, text: str) -> None:
    snapshot = state_snapshot(app)
    gate = app.command_gate
    serial = app.status_serial
    assert press(app, lab, M) is False
    assert not lab.preview_open
    assert app.status_serial == serial + 1
    assert app.status_message == text
    assert app.command_gate is gate
    assert app.hover_suspended is False
    assert state_snapshot(app) == snapshot


def test_rejected_when_symmetry_off():
    app, lab = make_lab("subd_cube")
    select(app, visible(app)[0])
    _assert_refused(app, lab, "Re-Symmetrize: Symmetrie aus")


def test_rejected_without_selection():
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    _assert_refused(app, lab, "Re-Symmetrize: keine Auswahl")


def test_rejected_with_two_selected_vertices():
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    a = first_visible(app, side_vertices(app, 0))
    b = first_visible(app, [v for v in side_vertices(app, 0) if v != a])
    select(app, a)
    click(app, *screen(app, b), SHIFT_LMB)
    assert app.selection.vertices == {a, b}
    _assert_refused(app, lab, "Re-Symmetrize: genau einen Vertex auswählen")


def test_rejected_for_seam_vertex():
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    select(app, first_visible(app, seam_vertices(app)))
    _assert_refused(app, lab, "Re-Symmetrize: Seam-Vertex gewählt — Quellseite unklar")


def test_rejected_when_seam_does_not_split_into_two():
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "Y")  # 0 Seam-Edges → 1 Komponente
    select(app, visible(app)[0])
    _assert_refused(app, lab, "Re-Symmetrize: Seam teilt das Mesh in 1 Teile (nötig: genau 2)")


@pytest.mark.parametrize("running", [False, True], ids=["armed", "running"])
def test_rejected_while_move_armed_or_dragging(running):
    """README Schritt 12 („Move scharf"); auf dem App-Pfad die Owner-Ablehnung von
    Slice 1b (H2-R2), die Vorschau öffnet nicht, Gate und Hover-Flag bleiben."""
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    select_on_side(app, 0)
    assert press(app, lab, W)
    if running:
        app.pointer_motion(400, 300, 8.0, 2.0)
        assert app.transform_interacting
    serial = app.status_serial
    assert press(app, lab, M) is False
    assert not lab.preview_open
    assert app.status_serial == serial + 1
    assert app.status_message == "Re-Symmetrize (M) abgelehnt — Transform läuft"
    assert app.command_gate is ROW_SYMMETRY_ON.gate
    assert app.hover_suspended is False
    assert press(app, lab, ESC)
    assert app.transform_command is None


# -- Vorschau-Zustand (A7, E15) ---------------------------------------------------------


def test_status_line_shows_direction_counts_and_keys(previewing):
    """README Schritt 4: Richtung, Anzahlen, Tasten; leer ohne Vorschau (wie
    `test_status_line_shows_direction_counts_and_keys` im alten Lab)."""
    app, lab, _source = previewing
    plan = lab.preview
    text = preview_text(lab)
    assert text == plan_summary(plan)
    assert f"Quelle {plan.source_label} → Ziel {plan.target_label}" in text
    assert "bewegt 27" in text
    assert "M = ausführen, ESC = abbrechen" in text
    assert press(app, lab, ESC)
    assert preview_text(lab) == ""


def test_m_m_executes_with_one_history_entry(previewing):
    app, lab, source = previewing
    history = len(app.history)
    assert press(app, lab, M) is True
    _assert_closed_on_symmetry_row(app, lab)
    assert len(app.history) == history + 1
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID
    assert app.status_message == "Re-Symmetrize ausgeführt: 27 Änderungen"
    assert app.selection.vertices == {source}  # Auswahl bleibt (§4.1)


def test_zero_changes_preview_then_m_creates_no_history_entry(cube_preview):
    """README Schritt 10 / E15: Vorschau `0 Änderungen`, M → kein Schritt;
    Ctrl+Z nimmt danach das Shift+S zurück, nicht Re-Symmetrize."""
    app, lab, _source = cube_preview
    assert lab.preview.is_empty
    assert "0 Änderungen" in preview_text(lab)
    state = app.scene.mesh.export_state()
    history = len(app.history)
    assert press(app, lab, M) is True
    _assert_closed_on_symmetry_row(app, lab)
    assert len(app.history) == history
    assert app.scene.mesh.export_state() == state
    assert app.status_message == "Re-Symmetrize: 0 Änderungen — kein Schritt"
    assert press(app, lab, CTRL_Z)
    assert lab.axis is None
    assert app.command_gate is None


def test_m_esc_leaves_mesh_unchanged_and_no_history(previewing):
    app, lab, _source = previewing
    snapshot = state_snapshot(app)
    assert lab_key_press(app, lab, ESC) is True
    _assert_closed_on_symmetry_row(app, lab)
    assert state_snapshot(app) == snapshot
    assert app.status_message == "Re-Symmetrize abgebrochen"


def test_navigation_allowed_during_preview(previewing):
    """README Schritt 5: Orbit, Pan, Zoom laufen weiter (nie gegatet)."""
    app, lab, source = previewing
    camera = app.camera
    before = (camera.yaw, camera.pitch, camera.distance, tuple(camera.target))
    x, y = screen(app, source)
    app.pointer_press(ALT_LMB, x, y)
    app.pointer_drag(20, 10, x + 20, y + 10)
    app.pointer_release("LEFT", x + 20, y + 10)
    app.pointer_scroll(WHEEL_UP)
    assert (camera.yaw, camera.pitch, camera.distance, tuple(camera.target)) != before
    assert lab.preview_open


def test_click_pressed_before_m_does_not_select_during_preview():
    """Ein Klick, der vor M begann, wird beim Loslassen vom Gate abgelehnt."""
    app, lab = make_lab("subd_cube")
    symmetry_to(app, lab, "X")
    source = select_on_side(app, 0)
    other = first_visible(app, side_vertices(app, 1))
    x, y = screen(app, other)
    app.pointer_press(LMB, x, y)
    assert press(app, lab, M) and lab.preview_open
    assert app.pointer_release("LEFT", x, y) is False
    assert app.selection.vertices == {source}
    assert app.status_message == PREVIEW_HINT


@pytest.mark.parametrize("inp", [SHIFT_S, W, CTRL_Z, CTRL_Y], ids=["shift_s", "w", "ctrl_z", "ctrl_y"])
def test_other_keys_are_ignored_during_preview(previewing, inp):
    """Ignoriert mit Hinweis; Rückgabe jetzt False (H2-R3: abgelehnt = nichts
    geändert), das Original gab True zurück."""
    app, lab, _source = previewing
    snapshot = state_snapshot(app)
    plan = lab.preview
    assert lab_key_press(app, lab, inp) is False
    app.key_release(inp)
    assert lab.preview is plan
    assert app.status_message == PREVIEW_HINT
    assert app.transform_command is None
    assert state_snapshot(app) == snapshot


def test_select_is_ignored_during_preview(previewing):
    app, lab, _source = previewing
    snapshot = state_snapshot(app)
    other = first_visible(app, side_vertices(app, 1))
    assert click(app, *screen(app, other)) is False
    assert state_snapshot(app) == snapshot
    assert app.status_message == PREVIEW_HINT
    assert lab.preview_open


def test_paired_state_unaffected_by_preview(previewing):
    """Die Vorschau ändert weder Mesh noch Befund (magenta bleibt bis zum
    Ausführen)."""
    app, lab, _source = previewing
    assert len(lab.report.unpaired) == 54
    app.viewport.sync()
    assert len(lab.report.unpaired) == 54
