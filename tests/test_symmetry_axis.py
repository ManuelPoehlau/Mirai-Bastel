"""E1/E3 axis definitions (`mirai.symmetry_axis`), AD-SYM-04 slice A1.

Moved with the functions from the Symmetry Lab (`experiments/symmetry_lab/tests/test_lab_symmetry.py`,
K-2: moved, not copied). The seam counts characterise today's assets (exact comparison, no
tolerance - E4), they are no capability rule.
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SymmetryDefinition  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.symmetry_axis import (  # noqa: E402
    AXIS_NORMALS,
    ORIGIN,
    SYMMETRY_CYCLE,
    current_axis,
    definition_for_axis,
    derive_seam_edges,
    next_axis,
    set_symmetry_axis,
)


def mesh_of(asset: str):
    return build_core_scene_from_obj(asset_path(asset)).mesh


@pytest.mark.parametrize(
    "asset,axis,expected",
    [("subd_cube", "X", 8), ("subd_cube", "Z", 8), ("head_basemesh", "X", 36)],
)
def test_seam_edge_counts(asset, axis, expected):
    assert len(derive_seam_edges(mesh_of(asset), axis)) == expected


def test_seam_edges_lie_exactly_on_the_plane():
    mesh = mesh_of("head_basemesh")
    for eid in derive_seam_edges(mesh, "X"):
        for vid in mesh.edge_vertices(eid):
            assert mesh.vertex_position(vid)[0] == 0.0


def test_definition_uses_origin_and_exact_unit_normal():
    mesh = mesh_of("subd_cube")
    for axis, normal in AXIS_NORMALS.items():
        definition = definition_for_axis(mesh, axis)
        assert definition.plane_point == ORIGIN
        assert definition.plane_normal == normal
    assert definition_for_axis(mesh, None) is None


def test_cycle_order_and_set_axis_round_trip():
    assert SYMMETRY_CYCLE == (None, "X", "Y", "Z")
    assert [next_axis(a) for a in SYMMETRY_CYCLE] == ["X", "Y", "Z", None]
    mesh = mesh_of("subd_cube")
    for axis in SYMMETRY_CYCLE:
        set_symmetry_axis(mesh, axis)
        assert current_axis(mesh) == axis
        assert mesh.symmetry_definition == definition_for_axis(mesh, axis)


def test_current_axis_rejects_foreign_definition():
    """K-1: a definition outside E1 is an error, never silently read as one of the axes."""
    mesh = mesh_of("subd_cube")
    mesh.symmetry_definition = SymmetryDefinition((1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        current_axis(mesh)
