"""Symmetrie-Zyklus, Seam-Ableitung und States (Handoff Slice 3 §2 E1–E4, §7).

Die Zahlen sind Charakterisierung der heutigen Assets (exakter Vergleich,
keine Toleranz — E4), keine Capability-Regel.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.mesh_geometry import mesh_bounds
from mirai.symmetry import SymmetryState

from symmetry_lab import lab_draw_data
from symmetry_lab.lab_bindings import apply_lab_bindings
from symmetry_lab.lab_dispatch import Change, LabDispatcher
from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import (
    AXIS_NORMALS,
    ORIGIN,
    current_axis,
    cycle_symmetry,
    definition_for_axis,
    derive_seam_edges,
    symmetry_report,
)

SHIFT_S = Input("key", "s", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))


def make_app(asset: str) -> Application:
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, asset)
    return app


def set_axis(app: Application, axis: str) -> None:
    app.scene.mesh.symmetry_definition = definition_for_axis(app.scene.mesh, axis)


# -- Seam-Ableitung (E3) --------------------------------------------------------


@pytest.mark.parametrize(
    "asset,axis,expected",
    [("subd_cube", "X", 8), ("subd_cube", "Z", 8), ("head_basemesh", "X", 36)],
)
def test_seam_edge_counts(asset, axis, expected):
    assert len(derive_seam_edges(make_app(asset).scene.mesh, axis)) == expected


def test_seam_edges_lie_exactly_on_the_plane():
    mesh = make_app("head_basemesh").scene.mesh
    for eid in derive_seam_edges(mesh, "X"):
        for vid in mesh.edge_vertices(eid):
            assert mesh.vertex_position(vid)[0] == 0.0


def test_definition_uses_origin_and_exact_unit_normal():
    mesh = make_app("subd_cube").scene.mesh
    for axis, normal in AXIS_NORMALS.items():
        definition = definition_for_axis(mesh, axis)
        assert definition.plane_point == (0.0, 0.0, 0.0)
        assert definition.plane_normal == normal
    assert definition_for_axis(mesh, None) is None


def test_seam_is_stored_declaration_not_live_check():
    # E3: nach dem Einschalten wird die Seam nicht neu geprüft — ein Seam-Vertex,
    # der die Ebene verlässt, bleibt Seam und zeigt sich als VIOLATED.
    app = make_app("subd_cube")
    cycle_symmetry(app.scene)
    mesh = app.scene.mesh
    seam = mesh.symmetry_definition.seam_edges
    vid = mesh.edge_vertices(next(iter(seam)))[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x + 0.25, y, z))
    assert mesh.symmetry_definition.seam_edges == seam
    assert symmetry_report(mesh).state is SymmetryState.VIOLATED


# -- Zyklus (A2, E1, E2) ----------------------------------------------------------


def test_cycle_off_x_y_z_off_one_history_entry_each():
    app = make_app("subd_cube")
    dispatcher = LabDispatcher(app, 1280, 800)
    mesh = app.scene.mesh
    seen = [mesh.symmetry_definition]
    for step, expected in enumerate(["X", "Y", "Z", None], start=1):
        assert dispatcher.key(SHIFT_S) is True
        assert current_axis(mesh) == expected
        if expected is None:
            assert mesh.symmetry_definition is None
        else:
            assert mesh.symmetry_definition.plane_normal == AXIS_NORMALS[expected]
            assert mesh.symmetry_definition.plane_point == ORIGIN
        assert len(app.history) == step
        assert Change.MESH in dispatcher.take_changes()
        seen.append(mesh.symmetry_definition)

    # Undo stellt jeweils die vorherige Definition exakt wieder her.
    for step in range(4, 0, -1):
        dispatcher.key(CTRL_Z)
        assert mesh.symmetry_definition == seen[step - 1]
        assert len(app.history) == step - 1


def test_cycle_does_not_touch_positions_or_topology():
    app = make_app("head_basemesh")
    mesh = app.scene.mesh
    before = mesh.export_state()
    cycle_symmetry(app.scene)
    after = mesh.export_state()
    assert after["symmetry"] is not None
    assert {k: v for k, v in after.items() if k != "symmetry"} == {
        k: v for k, v in before.items() if k != "symmetry"
    }


def test_cycle_keeps_selection():
    app = make_app("subd_cube")
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    app.scene.selection.set({vid})
    LabDispatcher(app).key(SHIFT_S)
    assert app.scene.selection.vertices == {vid}


# -- States (Charakterisierung, E4) ----------------------------------------------


@pytest.mark.parametrize(
    "asset,axis,state",
    [
        ("head_basemesh", "X", SymmetryState.VALID),
        ("subd_cube", "Y", SymmetryState.PARTIAL),
        ("man_with_shoes_basemesh", "X", SymmetryState.PARTIAL),
    ],
)
def test_symmetry_states(asset, axis, state):
    app = make_app(asset)
    set_axis(app, axis)
    assert symmetry_report(app.scene.mesh).state is state


def test_man_with_shoes_x_has_exactly_54_unpaired():
    app = make_app("man_with_shoes_basemesh")
    set_axis(app, "X")
    report = symmetry_report(app.scene.mesh)
    assert len(report.unpaired) == 54
    assert report.ambiguous == frozenset()


def test_report_off_is_empty():
    report = symmetry_report(make_app("subd_cube").scene.mesh)
    assert report.axis is None
    assert report.state is SymmetryState.OFF
    assert not (report.seam or report.unpaired or report.ambiguous)


def test_report_seam_vertices_match_seam_edges():
    app = make_app("subd_cube")
    set_axis(app, "X")
    mesh = app.scene.mesh
    endpoints = {
        v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)
    }
    assert symmetry_report(mesh).seam == endpoints


def test_current_axis_rejects_foreign_definition():
    from core import SymmetryDefinition

    mesh = make_app("subd_cube").scene.mesh
    mesh.symmetry_definition = SymmetryDefinition((1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        current_axis(mesh)


# -- Ebenen-Umriss ------------------------------------------------------------------


def test_plane_outline_off_is_empty():
    assert lab_draw_data.plane_outline_data(make_app("subd_cube").scene.mesh, None) == []


@pytest.mark.parametrize("axis,i", [("X", 0), ("Y", 1), ("Z", 2)])
def test_plane_outline_lies_in_plane_and_encloses_bounds(axis, i):
    mesh = make_app("head_basemesh").scene.mesh
    data = lab_draw_data.plane_outline_data(mesh, axis)
    assert len(data) == 4 * 2 * 3  # 4 Linien à 2 Punkte
    points = [data[k:k + 3] for k in range(0, len(data), 3)]
    assert all(p[i] == 0.0 for p in points)
    lo, hi = mesh_bounds(mesh)
    for j in (j for j in range(3) if j != i):
        assert min(p[j] for p in points) < lo[j]
        assert max(p[j] for p in points) > hi[j]

