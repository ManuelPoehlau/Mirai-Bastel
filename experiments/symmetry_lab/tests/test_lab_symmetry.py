"""Seam-Ableitung, Definition und States (Handoff Slice 3 §2 E1–E4, §7) — reine Tests
von `lab_symmetry`.

Die Zahlen sind Charakterisierung der heutigen Assets (exakter Vergleich,
keine Toleranz — E4), keine Capability-Regel. Der Zyklus (Shift+S), die
Seam-als-Deklaration-Probe und der Ebenen-Umriss laufen seit WP-SYM-LAB-03 auf dem
App-Pfad: `test_app_lab_cycle.py` (Plan A2-Tabelle, Slice 5).
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.symmetry import SymmetryState

from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import (
    AXIS_NORMALS,
    current_axis,
    definition_for_axis,
    derive_seam_edges,
    symmetry_report,
)


def make_app(asset: str) -> Application:
    app = Application()
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
