"""T-3 of AD-SYM-05 §6: non-symmetric Soft is bit-identical to Q2-D after SS1.

The oracle is `tests/soft_replay.replay`, a pure copy of the pre-SS1 arithmetic (no Core base
class), so it cannot follow the Core change (review CLAUDE-001 R-4). Inputs: the AD-020 P-D
set (head, a vertex plus its one-ring, pivot = their centroid, 60 random updates per gesture,
fixed oblique axis, tilted basis) and the existing step lists of `test_soft_selection_ops.py`
(`ROTATE_STEPS` changes the axis at step 3), each at radius 0, the 15 % step of the bounding
radius and 1.0, both metrics. Same platform as the ops, so libm cannot differ.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

import pytest

import tests._bootstrap  # noqa: F401

from core import HistoryStack, OperationContext
from mirai.interaction.tools.selection_helpers import _VertexSelectionView as _InfluenceView
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.soft_selection import (
    SoftMoveOperation,
    SoftRotateOperation,
    SoftScaleOperation,
    compute_influence,
    primary_pivot,
)
from tests.soft_replay import replay
from tests.soft_selection_fixtures import head

_C, _S = math.cos(math.pi / 6), math.sin(math.pi / 6)
TILTED = ((_C, _S, 0.0), (-_S, _C, 0.0), (0.0, 0.0, 1.0))

# The step lists of tests/test_soft_selection_ops.py (copied: that module is a test module).
MOVE_STEPS = [{"delta": (0.1, -0.03, 0.02)}, {"delta": (0.07, 0.2, -0.1)}, {"delta": (-0.3, 0.01, 0.0)}]
ROTATE_STEPS = [{"axis": (0.2, 1.0, 0.1), "angle": 0.3}, {"axis": (0.2, 1.0, 0.1), "angle": -0.11},
                {"axis": (1.0, 0.0, 0.0), "angle": 0.7}]
SCALE_STEPS = [{"factor": 1.3}, {"factor": (0.9, 1.0, 1.2)}, {"factor": 0.7}]
SCALE_BASIS_STEPS = [{"factor": (1.4, 1.0, 1.0), "basis": TILTED}, {"factor": (0.8, 1.0, 1.0), "basis": TILTED}]


def _pd_steps(op: str, n: int = 60, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    if op == "move":
        return [{"delta": tuple(rng.uniform(-0.05, 0.05) for _ in range(3))} for _ in range(n)]
    if op == "rotate":
        return [{"axis": (0.3, 1.0, -0.2), "angle": rng.uniform(-0.1, 0.1)} for _ in range(n)]
    return [{"factor": tuple(rng.uniform(0.97, 1.03) for _ in range(3)), "basis": TILTED}
            for _ in range(n)]


CASES = {
    "move/pd": ("move", _pd_steps("move")),
    "rotate/pd": ("rotate", _pd_steps("rotate")),
    "scale/pd": ("scale", _pd_steps("scale")),
    "move/list": ("move", MOVE_STEPS),
    "rotate/list": ("rotate", ROTATE_STEPS),
    "scale/list": ("scale", SCALE_STEPS),
    "scale/basis-list": ("scale", SCALE_BASIS_STEPS),
}
OPS = {"move": SoftMoveOperation, "rotate": SoftRotateOperation, "scale": SoftScaleOperation}


@lru_cache(maxsize=None)
def _seeds_and_pivot():
    mesh = head()
    first = mesh.all_vertex_ids()[100]
    seeds = {first}
    for eid in mesh.vertex_edges(first):
        seeds.update(mesh.edge_vertices(eid))
    return frozenset(seeds), primary_pivot(mesh, seeds), mesh_center_and_radius(mesh)[1]


@lru_cache(maxsize=None)
def _influence(radius_kind: str, metric: str):
    seeds, _, bounding = _seeds_and_pivot()
    radius = {"zero": 0.0, "15%": 0.15 * bounding, "one": 1.0}[radius_kind]
    return tuple(compute_influence(head(), set(seeds), radius, metric=metric, curve="smooth").items())


@pytest.mark.parametrize("metric", ["euclidean", "geodesic"])
@pytest.mark.parametrize("radius_kind", ["zero", "15%", "one"])
@pytest.mark.parametrize("case", sorted(CASES))
def test_soft_ops_replay_the_q2d_arithmetic_bit_for_bit(case, radius_kind, metric):
    op_name, steps = CASES[case]
    _, pivot, _ = _seeds_and_pivot()
    influence = dict(_influence(radius_kind, metric))
    if radius_kind != "zero":
        assert any(w < 1.0 for w in influence.values())
    mesh = head()
    start = {v: mesh.vertex_position(v) for v in influence}
    after, begin, end = replay(op_name, start, influence, pivot, steps)

    op = OPS[op_name](OperationContext(
        target=mesh, selection=_InfluenceView(set(influence)), history=HistoryStack(),
        params={"influence": dict(influence), "pivot": pivot},
    ))
    op.begin()
    for kwargs, expected in zip(steps, after):
        op.update(**kwargs)
        assert {v: mesh.vertex_position(v) for v in influence} == expected
    command = op.commit()
    assert command.start_positions == begin
    assert command.end_positions == end
