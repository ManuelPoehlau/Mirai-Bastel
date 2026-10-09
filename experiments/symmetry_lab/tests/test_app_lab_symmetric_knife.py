"""AD-SYM-03 slice 6c: the Knife under symmetry in the Symmetry Lab, now that `CContext.KNIFE` is declared.

- BLOCK: the Knife is no longer refused (the BLOCK row is derived from the declarations and names no context);
  the session runs coordinated: Enter cuts both sides in one history entry, Undo / Redo restore both sides and
  the seam, the residue is the working side's cut edge;
- MARK: the same, and no one-sided warning line (`e5_warning_text` is derived from the same declarations);
- the provisional mirror-preview variant key is not a Lab key (H2-R1 stays three keys), the BLOCK allow-list is
  what it was, and the key works through the Lab path inside the session only.

The undeclared-Knife behaviour (the derived refusal and warning mechanism) is still pinned, with the Knife
undeclared by `undeclare_knife`, in `test_app_lab_gate.py`, `test_app_lab_fail_closed.py` and the other files.
"""

from __future__ import annotations

import pytest

from mirai import symmetry_declarations as declarations
from mirai.application import KNIFE_MIRROR_VARIANT_KEY
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import completeness_report
from mirai.topology.contextual_c import CContext
from mirai.topology.knife_pick import knife_pick

from symmetry_lab.lab_app import (
    LAB_KEY_ENTRIES,
    NON_OPERATION,
    TRANSFORM_OPERATIONS,
    GateMode,
    block_row,
    e5_warning_text,
)

from ._app_lab_support import (
    C,
    CTRL_Y,
    CTRL_Z,
    ESC,
    HEIGHT,
    MISS,
    SHIFT_B,
    SHIFT_S,
    WIDTH,
    make_lab,
    press,
    screen,
)

ENTER = Input("key", "enter")
LMB = Input("mouse", "LEFT")
V = Input("key", KNIFE_MIRROR_VARIANT_KEY)


def lab_on(mode: GateMode):
    """subd_cube, Symmetrie X über Shift+S, E5-Modus `mode`."""
    app, lab = make_lab()
    if lab.gate_mode is not mode:
        assert press(app, lab, SHIFT_B)
    assert lab.gate_mode is mode
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    app.pointer_motion(*MISS)
    return app, lab


def one_side_diagonal(app):
    """Zwei diagonale Vertices einer Quad-Face ganz auf der +X-Seite, die der Knife als Vertex trifft."""
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
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert press(app, lab, C) is True
    assert app.knife_active


def topology(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def assert_valid(app, lab) -> None:
    report = completeness_report(app.scene.mesh)
    assert not (report.unpaired_vertices | report.faces_without_partner | report.edges_without_partner)
    assert not (report.self_mirrored_faces | report.dead_seam_ids)
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID
    assert lab.report.state is SymmetryState.VALID


def test_the_block_row_names_no_context_and_its_allow_list_is_what_it_was():
    gate = block_row().gate
    assert dict(gate.refused_contexts) == {} and dict(gate.refused) == {}
    assert gate.allowed == (
        NON_OPERATION
        | frozenset(TRANSFORM_OPERATIONS)
        | declarations.declared_removal_commands()
        | declarations.declared_extrude_commands()
        | {cmd.CONNECT}
    )
    assert cmd.KNIFE_COMMIT in gate.allowed and cmd.KNIFE_LIFT in gate.allowed


def test_the_variant_key_is_no_fourth_lab_key():
    assert len(LAB_KEY_ENTRIES) == 3
    assert V not in {entry.input for entry in LAB_KEY_ENTRIES}
    assert V.value not in {entry.input.value for entry in LAB_KEY_ENTRIES if not entry.input.modifiers}


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_the_knife_runs_coordinated_in_block_and_mark_with_one_history_entry(mode):
    app, lab = lab_on(mode)
    mesh = app.scene.mesh
    a, b = one_side_diagonal(app)
    before = topology(app)
    definition = mesh.symmetry_definition
    history = len(app.history)                      # Shift+S hat schon einen Eintrag
    edges = len(mesh.all_edge_ids())

    begin_knife(app, lab)
    assert e5_warning_text(lab) == ""                # keine einseitige Warnzeile (abgeleitet aus den Deklarationen)
    knife_click(app, a)
    knife_click(app, b)
    assert e5_warning_text(lab) == ""
    assert press(app, lab, ENTER) is True
    assert not app.knife_active
    assert len(app.history) == history + 1           # beide Seiten in einem Schritt
    assert len(mesh.all_edge_ids()) == edges + 2     # der Schnitt und sein Spiegelbild
    assert_valid(app, lab)
    assert len(app.selection.edges) == 1             # Residue F4 = A: nur die Schnittkante der Arbeitsseite
    assert all(mesh.vertex_position(v)[0] >= 0.0 for e in app.selection.edges for v in mesh.edge_vertices(e))
    after = topology(app)

    assert press(app, lab, CTRL_Z) is True
    assert len(app.history) == history
    assert topology(app) == before and mesh.symmetry_definition == definition
    assert press(app, lab, CTRL_Y) is True
    assert topology(app) == after
    assert_valid(app, lab)


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK], ids=["block", "mark"])
def test_the_variant_key_works_through_the_lab_path_inside_the_session_only(mode):
    app, lab = lab_on(mode)
    history = len(app.history)
    serial = app.status_serial
    assert press(app, lab, V) is False               # ausserhalb der Session: nichts, keine Ablehnung
    assert app.status_serial == serial
    begin_knife(app, lab)
    assert app.knife_mirror_variant == "V-b"
    assert press(app, lab, V) is True
    assert app.knife_mirror_variant == "V-c" and "V-c" in app.status_message
    assert press(app, lab, ESC) is True
    assert not app.knife_active
    assert len(app.history) == history
    if mode is GateMode.MARK:
        assert app.command_gate is None


def test_a_pending_session_follows_the_definition_it_started_with():
    """The session view is built at begin: a session started under a definition stays coordinated (the mesh and
    its definition do not change while the Knife runs - Shift+S is refused during a session)."""
    app, lab = lab_on(GateMode.BLOCK)
    begin_knife(app, lab)
    assert app._knife._symmetric_view is not None and app._knife._symmetric_commit is not None
    serial = app.status_serial
    assert press(app, lab, SHIFT_S) is False         # "Symmetrie (Shift+S) abgelehnt — Knife-Session läuft"
    assert app.status_serial == serial + 1
    assert press(app, lab, ESC) is True


def test_without_a_definition_the_knife_is_the_knife_as_before():
    """Symmetrie aus: der Knife ist der Knife wie vorher (kein Koordinator, keine Sicht)."""
    app, lab = make_lab()
    assert lab.axis is None
    begin_knife(app, lab)
    assert app._knife._symmetric_commit is None and app._knife._symmetric_view is None
    assert e5_warning_text(lab) == ""
    assert CContext.KNIFE in declarations.declared_c_contexts()
    assert press(app, lab, ESC) is True
