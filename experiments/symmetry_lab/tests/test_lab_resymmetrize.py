"""Re-Symmetrize über topologische Paarung (Handoff Slice 5 §2 A5–A7, E12–E15) — reine
Tests von `lab_resymmetrize` (Plan, Positionen, Vorschau-Daten).

Kein GL, keine Eingabe: das Verhalten über die Tasten (M / M / Esc, Ablehnungen,
Vorschau-Zustand) läuft seit WP-SYM-LAB-03 auf dem App-Pfad,
`test_app_lab_resymmetrize.py` und `test_app_lab_preview.py` (Plan A2-Tabelle,
Slice 5). Positionen werden exakt verglichen (A5: keine Toleranz).
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state

from symmetry_lab.lab_resymmetrize import (
    ResymmetrizeRejected,
    plan_resymmetrize,
    plan_summary,
    resym_preview_data,
    set_plan_positions,
)
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import definition_for_axis
from symmetry_lab.lab_topology import topology_report

PLANE = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def make_app(asset: str, axis: str | None = "X") -> Application:
    app = Application()
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


# -- man_with_shoes (§7) -------------------------------------------------------------


def test_target_is_exact_mirror_of_topological_partner():
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    source = vertex_on_side(app, 0)
    plan = plan_resymmetrize(mesh, source)
    assert len(plan.moves) == 27  # die 54 ungepaarten Vertices sind 27 Paare
    set_plan_positions(mesh, plan)
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
    set_plan_positions(mesh, plan)
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


def test_seam_vertices_already_on_plane_are_not_in_plan():
    app = make_app("head_basemesh")
    plan = plan_resymmetrize(app.scene.mesh, vertex_on_side(app, 1))
    assert plan.seam_moves == ()
    assert plan.is_empty


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
    set_plan_positions(app.scene.mesh, plan)
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


def test_preview_draw_data():
    """Seit Slice 5 rein: der Plan kommt direkt aus `plan_resymmetrize` (vorher über
    die Vorschau des alten Dispatchers), die Daten aus `lab_resymmetrize`."""
    app = make_app("man_with_shoes_basemesh")
    plan = plan_resymmetrize(app.scene.mesh, vertex_on_side(app, 0))
    assert len(plan.moves) == 27
    data = resym_preview_data(app.scene.mesh, plan)
    assert len(data.move_points) == 3 * len(plan.moves)
    assert len(data.move_lines) == 6 * len(plan.moves)
    first = plan.moves[0]
    assert tuple(data.move_lines[:6]) == first.before + first.after
    assert data.seam_points == data.seam_lines == data.keep_points == []
    empty = resym_preview_data(app.scene.mesh, None)
    assert empty.move_points == empty.move_lines == empty.keep_points == []


def test_plan_rejects_directly():
    app = make_app("subd_cube", axis=None)
    with pytest.raises(ResymmetrizeRejected):
        plan_resymmetrize(app.scene.mesh, next(iter(app.scene.mesh.all_vertex_ids())))

