"""Symmetrisches Delete, Dissolve und Dissolve (no cleanup) über den Lab-Pfad (AD-SYM-03 Slice 3c).

Mit den **echten** Deklarationen (`mirai.symmetry_declarations`). Der Koordinator selbst ist in
`tests/test_symmetric_removal.py` getestet; hier: die abgeleitete BLOCK-Zeile erlaubt die drei
Befehle (das Interim `INTERIM_ONE_SIDED` ist weg), `lab_key_press` Ende-zu-Ende unter BLOCK und MARK
(eine Undo-Stufe, symmetrisches Ergebnis, HUD `valid`, Undo/Redo), die Laufzeit-Ablehnungen sind in
MARK wie in BLOCK dieselben („Runtime refusals are not G-3“), der Nahtfall Delete (A1 Fall 1) läuft,
Dissolve an der Naht (Fall 2) wird mit eigenem Text abgelehnt, und ohne Symmetrie läuft alles einseitig
wie früher.
"""

from __future__ import annotations

import pytest

from core import SelectionMode
from mirai import symmetry_declarations as declarations
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_ops import TEXT_SEAM_DISSOLVE, TEXT_UNPAIRED
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import SymmetryIndex, completeness_report

from symmetry_lab.lab_app import GateMode, block_row, hud_text

from ._app_lab_support import (  # noqa: F401
    CTRL_Y,
    CTRL_Z,
    MISS,
    SHIFT_B,
    SHIFT_S,
    forbid_lab_calls,
    make_lab,
    press,
)

DELETE = Input("key", "delete")
DISSOLVE = Input("key", "backspace")
DISSOLVE_NO_CLEANUP = Input("key", "backspace", frozenset({"ctrl"}))
REMOVAL_KEYS = {DELETE: cmd.DELETE, DISSOLVE: cmd.DISSOLVE, DISSOLVE_NO_CLEANUP: cmd.DISSOLVE_NO_CLEANUP}

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
_COUNTERS = ("vertex_id_counter", "edge_id_counter", "face_id_counter")
MODES = [GateMode.BLOCK, GateMode.MARK]
MODE_IDS = ["block", "mark"]


def lab_on(mode: GateMode, asset: str = "subd_cube", *, symmetric: bool = True):
    """`asset`, Symmetrie X über Shift+S, E5-Modus `mode`."""
    app, lab = make_lab(asset)
    if symmetric:
        if lab.gate_mode is not mode:
            assert press(app, lab, SHIFT_B)
        assert lab.gate_mode is mode
        assert press(app, lab, SHIFT_S) and lab.axis == "X"
    app.pointer_motion(*MISS)
    return app, lab


def topology_state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if k not in _COUNTERS}


def selection_state(app) -> tuple:
    s = app.selection
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces))


def select(app, mode, ids) -> None:
    app.selection.clear()
    app.selection.mode = mode
    setattr(app.selection, {V: "vertices", E: "edges", F: "faces"}[mode], set(ids))


def plus_x_quad(app):
    """A +X quad away from the seam (no vertex on x = 0)."""
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > 1e-9 for v in vids):
            return fid
    raise AssertionError("keine Quad-Face ganz auf der +X-Seite")


def far_selection(app, mode, dissolve: bool):
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    if mode is V:
        return {mesh.face_vertices(quad)[0]}
    if mode is E:
        return {mesh.face_edges(quad)[0]}
    if not dissolve:
        return {quad}
    for e in mesh.face_edges(quad):  # a neighbouring +X face to merge with
        for g in mesh.edge_faces(e):
            if g != quad and all(mesh.vertex_position(v)[0] > 1e-9 for v in mesh.face_vertices(g)):
                return {quad, g}
    raise AssertionError("keine Nachbar-Face auf der +X-Seite")


def seam_pair(app):
    mesh = app.scene.mesh
    edge = next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)
    return edge, set(mesh.edge_faces(edge))


def assert_clean(app) -> None:
    mesh = app.scene.mesh
    report = completeness_report(mesh)
    assert not (report.unpaired_vertices | report.faces_without_partner | report.edges_without_partner)
    assert not (report.self_mirrored_faces | report.dead_seam_ids)
    assert symmetry_state(mesh) is SymmetryState.VALID


# -- die abgeleitete BLOCK-Zeile ---------------------------------------------------------------


def test_block_row_allows_the_three_removal_commands_through_their_declarations():
    gate = block_row().gate
    removal = {cmd.DELETE, cmd.DISSOLVE, cmd.DISSOLVE_NO_CLEANUP}
    assert declarations.declared_removal_commands() == removal
    assert removal <= gate.allowed
    assert all(gate.refusal(command) is None for command in removal)


# -- Ende zu Ende über lab_key_press -----------------------------------------------------------


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("key", list(REMOVAL_KEYS), ids=["delete", "dissolve", "dissolve_no_cleanup"])
@pytest.mark.parametrize("component", [V, E, F], ids=["vertex", "edge", "face"])
@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_removal_runs_symmetric_as_one_undo_step_in_block_and_mark(asset, component, key, mode):
    if key is DISSOLVE_NO_CLEANUP and component is V:
        pytest.skip("Vertex Dissolve hat keine Variante")
    app, lab = lab_on(mode, asset)
    dissolve = key is not DELETE
    select(app, component, far_selection(app, component, dissolve))
    before = topology_state(app)
    selection_before = selection_state(app)
    definition = app.scene.mesh.symmetry_definition
    gate = app.command_gate
    history = len(app.history)  # Shift+S hat schon einen Eintrag (Symmetrie-Definition)

    assert press(app, lab, key) is True
    assert len(app.history) == history + 1
    assert_clean(app)
    assert "valid" in hud_text(app, asset, lab.report)
    assert app.command_gate is gate  # keine Zeile pro Taste
    after = topology_state(app)
    assert after != before

    assert press(app, lab, CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before
    assert selection_state(app) == selection_before
    assert app.scene.mesh.symmetry_definition == definition
    assert press(app, lab, CTRL_Y) is True
    assert topology_state(app) == after


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_delete_removes_the_element_on_both_sides(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    partner = SymmetryIndex(mesh).face_partner(quad)
    assert partner is not None and partner != quad
    select(app, F, {quad})
    assert press(app, lab, DELETE) is True
    assert not mesh.is_valid_face(quad) and not mesh.is_valid_face(partner)
    assert app.status_message == "Delete Faces"


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_delete_of_a_face_pair_at_the_seam_keeps_the_hud_valid_and_undo_restores_the_seam(mode):
    """A1 Fall 1 (Manu: M): die Naht verschwindet nur, wo die angrenzenden Faces weg sind."""
    app, lab = lab_on(mode, "head_basemesh")
    seam_before = app.scene.mesh.symmetry_definition.seam_edges
    seam_edge, pair = seam_pair(app)
    select(app, F, pair)
    before = topology_state(app)

    assert press(app, lab, DELETE) is True
    mesh = app.scene.mesh
    assert not mesh.is_valid_edge(seam_edge) and seam_edge not in mesh.symmetry_definition.seam_edges
    assert mesh.symmetry_definition.seam_edges < seam_before
    assert_clean(app)
    assert "valid" in hud_text(app, "head_basemesh", lab.report)

    assert press(app, lab, CTRL_Z) is True
    assert topology_state(app) == before
    assert mesh.symmetry_definition.seam_edges == seam_before


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("key", [DISSOLVE, DISSOLVE_NO_CLEANUP], ids=["dissolve", "dissolve_no_cleanup"])
def test_dissolve_of_a_seam_edge_is_refused_with_its_text_in_block_and_mark(key, mode):
    """A1 Fall 2 (UNKNOWN): verweigert, nichts ändert sich."""
    app, lab = lab_on(mode, "head_basemesh")
    seam_edge, _pair = seam_pair(app)
    select(app, E, {seam_edge})
    before = (topology_state(app), selection_state(app), len(app.history), app.scene.mesh.symmetry_definition)
    serial = app.status_serial
    assert press(app, lab, key) is False
    assert app.status_message == TEXT_SEAM_DISSOLVE
    assert app.status_serial == serial + 1
    assert (
        topology_state(app),
        selection_state(app),
        len(app.history),
        app.scene.mesh.symmetry_definition,
    ) == before


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("key", list(REMOVAL_KEYS), ids=["delete", "dissolve", "dissolve_no_cleanup"])
def test_an_unpaired_selection_is_refused_visibly_in_block_and_mark(key, mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    vertex = mesh.face_vertices(quad)[0]
    x, y, z = mesh.vertex_position(vertex)
    mesh.set_vertex_position(vertex, (x + 0.01, y, z))  # die Ecke und ihre Kanten verlieren den Partner
    select(app, E, {e for e in mesh.face_edges(quad) if vertex in mesh.edge_vertices(e)})
    before = (topology_state(app), selection_state(app), len(app.history))
    serial = app.status_serial
    for n in (1, 2):
        assert press(app, lab, key) is False
        assert app.status_serial == serial + n
        assert app.status_message == TEXT_UNPAIRED
    assert (topology_state(app), selection_state(app), len(app.history)) == before


@pytest.mark.parametrize("key", list(REMOVAL_KEYS), ids=["delete", "dissolve", "dissolve_no_cleanup"])
def test_with_symmetry_off_removal_runs_one_sided_as_before(key):
    app, lab = lab_on(GateMode.BLOCK, symmetric=False)
    assert lab.axis is None and app.scene.mesh.symmetry_definition is None
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    edge = mesh.face_edges(quad)[0]
    select(app, E, {edge})
    mirrored = {tuple(sorted((-x, y, z) for x, y, z in map(mesh.vertex_position, mesh.edge_vertices(edge))))}
    mirror = next(
        e for e in mesh.all_edge_ids()
        if tuple(sorted(map(mesh.vertex_position, mesh.edge_vertices(e)))) in mirrored
    )
    assert press(app, lab, key) is True
    assert not mesh.is_valid_edge(edge) and mesh.is_valid_edge(mirror)  # one-sided: the mirror edge stays
    assert len(app.history) == 1
    assert app.scene.mesh.symmetry_definition is None
