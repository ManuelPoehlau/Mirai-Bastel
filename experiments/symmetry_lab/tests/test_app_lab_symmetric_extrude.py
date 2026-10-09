"""Symmetrischer Extrude (`T` halten) über den Lab-Pfad (AD-SYM-03 Slice 7, WP-SYM-EXTRUDE-01).

Mit den **echten** Deklarationen (`mirai.symmetry_declarations.EXTRUDE_COORDINATORS`). Der Planer und das
Werkzeug sind in `tests/test_symmetric_extrude.py` getestet; hier: die Deklaration schaltet die BLOCK-Zeile frei
(Extrude war eines der sechs nicht verdrahteten Commands), MARK zeigt keine Einseitig-Warnzeile mehr (der
Mechanismus folgt der Deklaration und ist mit einer undeklarierten Tabelle getestet), `T` unter Symmetrie in BLOCK
und MARK = koordiniert, eine Undo-Stufe, Auswahl auf der Arbeitsseite (Engineering-Default, kein Artist-Verdikt),
die Laufzeit-Ablehnungen sind in MARK wie in BLOCK dieselben, und ohne Symmetrie läuft `T` einseitig wie in B9.
"""

from __future__ import annotations

import pytest

from core import SelectionMode
from mirai import symmetry_declarations as declarations
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_extrude import TEXT_EXTRUDE_SPANNING
from mirai.symmetric_ops import TEXT_UNPAIRED
from mirai.symmetry import SymmetryState
from mirai.symmetry_coordination import SymmetryIndex, completeness_report

from symmetry_lab.lab_app import (
    BLOCK_NOT_ALLOWED_TEXT,
    GateMode,
    block_row,
    e5_warning_text,
    one_sided_text,
)

from ._app_lab_support import (  # noqa: F401
    CTRL_Y,
    CTRL_Z,
    MISS,
    SHIFT_B,
    SHIFT_S,
    declare,
    forbid_lab_calls,
    make_lab,
    press,
)

T = Input("key", "t")
ESC = Input("key", "ESCAPE")
F = SelectionMode.FACE
_COUNTERS = ("vertex_id_counter", "edge_id_counter", "face_id_counter")
MODES = [GateMode.BLOCK, GateMode.MARK]
MODE_IDS = ["block", "mark"]


def lab_on(mode: GateMode, asset: str = "head_basemesh", *, symmetric: bool = True):
    """`asset`, Symmetrie X über Shift+S, E5-Modus `mode`, Face-Modus."""
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


def state(app) -> tuple:
    s = app.selection
    return (topology_state(app), len(app.history), s.mode, frozenset(s.faces))


def select_faces(app, *faces) -> None:
    app.selection.clear()
    app.selection.mode = F
    app.selection.faces = set(faces)


def plus_x_face(app, *, seam: bool = False):
    """A +X quad away from the seam (`seam=False`) or with an edge on it."""
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        xs = [mesh.vertex_position(v)[0] for v in mesh.face_vertices(fid)]
        on = sum(1 for x in xs if x == 0.0)
        if len(xs) == 4 and min(xs) >= 0.0 and max(xs) > 0.0 and on == (2 if seam else 0):
            return fid
    raise AssertionError("keine passende +X-Quad")


def drag_t(app, lab, steps: int = 4, dx: float = 30.0, dy: float = 20.0) -> bool:
    assert press(app, lab, T)
    x, y = 400.0, 300.0
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)
    return app.key_release(T)


def assert_clean(app, lab) -> None:
    report = completeness_report(app.scene.mesh)
    assert not (report.unpaired_vertices | report.faces_without_partner | report.edges_without_partner)
    assert not (report.self_mirrored_faces | report.dead_seam_ids)
    assert lab.report.state is SymmetryState.VALID


# -- the declaration is the switch ------------------------------------------------------------


def test_extrude_is_declared_and_the_block_row_allows_it():
    assert declarations.declared_extrude_commands() == frozenset({cmd.EXTRUDE})
    gate = block_row().gate
    assert cmd.EXTRUDE in gate.allowed
    assert gate.refusal(cmd.EXTRUDE) is None


def test_without_the_declaration_block_refuses_extrude_visibly_and_the_row_follows_the_table(monkeypatch):
    app, lab = lab_on(GateMode.BLOCK)
    assert cmd.EXTRUDE in block_row().gate.allowed
    declare(monkeypatch)                         # nothing declared: the state before slice 7
    gate = block_row().gate
    assert cmd.EXTRUDE not in gate.allowed
    assert gate.refusal(cmd.EXTRUDE) == BLOCK_NOT_ALLOWED_TEXT
    lab.sync_gate()
    select_faces(app, plus_x_face(app))
    before = state(app)
    assert press(app, lab, T) is False
    assert app.status_message == BLOCK_NOT_ALLOWED_TEXT
    assert state(app) == before and app.transform_command is None


def test_no_warning_line_for_a_declared_extrude_and_one_for_an_undeclared_one_in_mark(monkeypatch):
    app, lab = lab_on(GateMode.MARK)
    select_faces(app, plus_x_face(app))
    assert press(app, lab, T)
    assert app.transform_command == cmd.EXTRUDE
    assert e5_warning_text(lab) == ""            # declared: nothing runs one-sided
    assert app.key_release(T)

    declare(monkeypatch)                         # the mechanism follows the declaration (like the Knife's)
    assert press(app, lab, T)
    assert e5_warning_text(lab) == one_sided_text("Extrude")
    assert app.key_release(T)


# -- T under symmetry --------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("seam", [False, True], ids=["interior_face", "seam_face"])
def test_t_is_coordinated_in_one_undo_step_and_selects_the_caps_on_the_working_side(mode, seam):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    face = plus_x_face(app, seam=seam)
    select_faces(app, face)
    before = state(app)
    seam_before = mesh.symmetry_definition.seam_edges
    steps = len(app.history)  # Shift+S is a history step of its own in the Lab

    assert drag_t(app, lab)
    assert app.status_message == "Extrude committed"
    assert len(app.history) == steps + 1
    assert_clean(app, lab)
    assert (mesh.symmetry_definition.seam_edges != seam_before) is seam   # S3 moves the seam with the mesh
    # Residue (Engineering-Default): the new caps on the side the selection was on.
    caps = set(app.selection.faces)
    assert caps and all(mesh.is_valid_face(f) for f in caps)
    assert all(sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0 for f in caps)

    assert press(app, lab, CTRL_Z) is True
    assert state(app) == before
    assert mesh.symmetry_definition.seam_edges == seam_before
    assert press(app, lab, CTRL_Y) is True
    assert len(app.history) == steps + 1
    assert_clean(app, lab)


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_the_caps_of_a_seam_extrude_extrude_again(mode):
    """Manu's report: extrude a face on the seam, then the newly selected cap again was refused ("neue Elemente ohne
    Partner", the old seam vertices purple). Both extrudes and a third run, one Undo step each, HUD `valid`."""
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    select_faces(app, plus_x_face(app, seam=True))
    steps = len(app.history)
    for n in (1, 2, 3):
        assert drag_t(app, lab)
        assert app.status_message == "Extrude committed", f"extrude #{n}: {app.status_message}"
        assert len(app.history) == steps + n
        assert_clean(app, lab)
        assert app.selection.faces
    for n in (2, 1, 0):
        assert press(app, lab, CTRL_Z) is True
        assert len(app.history) == steps + n
        assert_clean(app, lab)
    assert all(mesh.is_valid_edge(e) for e in mesh.symmetry_definition.seam_edges)


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_both_sides_selected_extrude_as_one_intent_and_select_both_caps(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    face = plus_x_face(app)
    select_faces(app, face, SymmetryIndex(mesh).face_partner(face))
    steps = len(app.history)
    assert drag_t(app, lab)
    assert app.status_message == "Extrude committed" and len(app.history) == steps + 1
    assert_clean(app, lab)
    sides = {sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0 for f in app.selection.faces}
    assert sides == {True, False}


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_esc_during_the_gesture_restores_mesh_seam_and_selection(mode):
    app, lab = lab_on(mode)
    select_faces(app, plus_x_face(app, seam=True))
    before = state(app)
    seam_before = app.scene.mesh.symmetry_definition.seam_edges
    assert press(app, lab, T)
    x, y = 400.0, 300.0
    for _ in range(4):
        x, y = x + 30, y + 20
        app.pointer_motion(x, y, 30.0, 20.0)
    assert app.transform_interacting
    assert press(app, lab, ESC)
    assert state(app) == before
    assert app.scene.mesh.symmetry_definition.seam_edges == seam_before


# -- runtime refusals are the same in MARK and BLOCK -------------------------------------------


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_a_face_without_a_partner_is_refused_visibly_and_nothing_changes(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    face = plus_x_face(app)
    vertex = mesh.face_vertices(face)[0]
    x, y, z = mesh.vertex_position(vertex)
    mesh.set_vertex_position(vertex, (x + 0.01, y, z))   # the face loses its partner
    select_faces(app, face)
    before = state(app)
    drag_t(app, lab)
    assert app.status_message == TEXT_UNPAIRED
    assert state(app) == before
    assert app.transform_command is None and app.interaction_owner is None


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_a_face_spanning_the_plane_is_refused_visibly_and_nothing_changes(mode):
    """Artist statement 2026-10-09 (Case 4): refuse visibly, for now. The head has no such face: the vertices of a
    +X quad are moved across the plane together with their mirror so the pair stays complete but one face spans."""
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    index = SymmetryIndex(mesh)
    face = plus_x_face(app)
    partner = index.face_partner(face)
    # Rebuild `face` so that it uses a vertex of its partner: it then spans the plane and is its own mirror.
    vs = mesh.face_vertices(face)
    pvs = [index.vertex_partner(v) for v in vs]
    mesh.remove_face(face)
    mesh.remove_face(partner)
    spanning = mesh.add_face([vs[0], vs[1], pvs[1], pvs[0]])
    assert SymmetryIndex(mesh).face_partner(spanning) == spanning
    select_faces(app, spanning)
    before = state(app)
    drag_t(app, lab)
    assert app.status_message == TEXT_EXTRUDE_SPANNING
    assert state(app) == before
    assert app.transform_command is None


# -- symmetry off ------------------------------------------------------------------------------


def test_with_symmetry_off_t_runs_one_sided_as_in_b9():
    app, lab = lab_on(GateMode.BLOCK, symmetric=False)
    assert lab.axis is None and app.scene.mesh.symmetry_definition is None
    mesh = app.scene.mesh
    faces_before = len(mesh.all_face_ids())
    face = plus_x_face(app)
    select_faces(app, face)
    assert drag_t(app, lab)
    assert app.status_message == "Extrude committed" and len(app.history) == 1
    # One face -> 1 cap + 4 walls - 1 original: one-sided, the mirror face was not extruded.
    assert len(mesh.all_face_ids()) == faces_before + 4
    assert mesh.symmetry_definition is None
