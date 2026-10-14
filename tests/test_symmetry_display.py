"""The symmetry report and plane outline (`mirai.symmetry_display`), AD-SYM-04 slice A2.

Moved with the functions from the Symmetry Lab (`experiments/symmetry_lab/tests/test_lab_symmetry.py`,
K-2: moved, not copied). The numbers characterise today's assets (exact comparison, no tolerance -
E4), they are no capability rule. The display itself (`SymmetryDisplay` in `Application`) is
`test_application_symmetry_display.py`.
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from loaders.assets import asset_path  # noqa: E402
from mirai.mesh_geometry import mesh_bounds  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.symmetry import SymmetryState  # noqa: E402
from mirai.symmetry_axis import AXIS_INDEX, definition_for_axis  # noqa: E402
from mirai.symmetry_display import (  # noqa: E402
    PLANE_MARGIN,
    geometry_signature,
    only_positions_differ,
    plane_outline_data,
    symmetry_report,
)


def mesh_of(asset: str, axis: str | None = None):
    mesh = build_core_scene_from_obj(asset_path(asset)).mesh
    if axis is not None:
        mesh.symmetry_definition = definition_for_axis(mesh, axis)
    return mesh


# -- States (characterisation, E4) ------------------------------------------------------------


@pytest.mark.parametrize(
    "asset,axis,state",
    [
        ("head_basemesh", "X", SymmetryState.VALID),
        ("subd_cube", "Y", SymmetryState.PARTIAL),
        ("man_with_shoes_basemesh", "X", SymmetryState.PARTIAL),
    ],
)
def test_symmetry_states(asset, axis, state):
    assert symmetry_report(mesh_of(asset, axis)).state is state


def test_man_with_shoes_x_has_exactly_54_unpaired():
    report = symmetry_report(mesh_of("man_with_shoes_basemesh", "X"))
    assert len(report.unpaired) == 54
    assert report.ambiguous == frozenset()


def test_report_off_is_empty():
    report = symmetry_report(mesh_of("subd_cube"))
    assert report.axis is None
    assert report.state is SymmetryState.OFF
    assert not (report.seam or report.unpaired or report.ambiguous)
    assert report.correspondence is None


def test_report_seam_vertices_match_seam_edges():
    mesh = mesh_of("subd_cube", "X")
    endpoints = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    assert symmetry_report(mesh).seam == endpoints


# -- Plane outline --------------------------------------------------------------------------------


def test_outline_is_empty_while_off():
    assert plane_outline_data(mesh_of("subd_cube"), None) == []


@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
def test_outline_lies_in_the_plane_and_encloses_the_bounds_by_the_margin(axis):
    mesh = mesh_of("head_basemesh", axis)
    flat = plane_outline_data(mesh, axis)
    points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    assert len(points) == 8  # 4 lines x 2 ends, closed loop
    i = AXIS_INDEX[axis]
    assert all(p[i] == 0.0 for p in points)
    lo, hi = mesh_bounds(mesh)
    u, w = (j for j in range(3) if j != i)
    pad = PLANE_MARGIN * max(hi[u] - lo[u], hi[w] - lo[w])
    for j in (u, w):
        assert min(p[j] for p in points) == pytest.approx(lo[j] - pad)
        assert max(p[j] for p in points) == pytest.approx(hi[j] + pad)


# -- Change signature (plan A3 deferral) -------------------------------------------------------


def test_only_a_pure_position_change_counts_as_position_only():
    mesh = mesh_of("subd_cube", "X")
    before = geometry_signature(mesh)
    vid = sorted(mesh.all_vertex_ids(), key=int)[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x, y + 0.5, z))
    moved = geometry_signature(mesh)
    assert moved != before and only_positions_differ(before, moved)
    mesh.symmetry_definition = definition_for_axis(mesh, "Y")
    assert not only_positions_differ(moved, geometry_signature(mesh))
    assert not only_positions_differ(None, moved)
