"""Symmetrie-Zyklus, Overlays und Assets auf dem App-Pfad (WP-SYM-LAB-03 S1b).

Portiert nach Plan §4.4 (`test_lab_symmetry`: die Zyklus-Tests laufen jetzt über
`lab_key_press` → `Application`, seit AD-SYM-04 A1 deren Shift+S-Befehl, statt über `LabDispatcher`;
die Originale in `test_lab_symmetry.py` sind seit Slice 5 gelöscht, Plan A2-Tabelle):

- off → X → Y → Z → off, je genau ein History-Eintrag, Undo stellt jede Definition her
- der Zyklus ändert weder Positionen noch Topologie
- die Auswahl bleibt
- die Seam ist gespeicherte Deklaration (E3), keine laufende Prüfung

Dazu: das Symmetrie-Overlay der App im Lab (seit AD-SYM-04 A2 zeichnet die App Ebene und
Zustands-Marker; deren Sync-Tests stehen in `tests/test_application_symmetry_display.py`),
Assets per Registry-Name und der Einstieg `run` (Exit-Code 2, `--help`).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from loaders.assets import asset_names
from mirai.application import symmetry_status_text
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.symmetry import SymmetryState
from mirai.symmetry_axis import AXIS_NORMALS, ORIGIN, current_axis
from mirai.symmetry_display import SymmetryDisplay, symmetry_report
from viewport.gl_symmetry_overlay import SEAM_LAYER, GLSymmetryOverlay

from symmetry_lab import run
from symmetry_lab._paths import LAB_DIR
from symmetry_lab.lab_app import hud_text
from symmetry_lab.lab_overlays import LabPointOverlay, ResymPreviewLineOverlay

from ._app_lab_support import (  # noqa: F401
    CTRL_Y,
    CTRL_Z,
    SHIFT_S,
    W,
    arm_and_move,
    click,
    forbid_lab_calls,
    lab_app,
    make_lab,
    press,
    screen,
    visible,
)

EXPECTED_VERTEX_COUNTS = {
    "head_basemesh": 326,
    "man_with_shoes_basemesh": 928,
    "subd_cube": 26,
}
#: Registrierte Assets, die das Lab vorerst bewusst nicht abdeckt (Symmetrie nicht geprüft).
LAB_EXCLUDED_ASSETS = {"gollum"}


# -- Zyklus (portiert) ------------------------------------------------------------


def test_cycle_off_x_y_z_off_one_history_entry_each(lab_app):
    """Portiert: Shift+S off → X → Y → Z → off, je ein Undo-Schritt (`Symmetry <axis>`);
    Ctrl+Z stellt jede vorherige Definition exakt wieder her."""
    app, lab = lab_app
    mesh = app.scene.mesh
    seen = [mesh.symmetry_definition]
    for step, expected in enumerate(["X", "Y", "Z", None], start=1):
        assert press(app, lab, SHIFT_S) is True
        assert current_axis(mesh) == expected
        if expected is None:
            assert mesh.symmetry_definition is None
        else:
            assert mesh.symmetry_definition.plane_normal == AXIS_NORMALS[expected]
            assert mesh.symmetry_definition.plane_point == ORIGIN
        assert len(app.history) == step
        assert app.history._undo_stack[-1].description == f"Symmetry {expected or 'off'}"
        assert app.status_message == symmetry_status_text(mesh)  # die Statuszeile der App (S-1)
        seen.append(mesh.symmetry_definition)

    for step in range(4, 0, -1):
        assert press(app, lab, CTRL_Z)
        assert mesh.symmetry_definition == seen[step - 1]
        assert len(app.history) == step - 1


def test_cycle_does_not_touch_positions_or_topology():
    """Portiert: nur die Definition ändert sich (head_basemesh)."""
    app, lab = make_lab("head_basemesh")
    before = app.scene.mesh.export_state()
    assert press(app, lab, SHIFT_S)
    after = app.scene.mesh.export_state()
    assert after["symmetry"] is not None
    assert {k: v for k, v in after.items() if k != "symmetry"} == {
        k: v for k, v in before.items() if k != "symmetry"
    }


def test_cycle_keeps_selection(lab_app):
    """Portiert: Shift+S lässt die Auswahl stehen; Undo/Redo ebenso."""
    app, lab = lab_app
    vid = visible(app)[0]
    click(app, *screen(app, vid))
    assert app.selection.vertices == {vid}
    assert press(app, lab, SHIFT_S)
    assert app.selection.vertices == {vid}
    assert press(app, lab, CTRL_Z)
    assert app.selection.vertices == {vid}
    assert press(app, lab, CTRL_Y)
    assert app.selection.vertices == {vid}


def test_seam_is_stored_declaration_not_live_check(lab_app):
    """Portiert (E3): nach Shift+S über den App-Pfad wird die Seam nicht neu
    geprüft — ein Seam-Vertex, der die Ebene verlässt, bleibt Seam und zeigt sich
    als VIOLATED."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    mesh = app.scene.mesh
    seam = mesh.symmetry_definition.seam_edges
    vid = mesh.edge_vertices(next(iter(seam)))[0]
    x, y, z = mesh.vertex_position(vid)
    # Direkt am Mesh wie im Original: geprüft wird die Definition, nicht die
    # Move-Regel (W hält Seam-Vertices in der Ebene).
    mesh.set_vertex_position(vid, (x + 0.25, y, z))
    assert mesh.symmetry_definition.seam_edges == seam
    assert symmetry_report(mesh).state is SymmetryState.VIOLATED


def test_symmetric_move_runs_through_src(lab_app):
    """Symmetrisches W kommt aus `src` (`MoveTool`), ohne Lab-Code: der Partner bewegt
    sich gespiegelt mit, ein Commit = ein Undo-Schritt."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    mesh = app.scene.mesh
    report = symmetry_report(mesh)
    vid = next(v for v in visible(app) if v not in report.seam and v not in report.unpaired)
    click(app, *screen(app, vid))
    before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    arm_and_move(app, lab)
    assert app.key_release(W)
    moved = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) != before[v]}
    assert vid in moved and len(moved) == 2
    (partner,) = moved - {vid}
    px, py, pz = mesh.vertex_position(partner)
    vx, vy, vz = mesh.vertex_position(vid)
    assert (px, py, pz) == (-vx, vy, vz)
    assert len(app.history) == 2


# -- Overlays (H1) ----------------------------------------------------------------
#
# Ebenen-Umriss und Zustands-Marker zeichnet seit AD-SYM-04 A2 die App (`mirai.symmetry_display`,
# Senke `GLSymmetryOverlay` über `GL_TYPES`). Ihre Sync-Tests (Umriss in der Ebene, Marker =
# Befund, Neuaufbau nach Shift+S, Undo/Redo und Move-Commit, Aufschub während des Drags) sind mit
# dem Code nach `tests/test_application_symmetry_display.py` gezogen. Hier bleibt, was das Lab
# betrifft: es bekommt das Overlay der App genau einmal und zeichnet nichts davon selbst (L-9).


def test_the_app_draws_plane_and_markers_once_the_lab_adds_only_its_own(lab_app):
    app, lab = lab_app
    display = app.symmetry_display
    assert isinstance(display, SymmetryDisplay)
    assert app.viewport.extra_overlays == [display, *lab.overlays]
    assert [type(o) for o in lab.overlays] == [ResymPreviewLineOverlay, LabPointOverlay]
    lab_layers = {layer for o in lab.overlays for layer in o.LAYERS}
    assert not lab_layers & set(GLSymmetryOverlay.LAYER_STYLES)


def test_app_markers_follow_the_shift_s_the_lab_forwards(lab_app):
    """Shift+S über den Lab-Pfad (`lab_key_press` → `Application`): das Overlay der App folgt (K-3),
    Ctrl+Z ebenso; das Lab setzt dafür kein `dirty`."""
    app, lab = lab_app
    sink = app.symmetry_display.sink
    assert press(app, lab, SHIFT_S)
    app.viewport.sync()
    assert len(sink.segments()) == 4
    assert len(sink.points(SEAM_LAYER)) == 8
    assert press(app, lab, CTRL_Z)
    app.viewport.sync()
    assert sink.segments() == []
    assert sink.points(SEAM_LAYER) == []


def test_hud_text_shows_symmetry_and_status(lab_app):
    """Seit Slice 2 ist die HUD-Zeile die volle Zeile (`test_app_lab_hud.py`); die
    beiden Slice-1b-Teile — Symmetrie-Zustand und letzte Meldung — bleiben."""
    app, lab = lab_app
    assert "Symmetrie: aus (off)" in hud_text(app, "subd_cube", lab.report)
    assert press(app, lab, SHIFT_S)
    text = hud_text(app, "subd_cube", lab.report)
    assert "Symmetrie: X (valid)" in text
    assert text.endswith(" | Symmetrie X (valid)")


# -- Assets / Einstieg ----------------------------------------------------------------


def test_registry_matches_expected_assets():
    assert set(asset_names()) - LAB_EXCLUDED_ASSETS == set(EXPECTED_VERTEX_COUNTS)
    assert run.DEFAULT_ASSET == "subd_cube"


@pytest.mark.parametrize("name", sorted(EXPECTED_VERTEX_COUNTS))
def test_load_by_registry_name_on_the_app_path(name):
    """Portiert (`test_lab_scene`): Asset über `init_scene("obj", asset_path(name))`
    + `frame_scene()`; Auswahl leer im Vertex-Modus, Symmetrie aus, kein Gate."""
    app, lab = make_lab(name)
    mesh = app.scene.mesh
    assert len(mesh.all_vertex_ids()) == EXPECTED_VERTEX_COUNTS[name]
    center, _radius = mesh_center_and_radius(mesh)
    assert app.camera.target == center
    assert app.selection.is_empty()
    assert app.selection.mode.name == "VERTEX"
    assert lab.axis is None
    assert app.command_gate is None
    assert len(app.history) == 0


def test_run_rejects_unknown_name_before_opening_a_window(capsys):
    assert run.main(["no_such_mesh"]) == 2
    err = capsys.readouterr().err
    for name in asset_names():
        assert name in err


def test_run_help_runs_without_a_window():
    result = subprocess.run(
        [sys.executable, str(LAB_DIR / "run.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Registry-Name" in result.stdout
