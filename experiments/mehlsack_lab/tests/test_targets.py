"""§7.2 Loop/Ring on the box (rules of `playground.topology_tools.loop_ring`, unchanged), and
the `TopologyIndex` returns the same traversal as the raw mesh for every edge."""

from __future__ import annotations

import pytest

from mehlsack_lab.box import BoxParams, build_box_mesh
from mehlsack_lab.targets import MODE_LOOP, MODE_RING, TargetFinder, TopologyIndex
from playground.topology_tools.loop_ring import edge_loop, edge_ring

from .helpers import horizontal_edge


@pytest.mark.parametrize("h,n", [(2, 1), (4, 3), (6, 5)])
def test_mid_height_loop_is_closed_with_4n_edges(h, n):
    mesh = build_box_mesh(BoxParams(h=h, n=n))
    target = TargetFinder(mesh).target(horizontal_edge(mesh, 0.0), MODE_LOOP)
    assert target.closed
    assert len(target.edges) == 4 * n
    assert len(set(target.edges)) == 4 * n
    # all at mid height: the seeds are exactly the 4n vertices of that row
    assert len(target.seeds) == 4 * n
    assert all(abs(mesh.vertex_position(v)[1]) < 1e-12 for v in target.seeds)


@pytest.mark.parametrize("h,n", [(1, 1), (3, 2), (4, 4)])
def test_ring_is_closed(h, n):
    mesh = build_box_mesh(BoxParams(h=h, n=n))
    finder = TargetFinder(mesh)
    for eid in mesh.all_edge_ids()[:: max(1, len(mesh.all_edge_ids()) // 15)]:
        target = finder.target(eid, MODE_RING)
        assert target.closed, eid


@pytest.mark.parametrize("n", [2, 3, 5])
def test_rim_loop_stops_at_the_corners(n):
    """Rim corners have valence 3: the loop runs along one side's rim and stops (n edges, open)."""
    mesh = build_box_mesh(BoxParams(h=3, n=n))
    target = TargetFinder(mesh).target(horizontal_edge(mesh, 1.0), MODE_LOOP)
    assert not target.closed
    assert len(target.edges) == n


def test_unit_box_still_has_targets():
    mesh = build_box_mesh(BoxParams(h=1, n=1))
    finder = TargetFinder(mesh)
    for eid in mesh.all_edge_ids():
        loop = finder.target(eid, MODE_LOOP)
        ring = finder.target(eid, MODE_RING)
        assert loop.edges == (eid,) and not loop.closed and len(loop.seeds) == 2
        assert len(ring.edges) == 4 and ring.closed and len(ring.seeds) == 8


def test_anchor_is_a_seed():
    mesh = build_box_mesh(BoxParams(h=3, n=2))
    finder = TargetFinder(mesh)
    for eid in mesh.all_edge_ids():
        for mode in (MODE_LOOP, MODE_RING):
            target = finder.target(eid, mode)
            assert target.anchor in target.seeds and target.anchor in mesh.edge_vertices(eid)


@pytest.mark.parametrize("h,n", [(1, 1), (3, 2), (4, 3)])
def test_index_traversals_equal_raw_mesh_traversals(h, n):
    """The index is only a faster query surface: every loop and ring is the one
    `loop_ring` finds on the Core mesh itself (same edges, same order, same `closed`)."""
    mesh = build_box_mesh(BoxParams(h=h, n=n))
    index = TopologyIndex(mesh)
    for eid in mesh.all_edge_ids():
        assert edge_loop(index, eid) == edge_loop(mesh, eid)
        assert edge_ring(index, eid) == edge_ring(mesh, eid)
        assert index.vertex_edges(mesh.edge_vertices(eid)[0]) == mesh.vertex_edges(mesh.edge_vertices(eid)[0])


def test_unknown_mode_refused():
    mesh = build_box_mesh(BoxParams())
    with pytest.raises(ValueError):
        TargetFinder(mesh).target(mesh.all_edge_ids()[0], "spiral")
