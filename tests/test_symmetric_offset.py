"""The symmetric coordinator of the width gestures (`mirai.symmetric_offset`, 2026-10-29).

Pinned: `place` writes each mirror pair of new vertices as an exact mirror (the normal's side drives,
whatever rounding the other side had) and projects a vertex that is its own partner onto the plane;
the partners of old elements are read before the build (the build removes many of them, and vertex,
edge and face ids are separate key spaces); `finish` adds the created edges on the plane to the seam
and refuses an unmirrored result (the gesture is then taken back)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from mirai.symmetric_offset import OffsetSymmetryRefusal, plan_bevel, plan_inset
from mirai.symmetric_ops import SymmetryRefusal
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import set_symmetry_axis
from mirai.topology.bevel import build_bevel, plan_bevel as plan_plain_bevel
from mirai.topology.inset import build_inset, plan_inset as plan_plain_inset
from tests.test_bevel import _edge, _grid, _vertex
from tests.test_inset import _face


def _perturbed(positions):
    """The positions with every vertex on the -X side nudged off its mirror image."""
    return {v: (p[0] - 1e-3, p[1] + 2e-3, p[2]) if p[0] < 0.0 else p for v, p in positions.items()}


def _assert_exact_pairs(mesh, placed):
    by_pos = set(placed.values())
    for p in placed.values():
        assert (-p[0], p[1], p[2]) in by_pos, p


def test_place_mirrors_a_bevel_exactly_and_finish_keeps_the_symmetry():
    mesh = _grid()
    set_symmetry_axis(mesh, "X")
    seed = _edge(mesh, _vertex(mesh, 0.0, 0.0), _vertex(mesh, 1.0, 0.0))  # its mirror shares the seam vertex
    union, symmetric = plan_bevel(mesh, SelectionMode.EDGE, {seed})
    assert len(union) == 2
    change = mesh.begin_change()
    result = build_bevel(mesh, plan_plain_bevel(mesh, SelectionMode.EDGE, union))
    placed = symmetric.place(result.keys, _perturbed(result.positions(0.25)))
    _assert_exact_pairs(mesh, placed)
    on_plane = [p for p in placed.values() if p[0] == 0.0]
    assert len(on_plane) == 2  # the two seam slides, exactly on the plane
    for v, p in placed.items():
        mesh.set_vertex_position(v, p)
    symmetric.finish(mesh, change)
    mesh.end_change(change)
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_place_projects_the_seam_copies_of_an_inset_across_the_plane():
    mesh = _grid()
    set_symmetry_axis(mesh, "X")
    union, symmetric = plan_inset(mesh, {_face(mesh, 0.0, 0.0)})
    assert len(union) == 2
    change = mesh.begin_change()
    result = build_inset(mesh, plan_plain_inset(mesh, union))
    raw = result.positions(0.2)
    raw = {v: (p[0] + 1e-4, p[1], p[2]) for v, p in raw.items()}  # everything off by a hair
    placed = symmetric.place(result.keys, raw)
    _assert_exact_pairs(mesh, placed)
    assert sum(1 for p in placed.values() if p[0] == 0.0) == 2
    for v, p in placed.items():
        mesh.set_vertex_position(v, p)
    symmetric.finish(mesh, change)
    mesh.end_change(change)
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_finish_refuses_an_unmirrored_result():
    mesh = _grid()
    set_symmetry_axis(mesh, "X")
    union, symmetric = plan_inset(mesh, {_face(mesh, 1.0, 0.0)})
    change = mesh.begin_change()
    result = build_inset(mesh, plan_plain_inset(mesh, union))
    for v, p in _perturbed(result.positions(0.2)).items():  # not placed: the -X side is off
        mesh.set_vertex_position(v, p)
    with pytest.raises(OffsetSymmetryRefusal):
        symmetric.finish(mesh, change)
    mesh.rollback_change(change)


def test_planners_refuse_unpaired_and_plane_elements():
    mesh = _grid()
    set_symmetry_axis(mesh, "X")
    with pytest.raises(SymmetryRefusal, match="Mitte"):
        plan_bevel(mesh, SelectionMode.VERTEX, {_vertex(mesh, 0.0, 0.0)})
    mesh.set_vertex_position(_vertex(mesh, 1.0, 1.0), (1.25, 1.0, 0.0))  # breaks one pair
    with pytest.raises(SymmetryRefusal, match="Spiegelpartner"):
        plan_bevel(mesh, SelectionMode.VERTEX, {_vertex(mesh, 1.25, 1.0)})
