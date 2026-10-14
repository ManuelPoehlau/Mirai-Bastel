"""Symmetrie-Befund (Handoff Slice 3 §2 E4, §7) — reine Tests von `lab_symmetry`.

Die Zahlen sind Charakterisierung der heutigen Assets (exakter Vergleich,
keine Toleranz — E4), keine Capability-Regel. Der Zyklus (Shift+S), die
Seam-als-Deklaration-Probe und der Ebenen-Umriss laufen seit WP-SYM-LAB-03 auf dem
App-Pfad: `test_app_lab_cycle.py` (Plan A2-Tabelle, Slice 5). Die Tests von Seam-Ableitung,
Definition und `current_axis` (E1/E3) sind mit den Funktionen nach `tests/test_symmetry_axis.py`
gezogen (AD-SYM-04 A1, 2026-10-14).
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.symmetry import SymmetryState
from mirai.symmetry_axis import definition_for_axis

from symmetry_lab.lab_scene import load_asset_into
from symmetry_lab.lab_symmetry import symmetry_report


def make_app(asset: str) -> Application:
    app = Application()
    load_asset_into(app, asset)
    return app


def set_axis(app: Application, axis: str) -> None:
    app.scene.mesh.symmetry_definition = definition_for_axis(app.scene.mesh, axis)


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
