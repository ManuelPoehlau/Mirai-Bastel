"""Symmetrisches W/E/R auf dem App-Pfad (WP-SYM-LAB-03 Slice 2, Plan §4.4).

Portiert aus `test_lab_symmetric_transform.py` (alle 12) und `test_lab_move.py` (die
sechs „keep"-Fälle: symmetrischer Partner, Seam gleitet, je ein Undo-Schritt, exaktes
Esc, ohne Symmetrie, Status). Statt `LabDispatcher` laufen die Tasten durch
`lab_key_press` (Lab-Pfad, Nicht-Lab-Tasten gehen an `app.key_press`), die Maus durch
`app.pointer_motion` und das Loslassen durch `app.key_release` — wie im Fenster. Die
Originale bleiben bis Slice 5 unverändert.

Abweichungen gegenüber den Originalen, alle App-Entscheidungen (Plan §4.3):
Meldungen kommen von `Application` (englisch, `Rotate committed`,
`Rotate: refused — …` aus H5); W hält die X/Y/Z-Constraint ein (B4.1, Plan §1.2 D1 —
das Original prüfte, dass sie im alten Lab *nicht* wirkte); Undo stellt die Auswahl
wieder her (B6 Follow-up); der E5-Teil (`one_sided_active`, `gate_mode`) entfällt bis
Slice 4. Die Kombination „W + Constraint + Symmetrie" ist in `src` schon getestet
(`tests/test_application_symmetry.py`, Slice 1a); der Lab-Pfad-Port
`test_move_honours_the_constraint_and_stays_mirrored` ersetzt hier das Original
`test_move_and_gate_unchanged` und deckt zusätzlich die Weiterleitung durch
`lab_key_press` und das echte Asset ab.
"""

from __future__ import annotations

import pytest

from mirai.interaction.input import Input
from mirai.interaction.tools.move import MoveTool
from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

from symmetry_lab.lab_app import TRANSFORM_IDLE, hud_text
from symmetry_lab.lab_symmetry import AXIS_NORMALS, ORIGIN

from ._app_lab_support import (  # noqa: F401
    CTRL_Y,
    CTRL_Z,
    ESC,
    SHIFT_S,
    W,
    forbid_lab_calls,
    make_lab,
    press,
)

KEY_E = Input("key", "e")
KEY_R = Input("key", "r")
KEY_X = Input("key", "x")
KEY_Y = Input("key", "y")
KEY_Z = Input("key", "z")
DRAGS = [(40, 2), (30, -3), (20, 7)]
MOVE_DRAGS = [(6, 2), (5, -3), (4, 7)]


@pytest.fixture
def lab():
    """`subd_cube` mit X-Symmetrie über die Lab-Taste (18 gepaarte + 8 Seam-Vertices)."""
    app, lab = make_lab("subd_cube")
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    return app, lab


def vertex_in_state(app, state):
    corr = vertex_correspondence(app.scene.mesh)
    return min(v for v, c in corr.items() if c.state is state)


def paired(app):
    vid = vertex_in_state(app, CorrespondenceState.PAIRED)
    return vid, vertex_correspondence(app.scene.mesh)[vid].partner


def same_side_pair(app, vid):
    """Ein zweiter gepaarter Vertex auf derselben Seite wie `vid` und sein Partner.
    Rotate/Scale brauchen seit dem Pivot pro Seite (Artist-Verdikt 2026-10-03) eine
    Gruppe: ein einzelner Vertex dreht/skaliert um sich selbst."""
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    side = mesh.vertex_position(vid)[0] > 0
    for w in sorted(mesh.all_vertex_ids(), key=int):
        c = corr[w]
        if w != vid and c.state is CorrespondenceState.PAIRED and (mesh.vertex_position(w)[0] > 0) == side:
            return w, c.partner
    raise AssertionError("kein zweiter gepaarter Vertex auf derselben Seite")


def select(app, *vids) -> None:
    app.selection.set(set(vids))
    app.viewport.on_selection_changed()


def move_mouse(app, drags=DRAGS, start=(400.0, 300.0)) -> None:
    """Mausbewegung ohne gedrückte Taste, während die Transform-Taste gehalten wird."""
    x, y = start
    for dx, dy in drags:
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)


def hold(app, lab, key, drags=DRAGS) -> None:
    assert press(app, lab, key)
    move_mouse(app, drags)
    app.key_release(key)


def mirrored_ok(app, vid, partner) -> bool:
    mesh = app.scene.mesh
    return mesh.vertex_position(partner) == mirror_position(
        mesh.vertex_position(vid), ORIGIN, AXIS_NORMALS["X"]
    )


# -- Portiert aus test_lab_symmetric_transform.py (12) ---------------------------------


@pytest.mark.parametrize("key,label", [(KEY_E, "Rotate"), (KEY_R, "Scale")])
def test_single_vertex_runs_symmetric_one_undo_step(lab, key, label):
    """Seit dem Pivot pro Seite (2026-10-03) mit einer einseitigen Zwei-Vertex-Gruppe;
    der Name bleibt für die Zuordnung zum portierten Original."""
    app, lab_ = lab
    mesh = app.scene.mesh
    vid, partner = paired(app)
    other, other_partner = same_side_pair(app, vid)
    select(app, vid, other)
    state0, before = mesh.export_state(), len(app.history)
    p0 = mesh.vertex_position(vid)

    assert press(app, lab_, key) is True
    assert app.status_message.startswith(f"{label}: 2 vertices")  # keine Ablehnung
    move_mouse(app)
    assert app.transform_interacting
    assert app.key_release(key) is True

    assert mesh.vertex_position(vid) != p0
    assert mirrored_ok(app, vid, partner)
    assert mirrored_ok(app, other, other_partner)
    assert vertex_correspondence(mesh)[vid].partner == partner  # Paar bleibt PAIRED
    assert app.status_message == f"{label} committed"
    assert len(app.history) == before + 1
    assert press(app, lab_, CTRL_Z)
    assert mesh.export_state() == state0
    assert len(app.history) == before


@pytest.mark.parametrize("key", [KEY_E, KEY_R])
def test_cancel_leaves_no_history(lab, key):
    app, lab_ = lab
    mesh = app.scene.mesh
    vid, _ = paired(app)
    select(app, vid)
    state0, before = mesh.export_state(), len(app.history)
    assert press(app, lab_, key)
    move_mouse(app)
    assert press(app, lab_, ESC)
    assert mesh.export_state() == state0
    assert len(app.history) == before
    assert app.transform_command is None


def test_constraint_keys_toggle_and_show_in_hud(lab):
    app, lab_ = lab
    assert app.axis_constraint is None
    assert press(app, lab_, KEY_X)
    assert app.axis_constraint == "x"
    assert " | Constraint: X | " in hud_text(app, "subd_cube", lab_.report)
    assert press(app, lab_, KEY_Y)
    assert app.axis_constraint == "y"
    assert press(app, lab_, KEY_Y)
    assert app.axis_constraint is None


def test_constraints_x_y_z_all_keep_the_pair_mirrored(lab):
    app, lab_ = lab
    vid, partner = paired(app)
    for key in (KEY_X, KEY_Y, KEY_Z):
        assert press(app, lab_, key)
        select(app, vid)
        hold(app, lab_, KEY_E)
        assert mirrored_ok(app, vid, partner)
        assert press(app, lab_, key)  # Constraint wieder frei


def test_seam_vertex_rotate_x_allowed(lab):
    # Ein einzelner Seam-Vertex ist sein eigener Pivot: erlaubt, aber nichts zu bewegen.
    app, lab_ = lab
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    select(app, seam)
    assert press(app, lab_, KEY_X)
    hold(app, lab_, KEY_E)
    assert "refused" not in app.status_message
    assert mesh.vertex_position(seam)[0] == 0.0


@pytest.mark.parametrize("constraint_key", [KEY_Y, KEY_Z, None])
def test_seam_vertex_rotate_other_axes_refused_with_message(lab, constraint_key):
    app, lab_ = lab
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    select(app, seam)
    if constraint_key is not None:  # None: Constraint frei = Bildachse (nicht ∥ Normale)
        assert press(app, lab_, constraint_key)
    state, before = mesh.export_state(), len(app.history)
    assert press(app, lab_, KEY_E)
    move_mouse(app)
    assert app.transform_command is None  # H5: nie gelaufen, sichtbar beendet
    assert app.status_message.startswith("Rotate: refused — ")
    assert "Seam" in app.status_message
    assert mesh.export_state() == state and len(app.history) == before
    assert app.key_release(KEY_E) is False
    assert mesh.export_state() == state


def test_seam_vertex_scale_allowed_and_on_plane(lab):
    app, lab_ = lab
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    select(app, seam)
    hold(app, lab_, KEY_R)
    assert "refused" not in app.status_message
    assert mesh.vertex_position(seam)[0] == 0.0


def test_move_honours_the_constraint_and_stays_mirrored(lab):
    """Port von `test_move_and_gate_unchanged`: im alten Lab ignorierte W die
    Constraint (Plan §1.2 D1), auf dem App-Pfad gilt sie (B4.1) — unter Symmetrie
    bleibt das Paar gespiegelt, bewegt wird nur entlang X."""
    app, lab_ = lab
    mesh = app.scene.mesh
    vid, partner = paired(app)
    select(app, vid)
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert press(app, lab_, KEY_X)
    assert press(app, lab_, W)
    move_mouse(app)
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert app.transform_space == "x"
    assert app.key_release(W)
    assert mirrored_ok(app, vid, partner)
    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and p1[1:] == p0[1:] and q1[1:] == q0[1:]


# -- Portiert aus test_lab_move.py (6 „keep") ---------------------------------------


def test_symmetric_move_one_history_entry_and_exact_undo(lab):
    app, lab_ = lab
    mesh = app.scene.mesh
    vid, partner = paired(app)
    select(app, vid)
    history_before = len(app.history)
    state_before = mesh.export_state()
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)

    assert press(app, lab_, W) is True
    assert app.transform_command == "Move" and not app.transform_interacting
    move_mouse(app, MOVE_DRAGS)
    assert app.transform_interacting
    # MoveTool löst die Symmetrie selbst aus dem Mesh auf (nicht das Lab).
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert app.key_release(W) is True

    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and q1 != q0
    assert mirror_position(p1, ORIGIN, AXIS_NORMALS["X"]) == q1
    assert vertex_correspondence(mesh)[vid].partner == partner
    assert len(app.history) == history_before + 1

    assert press(app, lab_, CTRL_Z)
    assert mesh.vertex_position(vid) == p0
    assert mesh.vertex_position(partner) == q0
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before


def test_move_without_symmetry_moves_only_the_selection(lab):
    app, lab_ = lab
    for _ in range(3):  # X → Y → Z → aus
        assert press(app, lab_, SHIFT_S)
    assert app.scene.mesh.symmetry_definition is None
    vid = min(app.scene.mesh.all_vertex_ids())
    select(app, vid)
    assert press(app, lab_, W)
    move_mouse(app, MOVE_DRAGS)
    assert app.tool_manager.active_tool.moves == {vid}
    assert app.key_release(W)


def test_seam_vertex_stays_exactly_on_plane(lab):
    app, lab_ = lab
    mesh = app.scene.mesh
    vid = vertex_in_state(app, CorrespondenceState.SEAM)
    select(app, vid)
    p0 = mesh.vertex_position(vid)
    hold(app, lab_, W, MOVE_DRAGS * 3)
    p1 = mesh.vertex_position(vid)
    assert p1 != p0  # nicht trivial: der Vertex hat sich in der Ebene bewegt
    assert p1[0] == 0.0
    assert lab_.report.state.value == "valid"


def test_undo_takes_back_exactly_one_action_each(lab):
    # Symmetrie-Schritt (Fixture) + Move → zwei Einträge, je ein Undo pro Handlung.
    app, lab_ = lab
    mesh = app.scene.mesh
    vid, _partner = paired(app)
    select(app, vid)
    after_symmetry = mesh.export_state()
    hold(app, lab_, W, MOVE_DRAGS)
    assert len(app.history) == 2

    assert press(app, lab_, CTRL_Z)
    assert mesh.export_state() == after_symmetry
    assert app.selection.vertices == {vid}  # App: Undo stellt die Auswahl her (B6)
    assert press(app, lab_, CTRL_Z)
    assert mesh.symmetry_definition is None
    assert len(app.history) == 0

    assert press(app, lab_, CTRL_Y)
    assert mesh.export_state() == after_symmetry


def test_esc_during_drag_restores_exactly_without_history(lab):
    app, lab_ = lab
    mesh = app.scene.mesh
    vid, _ = paired(app)
    select(app, vid)
    state_before = mesh.export_state()
    history_before = len(app.history)
    assert press(app, lab_, W)
    move_mouse(app, MOVE_DRAGS)
    assert mesh.export_state() != state_before
    assert press(app, lab_, ESC) is True
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.transform_command is None
    assert app.tool_manager.active_tool is None
    # Das spätere Loslassen von W bewirkt nichts mehr.
    assert app.key_release(W) is False
    assert mesh.export_state() == state_before


def test_hud_shows_plane_state_unpaired_and_move():
    """Port von `test_status_text_shows_plane_state_unpaired_move_and_selection`; die
    Auswahl-Liste gehört nicht mehr zur Zeile (Slice-2-Brief), das Ziel schon."""
    app, lab_ = make_lab("man_with_shoes_basemesh")
    assert "Symmetrie: aus (off)" in hud_text(app, "man", lab_.report)
    assert TRANSFORM_IDLE in hud_text(app, "man", lab_.report)
    assert press(app, lab_, SHIFT_S)
    select(app, min(app.scene.mesh.all_vertex_ids()))
    assert press(app, lab_, W)
    text = hud_text(app, "man", lab_.report)
    assert "Symmetrie: X (partial)" in text
    assert "ohne Partner: 54" in text
    assert "Move: scharf (Auswahl)" in text
