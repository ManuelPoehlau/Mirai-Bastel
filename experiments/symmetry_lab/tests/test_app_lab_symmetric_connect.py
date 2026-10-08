"""Symmetrisches Edge Connect und Vertex Connect über den Lab-Pfad (AD-SYM-03 Slice 3b).

Mit den **echten** Deklarationen (`mirai.symmetry_declarations`: Edge und Vertex Connect). Die
Koordinatoren selbst sind in `tests/test_symmetric_ops.py` getestet; hier: die abgeleitete BLOCK-Zeile,
`lab_key_press` Ende-zu-Ende unter BLOCK und MARK (eine Undo-Stufe, symmetrisches Ergebnis, Undo/Redo),
die Laufzeit-Ablehnungen sind in MARK wie in BLOCK dieselben (Amendment: „Runtime refusals are not
G-3“), Split und Knife bleiben unter BLOCK mit ihrem Namen abgelehnt, die Knife-MARK-Warnzeile ist
unverändert (Knife undeklariert).
"""

from __future__ import annotations

import pytest

from core import SelectionMode
from mirai import symmetry_declarations as declarations
from mirai.interaction import commands as cmd
from mirai.symmetric_ops import (
    TEXT_BOTH_SIDES_FACE,
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
)
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import completeness_report
from mirai.topology.contextual_c import CContext

from symmetry_lab.lab_app import (
    CONTEXT_NAMES,
    KNIFE_ONE_SIDED_TEXT,
    GateMode,
    block_row,
    block_text,
    e5_warning_text,
)

from ._app_lab_support import (  # noqa: F401
    C,
    CTRL_Y,
    CTRL_Z,
    ESC,
    MISS,
    SHIFT_B,
    SHIFT_S,
    forbid_lab_calls,
    make_lab,
    press,
)

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


def plus_x_quad(app):
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > 1e-9 for v in vids):
            return fid, vids
    raise AssertionError("keine Quad-Face ganz auf der +X-Seite")


def select_opposite_edges(app) -> None:
    fid, _vids = plus_x_quad(app)
    edges = app.scene.mesh.face_edges(fid)
    app.selection.clear()
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = {edges[0], edges[2]}


def select_diagonal(app) -> None:
    _fid, vids = plus_x_quad(app)
    app.selection.clear()
    app.selection.mode = SelectionMode.VERTEX
    app.selection.vertices = {vids[0], vids[2]}


def assert_clean(app) -> None:
    mesh = app.scene.mesh
    report = completeness_report(mesh)
    assert not (report.unpaired_vertices | report.faces_without_partner | report.edges_without_partner)
    assert not (report.self_mirrored_faces | report.dead_seam_ids)
    assert symmetry_state(mesh) is SymmetryState.VALID


# -- die abgeleitete BLOCK-Zeile ---------------------------------------------------------------


def test_the_real_declarations_are_edge_and_vertex_connect_only():
    assert declarations.declared_c_contexts() == {CContext.EDGE_CONNECT, CContext.VERTEX_CONNECT}
    assert declarations.declared_removal_commands() == frozenset()


def test_block_row_with_the_real_declarations_allows_connect_and_names_split_and_knife():
    gate = block_row().gate
    assert cmd.CONNECT in gate.allowed
    assert dict(gate.refused) == {}
    assert dict(gate.refused_contexts) == {
        CContext.SPLIT: block_text("Split"),
        CContext.KNIFE: block_text("Knife"),
    }
    assert CContext.EDGE_CONNECT not in gate.refused_contexts
    assert CContext.VERTEX_CONNECT not in gate.refused_contexts
    assert set(CONTEXT_NAMES) - set(gate.refused_contexts) == declarations.declared_c_contexts()


# -- Ende zu Ende über lab_key_press -----------------------------------------------------------


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
@pytest.mark.parametrize("kind", ["edge", "vertex"])
def test_connect_runs_symmetric_as_one_undo_step_in_block_and_mark(kind, mode):
    app, lab = lab_on(mode)
    (select_opposite_edges if kind == "edge" else select_diagonal)(app)
    before = topology_state(app)
    selection_before = selection_state(app)
    gate = app.command_gate
    history = len(app.history)  # Shift+S hat schon einen Eintrag (Symmetrie-Definition)

    assert press(app, lab, C) is True
    assert app.status_message == ("Connect Edges" if kind == "edge" else "Vertex Connect")
    assert len(app.history) == history + 1
    assert_clean(app)
    assert app.command_gate is gate  # keine Zeile pro Taste
    after = topology_state(app)
    assert after != before

    assert press(app, lab, CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before
    assert selection_state(app) == selection_before
    assert press(app, lab, CTRL_Y) is True
    assert topology_state(app) == after


def edge_sides(app, edges) -> set:
    mesh = app.scene.mesh
    out = set()
    for e in edges:
        total = sum(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(e))
        out.add((total > 0) - (total < 0))
    return out


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_residue_is_the_created_edges_on_the_side_worked_on_or_on_both_sides(mode):
    """Artist ITERATE 2026-10-08: one side selected -> that side's created edges; both sides
    selected on purpose -> the created edges of both; Undo restores the selection."""
    app, lab = lab_on(mode)
    select_opposite_edges(app)
    one_sided = set(app.selection.edges)
    selection_before = selection_state(app)
    assert press(app, lab, C) is True
    assert edge_sides(app, app.selection.edges) == {1}
    assert press(app, lab, CTRL_Z) is True
    assert selection_state(app) == selection_before

    from mirai.symmetry_coordination import SymmetryIndex

    index = SymmetryIndex(app.scene.mesh)
    app.selection.edges = one_sided | {index.edge_partner(e) for e in one_sided}
    assert press(app, lab, C) is True
    assert edge_sides(app, app.selection.edges) == {1, -1}


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_split_and_knife_contexts_stay_unsupported(mode):
    """BLOCK: benannt abgelehnt. MARK: laufen weiter einseitig (hier: Split der einen Kante)."""
    app, lab = lab_on(mode)
    fid, _ = plus_x_quad(app)
    edge = app.scene.mesh.face_edges(fid)[0]
    app.selection.clear()
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = {edge}
    vertices = len(app.scene.mesh.all_vertex_ids())
    if mode is GateMode.BLOCK:
        before = (topology_state(app), selection_state(app), len(app.history))
        assert press(app, lab, C) is False
        assert app.status_message == block_text("Split")
        assert (topology_state(app), selection_state(app), len(app.history)) == before

        app.selection.clear()
        assert press(app, lab, C) is False
        assert app.status_message == block_text("Knife")
        assert not app.knife_active
    else:
        assert press(app, lab, C) is True
        assert app.status_message == "Split"
        assert len(app.scene.mesh.all_vertex_ids()) == vertices + 1


def test_knife_mark_warning_line_is_unchanged():
    """Knife ist undeklariert: die MARK-Session läuft einseitig und warnt wie vor 3b; Edge und
    Vertex Connect (deklariert) geben keine Warnzeile."""
    app, lab = lab_on(GateMode.MARK)
    select_opposite_edges(app)
    assert press(app, lab, C) is True
    assert e5_warning_text(lab) == ""  # sofortiges, koordiniertes Connect: keine Interaktion
    app.selection.clear()
    assert press(app, lab, C) is True and app.knife_active
    assert e5_warning_text(lab) == KNIFE_ONE_SIDED_TEXT
    assert press(app, lab, ESC) is True
    assert not app.knife_active


# -- Laufzeit-Ablehnungen: in BLOCK wie in MARK dieselben ---------------------------------------


def displace(app) -> None:
    """Eine +X-Ecke verschieben: sie und ihre Kanten verlieren den Partner."""
    mesh = app.scene.mesh
    _fid, vids = plus_x_quad(app)
    x, y, z = mesh.vertex_position(vids[0])
    mesh.set_vertex_position(vids[0], (x + 0.01, y, z))


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
@pytest.mark.parametrize("kind", ["edge", "vertex"])
def test_unpaired_selection_is_refused_visibly_in_block_and_mark(kind, mode):
    app, lab = lab_on(mode)
    displace(app)
    (select_opposite_edges if kind == "edge" else select_diagonal)(app)
    before = (topology_state(app), selection_state(app), len(app.history))
    serial = app.status_serial
    for n in (1, 2):
        assert press(app, lab, C) is False
        assert app.status_serial == serial + n
        assert app.status_message == TEXT_UNPAIRED
    assert (topology_state(app), selection_state(app), len(app.history)) == before


def test_refusal_texts_are_distinct_and_say_what_to_do():
    texts = [TEXT_UNPAIRED, TEXT_BOTH_SIDES_FACE, TEXT_NON_EXACT_PLANE, TEXT_DELTA]
    assert len(set(texts)) == 4
    assert all(text.startswith("Symmetrie:") and "Shift+S" in text for text in texts)
