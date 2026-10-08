"""AD-SYM-03 slice 4: symmetric Split through `C` (`coordinate_split` in `mirai.symmetric_ops`,
wired in `Application._connect_command`).

Headless, no gate: the coordinator runs whenever a definition is set, in MARK as in BLOCK (AD-013
H2 amendment, "Runtime refusals are not G-3"); the Lab path is tested in
`experiments/symmetry_lab/tests/test_app_lab_symmetric_split.py`. Assets and helpers as in
`tests/test_symmetric_ops.py`, but axis-aware: `subd_cube` is exact on the X and Z planes,
`head_basemesh` on the X plane (the Y plane of `subd_cube` is not exact: `partial`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401 — production path src/core, src/mirai

from core import SelectionMode
from core.mesh import SymmetryDefinition
from mirai import symmetric_ops
from mirai.symmetric_ops import (
    TEXT_BOTH_SIDES_FACE,
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
    SymmetryRefusal,
    coordinate_split,
)
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import SymmetryIndex, completeness_report
from tests.test_symmetric_ops import (
    C,
    CTRL_Y,
    CTRL_Z,
    ORIGIN,
    assert_clean,
    assert_refused,
    everything,
    make_app,
    plus_side_edges,
    select_edges,
    selection_state,
    spanning_face_app,
    topology_state,
)

AXES = {0: (1.0, 0.0, 0.0), 1: (0.0, 1.0, 0.0), 2: (0.0, 0.0, 1.0)}
#: Every exact plane of the paired assets (probe: `subd_cube` X and Z, `head_basemesh` X).
EXACT_PLANES = [("subd_cube", 0), ("subd_cube", 2), ("head_basemesh", 0)]
PLANE_IDS = [f"{asset}-{'xyz'[axis]}" for asset, axis in EXACT_PLANES]


def make_split_app(asset: str, axis: int = 0, *, definition: bool = True):
    app = make_app(asset, definition=False)
    mesh = app.scene.mesh
    if definition:
        seam = frozenset(
            e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[axis] == 0.0 for v in mesh.edge_vertices(e))
        )
        mesh.symmetry_definition = SymmetryDefinition(ORIGIN, AXES[axis], seam)
    return app


def coord(mesh, vertex, axis: int) -> float:
    return mesh.vertex_position(vertex)[axis]


def side_of(mesh, element_vertices, axis: int) -> int:
    total = sum(coord(mesh, v, axis) for v in element_vertices)
    return (total > 0) - (total < 0)


def seam_vertices(mesh) -> set:
    return {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}


def interior_edges(mesh, axis: int, side: int = 1) -> list:
    """Paired edges on `side`, none of whose vertices is on the plane or unpaired (ascending id)."""
    index = SymmetryIndex(mesh)
    seam = seam_vertices(mesh)
    found = []
    for e in sorted(mesh.all_edge_ids()):
        vs = mesh.edge_vertices(e)
        if (
            side_of(mesh, vs, axis) == side
            and not seam & set(vs)
            and all(coord(mesh, v, axis) * side > 0 for v in vs)
            and index.edge_partner(e) not in (None, e)
        ):
            found.append(e)
    return found


def seam_edge_of(mesh) -> object:
    """A seam edge between two faces (a real mesh edge, not a boundary), lowest id."""
    return next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)


def new_ids(before, after) -> set:
    return set(after) - set(before)


# -- the success path: both sides, one Undo step -----------------------------------------------


@pytest.mark.parametrize("asset,axis", EXACT_PLANES, ids=PLANE_IDS)
def test_single_edge_splits_both_sides_in_one_undo_step(asset, axis):
    app = make_split_app(asset, axis)
    mesh = app.scene.mesh
    assert symmetry_state(mesh) is SymmetryState.VALID
    edge = interior_edges(mesh, axis)[0]
    partner = SymmetryIndex(mesh).edge_partner(edge)
    select_edges(app, {edge})
    before = everything(app)
    selection_before = selection_state(app)
    definition_before = mesh.symmetry_definition
    vertices_before, edges_before = set(mesh.all_vertex_ids()), set(mesh.all_edge_ids())
    faces_before = len(mesh.all_face_ids())

    assert app.key_press(C) is True
    assert app.status_message == "Split"
    assert len(app.history) == 1
    assert_clean(mesh)

    created = new_ids(vertices_before, mesh.all_vertex_ids())
    assert len(created) == 2
    assert not mesh.is_valid_edge(edge) and not mesh.is_valid_edge(partner)  # both were split
    assert len(mesh.all_edge_ids()) == len(edges_before) + 2  # each split: -1 edge, +2 halves
    assert len(mesh.all_face_ids()) == faces_before
    index = SymmetryIndex(mesh)
    a, b = sorted(created)
    assert index.vertex_partner(a) == b and index.vertex_partner(b) == a  # new vertices are paired
    assert {side_of(mesh, (v,), axis) for v in created} == {1, -1}
    assert mesh.symmetry_definition == definition_before  # no seam edge involved

    # Residue: Vertex mode, the new vertex of the side the live selection was on.
    assert app.selection.mode is SelectionMode.VERTEX
    (selected,) = app.selection.vertices
    assert selected in created and side_of(mesh, (selected,), axis) == 1
    assert not app.selection.edges and not app.selection.faces

    after = topology_state(app)
    after_selection = selection_state(app)
    assert app.key_press(CTRL_Z) is True
    assert everything(app) == (before[0], 0, selection_before, 0, 1)  # mesh, history, selection
    assert mesh.symmetry_definition == definition_before
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after
    assert selection_state(app) == after_selection
    assert len(app.history) == 1


def test_the_new_vertex_is_the_midpoint_of_each_edge():
    app = make_split_app("subd_cube")
    mesh = app.scene.mesh
    edge = interior_edges(mesh, 0)[0]
    partner = SymmetryIndex(mesh).edge_partner(edge)
    ends = {e: [mesh.vertex_position(v) for v in mesh.edge_vertices(e)] for e in (edge, partner)}
    before = set(mesh.all_vertex_ids())
    select_edges(app, {edge})
    assert app.key_press(C) is True
    midpoints = {mesh.vertex_position(v) for v in new_ids(before, mesh.all_vertex_ids())}
    expected = {tuple(0.5 * p + 0.5 * q for p, q in zip(*points)) for points in ends.values()}
    assert midpoints == expected


@pytest.mark.parametrize("asset,axis", EXACT_PLANES, ids=PLANE_IDS)
def test_selection_on_the_negative_side_puts_the_residue_there(asset, axis):
    app = make_split_app(asset, axis)
    mesh = app.scene.mesh
    edge = interior_edges(mesh, axis, side=-1)[0]
    select_edges(app, {edge})
    before = set(mesh.all_vertex_ids())
    assert app.key_press(C) is True
    created = new_ids(before, mesh.all_vertex_ids())
    assert len(created) == 2
    (selected,) = app.selection.vertices
    assert selected in created and side_of(mesh, (selected,), axis) == -1
    assert_clean(mesh)


# -- A2 = A: a mirror pair counts once ---------------------------------------------------------


@pytest.mark.parametrize("asset,axis", EXACT_PLANES, ids=PLANE_IDS)
def test_a_mirror_pair_selected_splits_exactly_twice_and_selects_both_new_vertices(asset, axis):
    app = make_split_app(asset, axis)
    twin = make_split_app(asset, axis)
    mesh = app.scene.mesh
    edge = interior_edges(mesh, axis)[0]
    partner = SymmetryIndex(mesh).edge_partner(edge)
    before = set(mesh.all_vertex_ids())
    edges_before = len(mesh.all_edge_ids())

    select_edges(app, {edge, partner})
    selection_before = selection_state(app)
    assert app.key_press(C) is True
    assert app.status_message == "Split"
    assert len(app.history) == 1

    created = new_ids(before, mesh.all_vertex_ids())
    assert len(created) == 2  # no double split
    assert len(mesh.all_edge_ids()) == edges_before + 2
    assert app.selection.mode is SelectionMode.VERTEX
    assert set(app.selection.vertices) == created  # both sides' results, to continue with both
    assert {side_of(mesh, (v,), axis) for v in created} == {1, -1}
    assert_clean(mesh)

    # The same result as the one-sided selection of the same intent.
    select_edges(twin, {edge})
    assert twin.key_press(C) is True
    assert topology_state(app) == topology_state(twin)

    assert app.key_press(CTRL_Z) is True
    assert selection_state(app) == selection_before
    assert app.key_press(CTRL_Y) is True
    assert set(app.selection.vertices) == created


# -- the seam (S1) -----------------------------------------------------------------------------


@pytest.mark.parametrize("asset,axis", EXACT_PLANES, ids=PLANE_IDS)
def test_a_seam_edge_is_split_once_and_the_seam_stays_continuous(asset, axis):
    app = make_split_app(asset, axis)
    mesh = app.scene.mesh
    old = seam_edge_of(mesh)
    ends = set(mesh.edge_vertices(old))
    seam_before = mesh.symmetry_definition.seam_edges
    seam_vertices_before = seam_vertices(mesh)
    vertices_before = set(mesh.all_vertex_ids())
    state_before = topology_state(app)
    select_edges(app, {old})
    selection_before = selection_state(app)

    assert app.key_press(C) is True
    assert app.status_message == "Split"
    assert len(app.history) == 1

    (new_vertex,) = new_ids(vertices_before, mesh.all_vertex_ids())  # once, not twice
    assert coord(mesh, new_vertex, axis) == 0.0  # exactly on the plane
    seam_after = mesh.symmetry_definition.seam_edges
    assert old not in seam_after and not mesh.is_valid_edge(old)
    halves = seam_after - seam_before
    assert len(seam_after) == len(seam_before) + 1 and len(halves) == 2
    assert all(mesh.is_valid_edge(e) for e in seam_after)
    # Continuity: the two halves meet in the new vertex and run to the old endpoints.
    assert {frozenset(mesh.edge_vertices(h)) for h in halves} == {frozenset({new_vertex, v}) for v in ends}
    assert seam_vertices(mesh) == seam_vertices_before | {new_vertex}
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert_clean(mesh)

    # Residue: the new vertex lies on the plane and stays selected.
    assert app.selection.mode is SelectionMode.VERTEX
    assert set(app.selection.vertices) == {new_vertex}

    assert app.key_press(CTRL_Z) is True
    assert topology_state(app) == state_before
    assert mesh.symmetry_definition.seam_edges == seam_before  # Undo restores the old seam
    assert selection_state(app) == selection_before


def test_a_seam_edge_with_a_mirror_pair_selected_alongside_is_still_split_once_each():
    """The seam edge is its own partner (counted once); the other, a mirror pair (A2)."""
    app = make_split_app("subd_cube")
    mesh = app.scene.mesh
    seam = seam_edge_of(mesh)
    edge = interior_edges(mesh, 0)[0]
    # Not a Split any more: two canonical edges are Edge Connect. Directly on the coordinator:
    before = set(mesh.all_vertex_ids())
    created = coordinate_split(mesh, {seam, edge})
    assert len(created) == 3  # seam once, edge and partner
    assert len(new_ids(before, mesh.all_vertex_ids())) == 3
    assert_clean(mesh)


# -- refusals: visible, no history entry, mesh and selection unchanged --------------------------


def edge_with_unpaired_endpoint(mesh):
    index = SymmetryIndex(mesh)
    for e in sorted(mesh.all_edge_ids()):
        if index.edge_partner(e) is None and any(index.vertex_partner(v) is None for v in mesh.edge_vertices(e)):
            return e
    raise LookupError("no edge with an unpaired endpoint")


def paired_edge_far_from_unpaired(mesh, axis: int = 0):
    """A +side interior edge none of whose faces holds an unpaired vertex."""
    index = SymmetryIndex(mesh)
    for e in interior_edges(mesh, axis):
        if all(
            index.vertex_partner(v) is not None for f in mesh.edge_faces(e) for v in mesh.face_vertices(f)
        ):
            return e
    raise LookupError("no clean +X edge")


def test_an_edge_without_a_partner_is_refused_and_a_far_one_splits_symmetrically():
    app = make_split_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    assert symmetry_state(mesh) is SymmetryState.PARTIAL

    select_edges(app, {edge_with_unpaired_endpoint(mesh)})
    assert_refused(app, TEXT_UNPAIRED)

    far = paired_edge_far_from_unpaired(mesh)
    before_report = completeness_report(mesh)
    select_edges(app, {far})
    assert app.key_press(C) is True
    assert app.status_message == "Split"
    after_report = completeness_report(mesh)
    # Partial symmetry that existed before is no violation (INV-10); the new elements are paired.
    assert after_report.unpaired_vertices == before_report.unpaired_vertices
    assert after_report.edges_without_partner == before_report.edges_without_partner
    assert after_report.faces_without_partner == before_report.faces_without_partner
    assert len(new_ids(before_report.vertices, after_report.vertices)) == 2
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == 0


@pytest.mark.parametrize(
    "definition",
    [
        SymmetryDefinition(ORIGIN, (0.6, 0.8, 0.0)),  # oblique
        SymmetryDefinition((0.3, 0.0, 0.0), AXES[0]),  # axis plane off the origin
    ],
    ids=["oblique", "off_origin"],
)
def test_a_non_exact_plane_is_refused(definition):
    app = make_split_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition
    select_edges(app, {sorted(mesh.all_edge_ids())[0]})
    assert_refused(app, TEXT_NON_EXACT_PLANE)


def test_an_edge_of_a_face_spanning_the_plane_is_refused():
    app, spanning = spanning_face_app()
    mesh = app.scene.mesh
    select_edges(app, {plus_side_edges(mesh, spanning)[0]})
    assert_refused(app, TEXT_BOTH_SIDES_FACE)


def test_a_failing_delta_check_rolls_back_mesh_seam_and_selection(monkeypatch):
    """The definition is part of the mesh state the transaction restores: a seam edge split is
    undone with the rest when the delta check refuses afterwards."""
    app = make_split_app("subd_cube")
    mesh = app.scene.mesh
    select_edges(app, {seam_edge_of(mesh)})

    def failing(before, mesh):
        raise SymmetryRefusal(TEXT_DELTA)

    monkeypatch.setattr(symmetric_ops, "_check_delta", failing)
    assert_refused(app, TEXT_DELTA)


def test_the_coordinator_refuses_an_unpaired_edge_before_it_mutates():
    app = make_split_app("subd_cube")
    mesh = app.scene.mesh
    edge = interior_edges(mesh, 0)[0]
    vertex = mesh.edge_vertices(edge)[0]
    x, y, z = mesh.vertex_position(vertex)
    mesh.set_vertex_position(vertex, (x + 0.01, y, z))  # the edge loses its partner
    state = topology_state(app)
    with pytest.raises(SymmetryRefusal) as caught:
        coordinate_split(mesh, {edge})
    assert str(caught.value) == TEXT_UNPAIRED
    assert topology_state(app) == state


def test_a_coordinator_needs_a_definition():
    app = make_split_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    with pytest.raises(ValueError):
        coordinate_split(mesh, {sorted(mesh.all_edge_ids())[0]})


# -- no definition: the unchanged operation ----------------------------------------------------


def test_without_a_definition_split_is_the_unchanged_one_sided_operation():
    app = make_split_app("subd_cube", definition=False)
    twin = make_split_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    edge = next(
        e
        for e in sorted(mesh.all_edge_ids())
        if all(coord(mesh, v, 0) > 0 for v in mesh.edge_vertices(e))
    )
    before = set(mesh.all_vertex_ids())
    select_edges(app, {edge})
    assert app.key_press(C) is True
    assert app.status_message == "Split"
    twin_new, _a, _b = twin.scene.mesh.split_edge(edge)
    assert topology_state(app) == topology_state(twin)
    (created,) = new_ids(before, mesh.all_vertex_ids())  # one-sided: exactly one vertex
    assert created == twin_new
    assert app.selection.mode is SelectionMode.VERTEX and set(app.selection.vertices) == {created}
    assert len(app.history) == 1


def test_a_refused_press_leaves_the_selection_untouched():
    app = make_split_app("man_with_shoes_basemesh")
    select_edges(app, {edge_with_unpaired_endpoint(app.scene.mesh)})
    selection_before = selection_state(app)
    assert_refused(app, TEXT_UNPAIRED)
    assert selection_state(app) == selection_before
    assert app.selection.mode is SelectionMode.EDGE
