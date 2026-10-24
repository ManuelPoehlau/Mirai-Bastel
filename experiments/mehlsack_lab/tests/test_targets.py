"""§7.2 Loop/Ring on the box (rules of `mirai.topology.loop_ring`, unchanged), and
the `TopologyIndex` returns the same traversal as the raw mesh for every edge. Slice 2a E15:
with the box's rims given, a Loop on a rim edge runs closed around the corners; every other
Loop and every Ring stays `loop_ring`'s."""

from __future__ import annotations

import pytest

from mehlsack_lab.box import BoxParams, box_rims, build_box_mesh
from mehlsack_lab.targets import MODE_LOOP, MODE_RING, TargetFinder, TopologyIndex
from mirai.topology.loop_ring import edge_loop, edge_ring

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
def test_without_rims_the_rim_loop_stops_at_the_corners(n):
    """`loop_ring`'s own rule (no override given): rim corners have valence 3, the loop runs
    along one side's rim and stops (n edges, open)."""
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


def _is_cap(mesh, face) -> bool:
    return len({mesh.vertex_position(v)[1] for v in mesh.face_vertices(face)}) == 1


def _rim_finder(params):
    mesh = build_box_mesh(params)
    return mesh, TargetFinder(mesh, box_rims(mesh, params))


@pytest.mark.parametrize("h,n", [(1, 1), (1, 3), (2, 1), (3, 2), (4, 4), (6, 5)])
def test_rim_loops_are_closed_with_4n_edges(h, n):
    params = BoxParams(height=2.0, width=1.5, depth=0.75, h=h, n=n)
    mesh, finder = _rim_finder(params)
    for y in (-1.0, 1.0):
        # independent of the override: edges at that height between a cap face and a wall face
        rim_edges = [e for e in mesh.all_edge_ids()
                     if all(mesh.vertex_position(v)[1] == y for v in mesh.edge_vertices(e))
                     and sorted(_is_cap(mesh, f) for f in mesh.edge_faces(e)) == [False, True]]
        assert len(rim_edges) == 4 * n
        assert all(e in finder.rim_of_edge for e in rim_edges)
        loops = set()
        for eid in rim_edges:
            target = finder.target(eid, MODE_LOOP)
            assert target.closed and len(target.edges) == len(set(target.edges)) == 4 * n
            assert target.edges[0] == eid  # hovered edge first, like a closed loop_ring traversal
            assert len(target.seeds) == 4 * n
            assert all(mesh.vertex_position(v)[1] == y for v in target.seeds)
            assert target.anchor in target.seeds
            loops.add(frozenset(target.edges))
        assert len(loops) == 1  # every edge of a rim yields the same loop
        # consecutive edges share a vertex: one chain around the corners
        edges = finder.target(rim_edges[0], MODE_LOOP).edges
        for a, b in zip(edges, edges[1:] + edges[:1]):
            assert set(mesh.edge_vertices(a)) & set(mesh.edge_vertices(b))


@pytest.mark.parametrize("h,n", [(1, 1), (3, 2), (4, 3)])
def test_rim_override_leaves_every_other_loop_and_every_ring_to_loop_ring(h, n):
    params = BoxParams(h=h, n=n)
    mesh, finder = _rim_finder(params)
    index = TopologyIndex(mesh)
    assert len(finder.rim_of_edge) == 8 * n
    for eid in mesh.all_edge_ids():
        ring = finder.target(eid, MODE_RING)
        traversal = edge_ring(index, eid)
        assert (list(ring.edges), ring.closed) == (traversal.edges, traversal.closed)
        if eid in finder.rim_of_edge:
            continue
        loop = finder.target(eid, MODE_LOOP)
        traversal = edge_loop(index, eid)
        assert (list(loop.edges), loop.closed) == (traversal.edges, traversal.closed)


def test_vertical_corner_edges_still_stop_at_the_corners():
    params = BoxParams(h=3, n=2)
    mesh, finder = _rim_finder(params)
    corner = [e for e in mesh.all_edge_ids()
              if all(abs(mesh.vertex_position(v)[0]) == 1.0 and abs(mesh.vertex_position(v)[2]) == 1.0
                     for v in mesh.edge_vertices(e))]
    assert corner
    for eid in corner:
        target = finder.target(eid, MODE_LOOP)
        assert not target.closed and len(target.edges) == 3  # the corner column, rim to rim


def test_bad_rim_cycle_refused():
    mesh = build_box_mesh(BoxParams(h=2, n=2))
    ids = mesh.all_vertex_ids()
    with pytest.raises(ValueError):
        TargetFinder(mesh, [(ids[0], ids[5], ids[9])])
