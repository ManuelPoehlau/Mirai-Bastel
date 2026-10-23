"""Smooth / Relax maths and plan (WP Toolbox Gaps C2): `core.operations.smooth.smooth_positions` and
`mirai.topology.smooth.plan_smooth`."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401

from core.mesh import Mesh
from core.operations.smooth import SMOOTH_FACTOR, smooth_positions
from mirai.scene_factory import create_sphere
from mirai.topology.smooth import SmoothRefused, plan_smooth


def _grid(n: int = 4, jitter: dict | None = None) -> tuple[Mesh, dict]:
    mesh = Mesh()
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            x, y, z = float(c), float(r), 0.0
            if jitter and (r, c) in jitter:
                x, y, z = (a + b for a, b in zip((x, y, z), jitter[(r, c)]))
            p[(r, c)] = mesh.add_vertex((x, y, z))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p


def _apply(mesh: Mesh, positions: dict) -> None:
    for v, q in positions.items():
        mesh.set_vertex_position(v, q)


def test_one_smooth_step_moves_halfway_to_the_neighbour_mean():
    positions = {"a": (0.0, 0.0, 0.0), "b": (2.0, 0.0, 0.0), "c": (0.0, 2.0, 0.0)}
    result = smooth_positions(positions, {"a": ["b", "c"]}, ["a"], 1.0)
    assert result == {"a": (0.5, 0.5, 0.0)}
    assert SMOOTH_FACTOR == 0.5


def test_amount_zero_changes_nothing_and_amount_is_continuous():
    positions = {"a": (0.0, 0.0, 0.0), "b": (2.0, 0.0, 0.0)}
    assert smooth_positions(positions, {"a": ["b"]}, ["a"], 0.0) == {}
    near = smooth_positions(positions, {"a": ["b"]}, ["a"], 1e-9)["a"]
    assert near[0] == pytest.approx(0.0, abs=1e-8)
    below = smooth_positions(positions, {"a": ["b"]}, ["a"], 1.0 - 1e-9)["a"]
    at = smooth_positions(positions, {"a": ["b"]}, ["a"], 1.0)["a"]
    assert below[0] == pytest.approx(at[0], abs=1e-8)


def test_smooth_pulls_a_bump_back_and_converges():
    mesh, p = _grid(jitter={(2, 2): (0.0, 0.0, 1.0)})
    plan = plan_smooth(mesh, [p[(2, 2)]], relax=False)
    heights = [plan.positions(a)[p[(2, 2)]][2] for a in (0, 1, 2, 4, 8, 16)]
    assert heights[0] == 1.0
    assert all(b < a for a, b in zip(heights, heights[1:]))
    assert heights[-1] < 1e-4


def test_relax_on_a_flat_grid_never_leaves_the_plane_and_evens_the_spacing():
    """Planar grid with one point pushed sideways: Relax moves it back toward the middle, in the plane."""
    mesh, p = _grid(jitter={(2, 2): (0.4, -0.3, 0.0)})
    inner = [p[(r, c)] for r in (1, 2, 3) for c in (1, 2, 3)]
    plan = plan_smooth(mesh, inner, relax=True)
    result = plan.positions(6.0)
    assert all(q[2] == 0.0 for q in result.values())
    assert math.dist(result[p[(2, 2)]], (2.0, 2.0, 0.0)) < math.dist(mesh.vertex_position(p[(2, 2)]), (2.0, 2.0, 0.0))


def test_relax_keeps_the_shape_better_than_smooth_on_a_sphere():
    mesh = create_sphere()
    vids = mesh.all_vertex_ids()
    radius = max(math.dist(mesh.vertex_position(v), (0.0, 0.0, 0.0)) for v in vids)

    def shrink(relax: bool) -> float:
        result = plan_smooth(mesh, vids, relax=relax).positions(4.0)
        return sum(radius - math.dist(q, (0.0, 0.0, 0.0)) for q in result.values()) / len(result)

    assert shrink(True) < shrink(False) * 0.5


def test_border_points_stay_fixed():
    mesh, p = _grid(2)
    plan = plan_smooth(mesh, mesh.all_vertex_ids(), relax=False)
    assert plan.movable == {p[(1, 1)]}
    with pytest.raises(SmoothRefused, match="border"):
        plan_smooth(mesh, [p[(0, 0)], p[(0, 1)]], relax=False)
