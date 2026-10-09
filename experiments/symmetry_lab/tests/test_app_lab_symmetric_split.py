"""Symmetrischer Split über den Lab-Pfad (AD-SYM-03 Slice 4).

Mit den **echten** Deklarationen (`mirai.symmetry_declarations`, Split ist deklariert). Der
Koordinator selbst ist in `tests/test_symmetric_split.py` getestet; hier: `C` mit einer Kante geht
unter BLOCK durchs Gate und läuft in MARK und BLOCK gleich (Amendment: „Runtime refusals are not
G-3“), die leere Auswahl bleibt unter BLOCK mit dem Knife-Text abgelehnt (keine Session), eine
abgelehnte Taste lässt die Auswahl unberührt, das HUD bleibt `valid`.
"""

from __future__ import annotations

import pytest

from core import SelectionMode
from mirai.symmetric_ops import TEXT_UNPAIRED
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import SymmetryIndex, completeness_report

from symmetry_lab.lab_app import GateMode, block_row, block_text, e5_warning_text

from ._app_lab_support import C, CTRL_Y, CTRL_Z, MISS, SHIFT_B, SHIFT_S, make_lab, press, undeclare_knife

_COUNTERS = ("vertex_id_counter", "edge_id_counter", "face_id_counter")


def lab_on(mode: GateMode):
    """subd_cube, Symmetrie X über Shift+S, E5-Modus `mode`."""
    app, lab = make_lab()
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


def select_edges(app, edges) -> None:
    app.selection.clear()
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = set(edges)


def plus_x_edge(app):
    """Eine Kante ganz auf der +X-Seite, nicht auf der Naht."""
    mesh = app.scene.mesh
    for eid in sorted(mesh.all_edge_ids(), key=int):
        if all(mesh.vertex_position(v)[0] > 0.0 for v in mesh.edge_vertices(eid)):
            return eid
    raise AssertionError("keine Kante auf der +X-Seite")


def assert_valid(app, lab) -> None:
    mesh = app.scene.mesh
    report = completeness_report(mesh)
    assert not (report.unpaired_vertices | report.faces_without_partner | report.edges_without_partner)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert lab.report.state is SymmetryState.VALID


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_c_with_one_edge_splits_both_sides_as_one_undo_step(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    gate = app.command_gate
    select_edges(app, {plus_x_edge(app)})
    before = topology_state(app)
    selection_before = selection_state(app)
    vertices = set(mesh.all_vertex_ids())
    history = len(app.history)  # Shift+S hat schon einen Eintrag (Symmetrie-Definition)

    assert press(app, lab, C) is True
    assert app.status_message == "Split"
    assert len(app.history) == history + 1
    created = set(mesh.all_vertex_ids()) - vertices
    assert len(created) == 2
    assert_valid(app, lab)
    assert app.command_gate is gate  # keine Zeile pro Taste
    assert e5_warning_text(lab) == ""
    (selected,) = app.selection.vertices  # nur der neue Vertex der gewählten (+X-)Seite
    assert selected in created and mesh.vertex_position(selected)[0] > 0.0
    after = topology_state(app)
    after_selection = selection_state(app)

    assert press(app, lab, CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before
    assert selection_state(app) == selection_before
    assert lab.report.state is SymmetryState.VALID
    assert press(app, lab, CTRL_Y) is True
    assert topology_state(app) == after
    assert selection_state(app) == after_selection


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_a_mirror_pair_selected_splits_exactly_twice(mode):
    """A2 = A: Kante und Spiegelkante sind eine Absicht, kein doppeltes Teilen, beide neuen
    Vertices ausgewählt."""
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    edge = plus_x_edge(app)
    partner = SymmetryIndex(mesh).edge_partner(edge)
    assert partner is not None and partner != edge
    select_edges(app, {edge, partner})
    vertices = set(mesh.all_vertex_ids())
    edges = len(mesh.all_edge_ids())

    assert press(app, lab, C) is True
    created = set(mesh.all_vertex_ids()) - vertices
    assert len(created) == 2
    assert len(mesh.all_edge_ids()) == edges + 2
    assert set(app.selection.vertices) == created
    assert_valid(app, lab)


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_a_seam_edge_is_split_once_and_the_new_vertex_is_a_seam_vertex(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    seam = mesh.symmetry_definition.seam_edges
    old = next(e for e in sorted(seam, key=int) if len(mesh.edge_faces(e)) == 2)
    select_edges(app, {old})
    vertices = set(mesh.all_vertex_ids())
    before = topology_state(app)

    assert press(app, lab, C) is True
    (new_vertex,) = set(mesh.all_vertex_ids()) - vertices
    assert mesh.vertex_position(new_vertex)[0] == 0.0
    assert old not in mesh.symmetry_definition.seam_edges
    assert len(mesh.symmetry_definition.seam_edges) == len(seam) + 1
    assert set(app.selection.vertices) == {new_vertex}
    assert_valid(app, lab)  # die Naht bleibt durchgehend: der neue Vertex ist ein Seam-Vertex

    assert press(app, lab, CTRL_Z) is True
    assert topology_state(app) == before
    assert mesh.symmetry_definition.seam_edges == seam


def test_the_empty_selection_under_block_is_refused_with_the_knife_text_while_undeclared(monkeypatch):
    undeclare_knife(monkeypatch)    # seit Slice 6c ist der Knife-Kontext deklariert
    app, lab = lab_on(GateMode.BLOCK)
    app.selection.clear()
    before = (topology_state(app), selection_state(app), len(app.history))
    serial = app.status_serial
    assert press(app, lab, C) is False
    assert app.status_serial == serial + 1
    assert app.status_message == block_text("Knife")
    assert not app.knife_active
    assert (topology_state(app), selection_state(app), len(app.history)) == before
    assert len(block_row().gate.refused_contexts) == 1  # nur Knife: die Zeile ist abgeleitet


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_a_refused_press_leaves_the_selection_untouched(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    edge = plus_x_edge(app)
    vertex = mesh.edge_vertices(edge)[0]
    x, y, z = mesh.vertex_position(vertex)
    mesh.set_vertex_position(vertex, (x + 0.01, y, z))  # die Kante verliert den Partner
    select_edges(app, {edge})
    before = (topology_state(app), selection_state(app), len(app.history))
    serial = app.status_serial
    for n in (1, 2):
        assert press(app, lab, C) is False
        assert app.status_serial == serial + n
        assert app.status_message == TEXT_UNPAIRED
    assert (topology_state(app), selection_state(app), len(app.history)) == before
    assert app.selection.mode is SelectionMode.EDGE
