"""Re-Symmetrize über topologische Paarung (Handoff Slice 5 §2 A5–A7, E12–E15, §7 Verhalten).

Echte Production-`Application` (`HistoryStack`, `tool_manager`) und
Dispatcher, kein GL-Kontext. Positionen werden exakt verglichen (A5: keine
Toleranz).
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state

from symmetry_lab import lab_draw_data
from symmetry_lab.lab_bindings import apply_lab_bindings
from symmetry_lab.lab_dispatch import PREVIEW_HINT, Change, LabDispatcher, MoveState
from symmetry_lab.lab_resymmetrize import (
    ResymmetrizeRejected,
    apply_plan,
    plan_resymmetrize,
    plan_summary,
)
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_status import preview_text, status_text
from symmetry_lab.lab_symmetry import definition_for_axis, symmetry_report
from symmetry_lab.lab_topology import topology_report

W, H = 1280, 800
M = Input("key", "m")
ESC = Input("key", "ESCAPE")
Q = Input("key", "q")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def make_app(asset: str, axis: str | None = "X") -> Application:
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, asset)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, axis)
    return app


def vertex_on_side(app: Application, side: int):
    sides = topology_report(app.scene.mesh).sides
    return min((v for v, s in sides.vertex_side.items() if s == side), key=int)


def side_vertices(app: Application, side: int) -> list:
    sides = topology_report(app.scene.mesh).sides
    return sorted((v for v, s in sides.vertex_side.items() if s == side), key=int)


def positions(app: Application, vids) -> dict:
    return {v: app.scene.mesh.vertex_position(v) for v in vids}


def run_m_m(app: Application, source) -> LabDispatcher:
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({source})
    assert dispatcher.key(M) is True
    assert dispatcher.resym_plan is not None
    assert dispatcher.key(M) is True
    assert dispatcher.resym_plan is None
    return dispatcher


# -- man_with_shoes: von jeder Seite aus (§7) ------------------------------------


@pytest.mark.parametrize("source_side", [0, 1])
def test_man_with_shoes_from_either_side_becomes_valid(source_side):
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    assert len(symmetry_report(mesh).unpaired) == 54
    source = vertex_on_side(app, source_side)
    source_before = positions(app, side_vertices(app, source_side))
    state_before = mesh.export_state()
    history_before = len(app.history)

    run_m_m(app, source)

    report = symmetry_report(mesh)
    assert report.state is SymmetryState.VALID
    assert report.unpaired == frozenset()
    assert len(app.history) == history_before + 1
    # Quellseite bitgenau unverändert (E13)
    assert positions(app, source_before) == source_before
    assert all(
        repr(mesh.vertex_position(v)) == repr(p) for v, p in source_before.items()
    )

    LabDispatcher(app, W, H).key(CTRL_Z)
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before


def test_target_is_exact_mirror_of_topological_partner():
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    source = vertex_on_side(app, 0)
    plan = plan_resymmetrize(mesh, source)
    assert len(plan.moves) == 27  # die 54 ungepaarten Vertices sind 27 Paare
    apply_plan(app.scene, plan)
    partners = topology_report(mesh).pairing.partners
    for vid in side_vertices(app, 1):
        mirrored = mirror_position(mesh.vertex_position(partners[vid]), *PLANE)
        assert mesh.vertex_position(vid) == mirrored


# -- Quellseite (A6, E12) -----------------------------------------------------------


def test_source_side_is_topological_even_after_crossing_the_plane():
    app = make_app("head_basemesh")
    mesh = app.scene.mesh
    source = vertex_on_side(app, 0)
    x, y, z = mesh.vertex_position(source)
    crossed = (-x - 0.05 if x > 0 else -x + 0.05, y, z)
    mesh.set_vertex_position(source, crossed)
    partner = topology_report(mesh).pairing.partners[source]

    plan = plan_resymmetrize(mesh, source)
    assert plan.source_side == 0
    assert [c.vertex for c in plan.moves] == [partner]
    apply_plan(app.scene, plan)
    assert mesh.vertex_position(source) == crossed  # Quelle bleibt
    assert mesh.vertex_position(partner) == mirror_position(crossed, *PLANE)
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_direction_label_names_source_and_target():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    for side in (0, 1):
        vid = vertex_on_side(app, side)
        plan = plan_resymmetrize(mesh, vid)
        sign = "+X" if mesh.vertex_position(vid)[0] > 0 else "−X"
        other = "−X" if sign == "+X" else "+X"
        assert (plan.source_label, plan.target_label) == (sign, other)
        assert f"Quelle {sign} → Ziel {other}" in plan_summary(plan)


# -- Seam (E13) ---------------------------------------------------------------------


def test_seam_vertex_moved_off_plane_ends_exactly_on_plane():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    seam_vid = min(topology_report(mesh).sides.seam_vertices, key=int)
    x, y, z = mesh.vertex_position(seam_vid)
    mesh.set_vertex_position(seam_vid, (0.3, y, z))
    assert symmetry_state(mesh) is SymmetryState.VIOLATED

    plan = plan_resymmetrize(mesh, vertex_on_side(app, 0))
    assert [c.vertex for c in plan.seam_moves] == [seam_vid]
    assert plan.moves == ()
    run_m_m(app, vertex_on_side(app, 0))
    assert mesh.vertex_position(seam_vid) == (0.0, y, z)
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_seam_vertices_already_on_plane_are_not_in_plan():
    app = make_app("head_basemesh")
    plan = plan_resymmetrize(app.scene.mesh, vertex_on_side(app, 1))
    assert plan.seam_moves == ()
    assert plan.is_empty


# -- Ablehnungen (E15) ----------------------------------------------------------------


def _assert_rejected(app, dispatcher, reason: str):
    history_before = len(app.history)
    state_before = app.scene.mesh.export_state()
    dispatcher.take_changes()
    assert dispatcher.key(M) is True
    assert dispatcher.resym_plan is None
    assert reason in dispatcher.message
    assert dispatcher.take_changes() == Change.STATUS
    assert len(app.history) == history_before
    assert app.scene.mesh.export_state() == state_before


def test_rejected_when_symmetry_off():
    app = make_app("subd_cube", axis=None)
    app.scene.selection.set({next(iter(app.scene.mesh.all_vertex_ids()))})
    _assert_rejected(app, LabDispatcher(app, W, H), "Symmetrie aus")


def test_rejected_without_selection():
    app = make_app("subd_cube")
    _assert_rejected(app, LabDispatcher(app, W, H), "keine Auswahl")


def test_rejected_for_seam_vertex():
    app = make_app("subd_cube")
    app.scene.selection.set({min(topology_report(app.scene.mesh).sides.seam_vertices)})
    _assert_rejected(app, LabDispatcher(app, W, H), "Seam-Vertex")


def test_rejected_when_seam_does_not_split_into_two():
    app = make_app("subd_cube", axis="Y")  # 0 Seam-Edges → 1 Komponente
    app.scene.selection.set({next(iter(app.scene.mesh.all_vertex_ids()))})
    _assert_rejected(app, LabDispatcher(app, W, H), "1 Teile (nötig: genau 2)")


def test_rejected_while_move_armed():
    app = make_app("subd_cube")
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({vertex_on_side(app, 0)})
    dispatcher.key(Q)
    assert dispatcher.move_state is MoveState.ARMED
    _assert_rejected(app, dispatcher, "Move")
    assert dispatcher.move_state is MoveState.ARMED


def test_rejected_while_move_dragging():
    app = make_app("subd_cube")
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({vertex_on_side(app, 0)})
    dispatcher.key(Q)
    dispatcher.press(LMB)
    dispatcher.drag(6, 2)
    assert dispatcher.move_state is MoveState.DRAGGING
    assert dispatcher.key(M) is True
    assert dispatcher.resym_plan is None
    assert "Move" in dispatcher.message
    dispatcher.key(ESC)


# -- Vorschau-Zustand (A7, E15) ---------------------------------------------------------


@pytest.fixture
def previewing():
    """man_with_shoes, Vertex auf Seite 0 gewählt, Vorschau offen (27 Moves)."""
    app = make_app("man_with_shoes_basemesh")
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({vertex_on_side(app, 0)})
    dispatcher.key(M)
    assert dispatcher.resym_plan is not None
    assert len(dispatcher.resym_plan.moves) == 27
    return app, dispatcher


def test_m_esc_leaves_mesh_unchanged_and_no_history(previewing):
    app, dispatcher = previewing
    state_before = app.scene.mesh.export_state()
    dispatcher.take_changes()
    assert dispatcher.key(ESC) is True  # schließt nicht das Fenster
    assert dispatcher.resym_plan is None
    assert Change.PREVIEW in dispatcher.take_changes()
    assert app.scene.mesh.export_state() == state_before
    assert len(app.history) == 0


def test_m_m_executes_with_one_history_entry(previewing):
    app, dispatcher = previewing
    dispatcher.take_changes()
    dispatcher.key(M)
    changes = dispatcher.take_changes()
    assert Change.MESH in changes and Change.PREVIEW in changes
    assert len(app.history) == 1
    assert symmetry_state(app.scene.mesh) is SymmetryState.VALID
    assert "ausgeführt" in dispatcher.message


@pytest.mark.parametrize("inp", [SHIFT_S, Q, CTRL_Z, CTRL_Y])
def test_other_keys_are_ignored_during_preview(previewing, inp):
    app, dispatcher = previewing
    state_before = app.scene.mesh.export_state()
    selection_before = set(app.scene.selection.vertices)
    plan = dispatcher.resym_plan
    assert dispatcher.key(inp) is True
    assert dispatcher.resym_plan is plan
    assert dispatcher.message == PREVIEW_HINT
    assert dispatcher.move_state is MoveState.READY
    assert app.scene.mesh.export_state() == state_before
    assert app.scene.selection.vertices == selection_before
    assert len(app.history) == 0


def test_select_is_ignored_during_preview(previewing):
    app, dispatcher = previewing
    selection_before = set(app.scene.selection.vertices)
    dispatcher.press(LMB)
    assert dispatcher.active_command is None
    assert dispatcher.release("LEFT", 0, 0) is False
    assert app.scene.selection.vertices == selection_before
    assert dispatcher.message == PREVIEW_HINT
    assert dispatcher.resym_plan is not None


def test_click_pressed_before_m_does_not_select_during_preview():
    app = make_app("subd_cube")
    dispatcher = LabDispatcher(app, W, H)
    vid = vertex_on_side(app, 0)
    app.scene.selection.set({vid})
    dispatcher.press(LMB)  # Select-Geste läuft schon
    dispatcher.key(M)
    assert dispatcher.resym_plan is not None
    assert dispatcher.release("LEFT", 0, 0) is False
    assert app.scene.selection.vertices == {vid}
    assert dispatcher.message == PREVIEW_HINT


def test_navigation_allowed_during_preview(previewing):
    app, dispatcher = previewing
    camera = app.camera
    before = (camera.yaw, camera.pitch, camera.distance)
    dispatcher.press(ALT_LMB)
    dispatcher.drag(20, 10)
    dispatcher.release("LEFT", 0, 0)
    dispatcher.scroll(Input("wheel", "UP"))
    assert (camera.yaw, camera.pitch, camera.distance) != before
    assert dispatcher.resym_plan is not None


def test_hover_paused_during_preview():
    app = make_app("subd_cube")
    dispatcher = LabDispatcher(app, W, H)
    vid = vertex_on_side(app, 0)
    x, y = app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), W, H)[:2]
    dispatcher.motion(x, y)
    assert dispatcher.hover_vertex is not None
    app.scene.selection.set({vid})
    dispatcher.key(M)
    assert dispatcher.hover_vertex is None
    dispatcher.motion(x, y)
    assert dispatcher.hover_vertex is None
    dispatcher.key(ESC)
    dispatcher.motion(x, y)
    assert dispatcher.hover_vertex is not None


def test_zero_changes_preview_then_m_creates_no_history_entry():
    app = make_app("head_basemesh")
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({vertex_on_side(app, 0)})
    state_before = app.scene.mesh.export_state()
    dispatcher.key(M)
    assert dispatcher.resym_plan.is_empty
    assert "0 Änderungen" in plan_summary(dispatcher.resym_plan)
    dispatcher.key(M)
    assert dispatcher.resym_plan is None
    assert len(app.history) == 0
    assert app.scene.mesh.export_state() == state_before
    assert "kein Schritt" in dispatcher.message


def test_status_line_shows_direction_counts_and_keys(previewing):
    app, dispatcher = previewing
    report = symmetry_report(app.scene.mesh)
    text = preview_text(dispatcher)
    plan = dispatcher.resym_plan
    assert f"Quelle {plan.source_label} → Ziel {plan.target_label}" in text
    assert "bewegt 27" in text
    assert "M = ausführen, ESC = abbrechen" in text
    assert "Quelle" not in status_text(app, "man_with_shoes_basemesh", dispatcher, report)
    dispatcher.key(ESC)
    assert preview_text(dispatcher) == ""


# -- Konflikt / ohne Partner (E13) -------------------------------------------------------


def _negative_edge(mesh):
    seam = mesh.symmetry_definition.seam_edges
    return next(
        e for e in mesh.all_edge_ids()
        if e not in seam and all(mesh.vertex_position(v)[0] < 0 for v in mesh.edge_vertices(e))
    )


def _side_of_sign(app, positive: bool) -> int:
    mesh = app.scene.mesh
    vid = vertex_on_side(app, 0)
    return 0 if (mesh.vertex_position(vid)[0] > 0) == positive else 1


def test_vertex_without_partner_on_target_stays_and_is_listed():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    new_vertex, _, _ = mesh.split_edge(_negative_edge(mesh))
    source = vertex_on_side(app, _side_of_sign(app, positive=True))
    # Zielseite verschieben, damit der Plan etwas zu tun hat
    for vid in side_vertices(app, 1 - _side_of_sign(app, positive=True)):
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x, y + 0.125, z))
    new_before = mesh.vertex_position(new_vertex)

    plan = plan_resymmetrize(mesh, source)
    assert plan.unmatched == frozenset({new_vertex})
    assert new_vertex not in {c.vertex for c in plan.changes}
    apply_plan(app.scene, plan)
    assert mesh.vertex_position(new_vertex) == new_before


def test_conflict_partners_stay_unchanged():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    merged = mesh.collapse_edge(_negative_edge(mesh))
    positive = _side_of_sign(app, positive=True)
    report = topology_report(mesh)
    # von −X aus: die +X-Vertices, deren Partner der Konflikt-Vertex wäre, bleiben
    plan = plan_resymmetrize(mesh, vertex_on_side(app, 1 - positive))
    assert len(plan.unmatched) == 2
    assert not (plan.unmatched & {c.vertex for c in plan.changes})
    assert all(report.sides.vertex_side[v] == positive for v in plan.unmatched)
    # von +X aus: der Konflikt-Vertex selbst liegt auf der Zielseite und bleibt
    plan = plan_resymmetrize(mesh, vertex_on_side(app, positive))
    assert merged in plan.unmatched
    assert merged not in {c.vertex for c in plan.changes}


# -- Vorschau-Daten -----------------------------------------------------------------------


def test_preview_draw_data(previewing):
    app, dispatcher = previewing
    plan = dispatcher.resym_plan
    data = lab_draw_data.resym_preview_data(app.scene.mesh, plan)
    assert len(data.move_points) == 3 * len(plan.moves)
    assert len(data.move_lines) == 6 * len(plan.moves)
    first = plan.moves[0]
    assert tuple(data.move_lines[:6]) == first.before + first.after
    assert data.seam_points == data.seam_lines == data.keep_points == []
    empty = lab_draw_data.resym_preview_data(app.scene.mesh, None)
    assert empty.move_points == empty.move_lines == empty.keep_points == []


def test_plan_rejects_directly():
    app = make_app("subd_cube", axis=None)
    with pytest.raises(ResymmetrizeRejected):
        plan_resymmetrize(app.scene.mesh, next(iter(app.scene.mesh.all_vertex_ids())))


def test_paired_state_unaffected_by_preview():
    # Anzeige gelb/magenta bleibt positionsbasiert (Handoff §5): die Vorschau
    # ändert weder Mesh noch Correspondence.
    app = make_app("man_with_shoes_basemesh")
    report_before = symmetry_report(app.scene.mesh)
    dispatcher = LabDispatcher(app, W, H)
    app.scene.selection.set({vertex_on_side(app, 0)})
    dispatcher.key(M)
    assert symmetry_report(app.scene.mesh) == report_before
