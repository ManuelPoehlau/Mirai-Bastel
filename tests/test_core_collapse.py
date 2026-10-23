"""Core contract of Collapse V/E/F (WP Toolbox Gaps B1, `core.operations.collapse`).

Edge, edge chain, face group, quad strip, border edge and triangle degeneration, each checked
against `tests/mesh_invariants.py`, plus the groups rule, the refusals (mesh unchanged) and exact
Undo/Redo through the change journal.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core/

from core.mesh import Mesh
from core.operations import (
    CollapseRefused,
    MeshDeltaCommand,
    collapse_elements,
    collapse_groups,
    record_mesh_change,
)
from mirai.scene_factory import create_cube
from tests.mesh_invariants import assert_mesh_invariants


def _grid(cols: int, rows: int):
    """cols × rows quads in the XY plane, counter-clockwise; (mesh, vertices[(r, c)], faces[(r, c)])."""
    mesh = Mesh()
    p = {}
    for r in range(rows + 1):
        for c in range(cols + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    f = {}
    for r in range(rows):
        for c in range(cols):
            f[(r, c)] = mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p, f


def _edge(mesh: Mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _face_edges(mesh: Mesh, faces) -> set:
    return {e for f in faces for e in mesh.face_edges(f)}


def _face_vertices(mesh: Mesh, faces) -> set:
    return {v for f in faces for v in mesh.face_vertices(f)}


def _collapse(mesh: Mesh, vertices, edges=None):
    """Collapse under the journal, as `Application` runs it; returns (survivors, command)."""
    delta, survivors = record_mesh_change(mesh, lambda: collapse_elements(mesh, vertices, edges))
    assert_mesh_invariants(mesh, context="collapse")
    return survivors, MeshDeltaCommand(mesh=mesh, delta=delta, description="Collapse")


def _assert_undo_redo_exact(mesh: Mesh, before: dict, command: MeshDeltaCommand) -> None:
    after = mesh.export_state()
    command.undo()
    assert mesh.export_state() == before
    command.redo()
    assert mesh.export_state() == after
    assert_mesh_invariants(mesh, context="redo")


def test_single_edge_collapses_to_its_midpoint() -> None:
    mesh, p, f = _grid(2, 2)
    edge = _edge(mesh, p[(1, 0)], p[(1, 1)])
    kept, gone = mesh.edge_vertices(edge)  # collapse_edge keeps v0
    before = mesh.export_state()
    survivors, command = _collapse(mesh, mesh.edge_vertices(edge), [edge])

    assert survivors == [kept]
    assert not mesh.is_valid_vertex(gone) and not mesh.is_valid_edge(edge)
    assert mesh.vertex_position(kept) == (0.5, 1.0, 0.0)
    assert len(mesh.all_vertex_ids()) == 8
    assert sorted(len(mesh.face_vertices(x)) for x in mesh.all_face_ids()) == [3, 3, 4, 4]
    _assert_undo_redo_exact(mesh, before, command)


def test_edge_chain_is_one_group_at_its_centroid() -> None:
    mesh, p, _ = _grid(3, 2)
    chain = [p[(1, c)] for c in range(4)]
    edges = [_edge(mesh, chain[i], chain[i + 1]) for i in range(3)]
    before = mesh.export_state()
    survivors, command = _collapse(mesh, chain, edges)

    assert len(survivors) == 1
    assert mesh.vertex_position(survivors[0]) == (1.5, 1.0, 0.0)
    assert len(mesh.all_vertex_ids()) == 12 - 3
    assert all(len(mesh.face_vertices(x)) == 3 for x in mesh.all_face_ids())
    _assert_undo_redo_exact(mesh, before, command)


def test_face_group_collapses_to_one_point() -> None:
    mesh, p, f = _grid(4, 4)
    group = [f[(1, 1)], f[(1, 2)], f[(2, 1)], f[(2, 2)]]
    vertices = _face_vertices(mesh, group)
    before = mesh.export_state()
    survivors, command = _collapse(mesh, vertices, _face_edges(mesh, group))

    assert len(survivors) == 1
    assert mesh.vertex_position(survivors[0]) == (2.0, 2.0, 0.0)
    assert not any(mesh.is_valid_face(x) for x in group)
    assert len(mesh.all_vertex_ids()) == 25 - 8
    # The 8 faces that shared an edge with the group become triangles, the 4 corners stay quads.
    sizes = sorted(len(mesh.face_vertices(x)) for x in mesh.all_face_ids())
    assert sizes == [3] * 8 + [4] * 4
    _assert_undo_redo_exact(mesh, before, command)


def test_quad_strip_rungs_are_separate_groups() -> None:
    """Two rungs of a 1×3 strip, not connected to each other: two points; the quad between them
    degenerates, its two rails merge into one edge."""
    mesh, p, f = _grid(3, 1)
    rungs = [_edge(mesh, p[(0, c)], p[(1, c)]) for c in (1, 2)]
    vertices = {v for e in rungs for v in mesh.edge_vertices(e)}
    assert len(collapse_groups(mesh, vertices, rungs)) == 2
    before = mesh.export_state()
    survivors, command = _collapse(mesh, vertices, rungs)

    assert [mesh.vertex_position(v) for v in survivors] == [(1.0, 0.5, 0.0), (2.0, 0.5, 0.0)]
    assert not mesh.is_valid_face(f[(0, 1)])
    assert sorted(len(mesh.face_vertices(x)) for x in mesh.all_face_ids()) == [3, 3]
    _assert_undo_redo_exact(mesh, before, command)


def test_vertex_mode_groups_over_edges_between_selected_vertices() -> None:
    """Vertex selection: groups over the edges between two selected vertices; the opposite
    corners of a quad share no edge, so nothing changes (Blender "Merge at Center", per group)."""
    mesh, p, _ = _grid(2, 2)
    corners = [p[(0, 0)], p[(1, 1)]]
    assert collapse_groups(mesh, corners) == [[corners[0]], [corners[1]]]
    before = mesh.export_state()
    delta, survivors = record_mesh_change(mesh, lambda: collapse_elements(mesh, corners))
    assert delta.empty and survivors == corners
    assert mesh.export_state() == before

    row = [p[(0, 0)], p[(0, 1)], p[(0, 2)], p[(2, 2)]]
    groups = collapse_groups(mesh, row)
    assert groups == [[p[(0, 0)], p[(0, 1)], p[(0, 2)]], [p[(2, 2)]]]
    survivors, _ = _collapse(mesh, row)
    assert len(survivors) == 2 and mesh.vertex_position(survivors[0]) == (1.0, 0.0, 0.0)
    assert mesh.vertex_position(p[(2, 2)]) == (2.0, 2.0, 0.0)


def test_border_edge() -> None:
    mesh, p, f = _grid(2, 2)
    edge = _edge(mesh, p[(0, 0)], p[(0, 1)])
    before = mesh.export_state()
    survivors, command = _collapse(mesh, mesh.edge_vertices(edge), [edge])

    assert mesh.vertex_position(survivors[0]) == (0.5, 0.0, 0.0)
    assert len(mesh.face_vertices(f[(0, 0)])) == 3
    assert len(mesh.all_face_ids()) == 4
    _assert_undo_redo_exact(mesh, before, command)


def test_triangle_degenerates_and_its_edges_merge() -> None:
    """A quad split into two triangles: collapsing an outer edge of one triangle removes that
    triangle; its two other edges merge into one, so no stale edge is left."""
    mesh = Mesh()
    a = mesh.add_vertex((0.0, 0.0, 0.0))
    b = mesh.add_vertex((1.0, 0.0, 0.0))
    c = mesh.add_vertex((1.0, 1.0, 0.0))
    d = mesh.add_vertex((0.0, 1.0, 0.0))
    t1 = mesh.add_face([a, b, c])
    t2 = mesh.add_face([a, c, d])
    edge = _edge(mesh, a, b)
    before = mesh.export_state()
    survivors, command = _collapse(mesh, [a, b], [edge])

    assert not mesh.is_valid_face(t1) and mesh.is_valid_face(t2)
    assert survivors == [a] and mesh.vertex_position(a) == (0.5, 0.0, 0.0)
    assert len(mesh.all_edge_ids()) == 3
    assert {len(mesh.edge_faces(e)) for e in mesh.all_edge_ids()} == {1}
    _assert_undo_redo_exact(mesh, before, command)


def test_cube_face_becomes_an_apex() -> None:
    mesh = create_cube()
    top = max(
        mesh.all_face_ids(),
        key=lambda x: sum(mesh.vertex_position(v)[1] for v in mesh.face_vertices(x)),
    )
    before = mesh.export_state()
    survivors, command = _collapse(mesh, mesh.face_vertices(top), mesh.face_edges(top))

    assert len(mesh.all_vertex_ids()) == 5 and len(mesh.all_face_ids()) == 5
    x, y, z = mesh.vertex_position(survivors[0])
    assert abs(x) < 1e-12 and abs(z) < 1e-12 and y > 0
    _assert_undo_redo_exact(mesh, before, command)


def test_pinched_face_is_refused_and_mesh_untouched() -> None:
    """The opposite corners of the centre quad joined by a path around it: merged, the quad would
    hold one vertex twice."""
    mesh, p, _ = _grid(3, 3)
    path = [p[(1, 1)], p[(0, 1)], p[(0, 2)], p[(0, 3)], p[(1, 3)], p[(2, 3)], p[(2, 2)]]
    edges = [_edge(mesh, path[i], path[i + 1]) for i in range(len(path) - 1)]
    before = mesh.export_state()
    with pytest.raises(CollapseRefused):
        record_mesh_change(mesh, lambda: collapse_elements(mesh, path, edges))
    assert mesh.export_state() == before


def test_tetrahedron_edge_is_refused_two_faces_would_coincide() -> None:
    mesh = Mesh()
    a = mesh.add_vertex((0.0, 0.0, 0.0))
    b = mesh.add_vertex((1.0, 0.0, 0.0))
    c = mesh.add_vertex((0.0, 1.0, 0.0))
    d = mesh.add_vertex((0.0, 0.0, 1.0))
    for face in ([a, c, b], [a, b, d], [b, c, d], [a, d, c]):
        mesh.add_face(face)
    before = mesh.export_state()
    with pytest.raises(CollapseRefused):
        collapse_elements(mesh, [a, b], [_edge(mesh, a, b)])
    assert mesh.export_state() == before


def test_edge_with_more_than_two_faces_is_refused() -> None:
    """Link condition: x and y share the neighbour w, but no face holds all three. Merged, the
    edges x-w and y-w become one edge on four faces."""
    mesh = Mesh()
    x = mesh.add_vertex((0.0, 0.0, 0.0))
    y = mesh.add_vertex((1.0, 0.0, 0.0))
    w = mesh.add_vertex((0.5, 1.0, 0.0))
    e = mesh.add_vertex((0.5, -1.0, 0.0))
    a, b, c, d = (mesh.add_vertex((float(i), 2.0, 1.0)) for i in range(4))
    for face in ([x, w, a], [w, x, b], [y, w, c], [w, y, d], [x, y, e]):
        mesh.add_face(face)
    before = mesh.export_state()
    with pytest.raises(CollapseRefused):
        collapse_elements(mesh, [x, y])
    assert mesh.export_state() == before


@pytest.mark.parametrize("seed", range(40))
def test_random_edge_selections_are_valid_or_refused_untouched(seed) -> None:
    """Randomised: on a sphere (triangle poles, quads), a cube and a grid, any edge selection
    either collapses to valid topology with exact Undo/Redo, or is refused with the mesh
    untouched."""
    import random

    from mirai.scene_factory import create_sphere

    rng = random.Random(seed)
    mesh = [create_sphere, create_cube, lambda: _grid(4, 3)[0]][seed % 3]()
    edges = sorted(mesh.all_edge_ids(), key=int)
    picked = rng.sample(edges, rng.randint(1, min(8, len(edges))))
    vertices = {v for e in picked for v in mesh.edge_vertices(e)}
    before = mesh.export_state()
    try:
        _, command = _collapse(mesh, vertices, picked)
    except CollapseRefused:
        assert mesh.export_state() == before
        return
    _assert_undo_redo_exact(mesh, before, command)
