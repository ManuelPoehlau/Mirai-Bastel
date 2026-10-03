"""Symmetrie-Zyklus, Overlays und Assets auf dem App-Pfad (WP-SYM-LAB-03 S1b).

Portiert nach Plan §4.4 (`test_lab_symmetry`: die Zyklus-Tests laufen jetzt über
`lab_key_press` → `Application.apply_mesh_change` statt über `LabDispatcher`;
die Originale in `test_lab_symmetry.py` bleiben bis Slice 5 unverändert):

- off → X → Y → Z → off, je genau ein History-Eintrag, Undo stellt jede Definition her
- der Zyklus ändert weder Positionen noch Topologie
- die Auswahl bleibt
- die Seam ist gespeicherte Deklaration (E3), keine laufende Prüfung

Dazu: Ebenen-Umriss und Zustands-Marker als Viewport-Overlays (H1), Neuaufbau nach
Shift+S (eigenes `dirty`) und nach Undo (Viewport-Meldung), Assets per Registry-Name
und der Einstieg `run_app` (Exit-Code 2, `--help`).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from loaders.assets import asset_names
from mirai.mesh_geometry import mesh_bounds, mesh_center_and_radius
from mirai.symmetry import SymmetryState

from symmetry_lab import run_app
from symmetry_lab._paths import LAB_DIR
from symmetry_lab.lab_app import hud_text
from symmetry_lab.lab_overlays import (
    AMBIGUOUS_LAYER,
    SEAM_LAYER,
    UNPAIRED_LAYER,
    SymmetryPlaneOverlay,
    SymmetryStateOverlay,
)
from symmetry_lab.lab_symmetry import (
    AXIS_INDEX,
    AXIS_NORMALS,
    ORIGIN,
    current_axis,
    symmetry_report,
)

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


def _overlays(lab) -> tuple[SymmetryPlaneOverlay, SymmetryStateOverlay]:
    plane, state = lab.overlays
    assert isinstance(plane, SymmetryPlaneOverlay)
    assert isinstance(state, SymmetryStateOverlay)
    return plane, state


def _cycle_to(app, lab, axis):
    for _ in range(4):
        if lab.axis == axis:
            return
        assert press(app, lab, SHIFT_S)
    raise AssertionError(axis)


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
        assert app.status_message == f"Shift+S: Symmetrie {expected or 'aus'}"
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


def test_overlays_are_attached_in_draw_order(lab_app):
    app, lab = lab_app
    plane, state = _overlays(lab)
    assert app.viewport.extra_overlays == [plane, state]


def test_overlays_empty_while_symmetry_off(lab_app):
    app, lab = lab_app
    app.viewport.sync()
    plane, state = _overlays(lab)
    assert plane.segments() == []
    for layer in (SEAM_LAYER, UNPAIRED_LAYER, AMBIGUOUS_LAYER):
        assert state.points(layer) == []


@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
def test_plane_outline_lies_in_plane_and_encloses_bounds(axis):
    """Portierter Umriss-Test, jetzt über das Viewport-Overlay (head_basemesh)."""
    app, lab = make_lab("head_basemesh")
    _cycle_to(app, lab, axis)
    app.viewport.sync()
    plane, _state = _overlays(lab)
    segments = plane.segments()
    assert len(segments) == 4
    points = [p for seg in segments for p in seg]
    i = AXIS_INDEX[axis]
    assert all(p[i] == 0.0 for p in points)
    lo, hi = mesh_bounds(app.scene.mesh)
    for j in (j for j in range(3) if j != i):
        assert min(p[j] for p in points) < lo[j]
        assert max(p[j] for p in points) > hi[j]


@pytest.mark.parametrize(
    "asset,axis,seam,unpaired",
    [
        ("subd_cube", "X", 8, 0),  # 8 Seam-Edges = ein Ring aus 8 Vertices
        ("subd_cube", "Y", 0, 26),
        ("man_with_shoes_basemesh", "X", None, 54),
    ],
)
def test_state_markers_match_the_report(asset, axis, seam, unpaired):
    """Zustands-Marker = `symmetry_report` (README-Charakterisierung, E4: 54 ohne Partner)."""
    app, lab = make_lab(asset)
    _cycle_to(app, lab, axis)
    app.viewport.sync()
    _plane, state = _overlays(lab)
    mesh = app.scene.mesh
    report = symmetry_report(mesh)
    for layer, ids in (
        (SEAM_LAYER, report.seam),
        (UNPAIRED_LAYER, report.unpaired),
        (AMBIGUOUS_LAYER, report.ambiguous),
    ):
        assert state.points(layer) == [mesh.vertex_position(v) for v in sorted(ids)]
    assert len(state.points(UNPAIRED_LAYER)) == unpaired
    if seam is not None:
        assert len(state.points(SEAM_LAYER)) == seam


def test_overlays_resync_after_shift_s_via_own_dirty_flag(lab_app):
    """Ein reiner Definitionswechsel meldet dem Viewport nichts; das Lab setzt
    `dirty` selbst, der nächste `sync()` baut neu und setzt es zurück."""
    app, lab = lab_app
    app.viewport.sync()
    plane, state = _overlays(lab)
    assert press(app, lab, SHIFT_S)
    assert plane.dirty and state.dirty
    app.viewport.sync()
    assert not plane.dirty and not state.dirty
    assert len(plane.segments()) == 4
    assert len(state.points(SEAM_LAYER)) == 8


def test_overlays_resync_after_undo_redo_via_viewport_notification(lab_app):
    """Undo/Redo der Definition läuft durch `Application` (Viewport-Meldung), ohne
    dass das Lab `dirty` setzt — die Overlays folgen trotzdem."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    app.viewport.sync()
    plane, state = _overlays(lab)
    assert press(app, lab, CTRL_Z)
    assert not plane.dirty and not state.dirty
    app.viewport.sync()
    assert plane.segments() == []
    assert state.points(SEAM_LAYER) == []
    assert press(app, lab, CTRL_Y)
    app.viewport.sync()
    assert len(plane.segments()) == 4
    assert len(state.points(SEAM_LAYER)) == 8


def test_overlays_follow_a_committed_move(lab_app):
    """Ein W-Commit meldet bewegte Vertices; die Marker zeigen die neuen Positionen."""
    app, lab = lab_app
    assert press(app, lab, SHIFT_S)
    app.viewport.sync()
    _plane, state = _overlays(lab)
    mesh = app.scene.mesh
    vid = next(v for v in visible(app) if v in symmetry_report(mesh).seam)
    click(app, *screen(app, vid))
    arm_and_move(app, lab)
    assert app.key_release(W)
    app.viewport.sync()
    assert mesh.vertex_position(vid) in state.points(SEAM_LAYER)


def test_hud_text_shows_symmetry_and_status(lab_app):
    """Seit Slice 2 ist die HUD-Zeile die volle Zeile (`test_app_lab_hud.py`); die
    beiden Slice-1b-Teile — Symmetrie-Zustand und letzte Meldung — bleiben."""
    app, lab = lab_app
    assert "Symmetrie: aus (off)" in hud_text(app, "subd_cube", lab.report)
    assert press(app, lab, SHIFT_S)
    text = hud_text(app, "subd_cube", lab.report)
    assert "Symmetrie: X (valid)" in text
    assert text.endswith(" | Shift+S: Symmetrie X")


# -- Assets / Einstieg ----------------------------------------------------------------


def test_registry_matches_expected_assets():
    assert set(asset_names()) == set(EXPECTED_VERTEX_COUNTS)
    assert run_app.DEFAULT_ASSET == "subd_cube"


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


def test_run_app_rejects_unknown_name_before_opening_a_window(capsys):
    assert run_app.main(["no_such_mesh"]) == 2
    err = capsys.readouterr().err
    for name in asset_names():
        assert name in err


def test_run_app_help_runs_without_a_window():
    result = subprocess.run(
        [sys.executable, str(LAB_DIR / "run_app.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Registry-Name" in result.stdout
