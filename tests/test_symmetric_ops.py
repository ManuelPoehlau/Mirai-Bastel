"""AD-SYM-03 slice 3b: symmetric Edge Connect and Vertex Connect through `C` (coordinators in
`mirai.symmetric_ops`, wired in `Application._connect_command`).

Headless, no gate: the coordinators run whenever a definition is set, in MARK as in BLOCK
(AD-013 H2 amendment, "Runtime refusals are not G-3"); the Lab path is tested in
`experiments/symmetry_lab/tests/test_app_lab_symmetric_connect.py`.

Assets as in `tests/test_symmetry_coordination.py`: plane x = 0, the x = 0 edges are the seam.
`subd_cube` / `head_basemesh` are fully paired, `man_with_shoes_basemesh` is `partial`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401 — production path src/core, src/mirai

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode
from core.mesh import SymmetryDefinition
from mirai import symmetric_ops, symmetry_declarations
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_ops import (
    TEXT_BOTH_SIDES_FACE,
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
    SymmetryRefusal,
    coordinate_edge_connect,
    coordinate_vertex_connect,
)
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_coordination import SymmetryIndex, canonical_edges, completeness_report
from mirai.topology.connect_per_face import apply_connect_edges
from mirai.topology.contextual_c import CContext
from mirai.topology.delete_dissolve import apply_removal

ORIGIN = (0.0, 0.0, 0.0)
X = (1.0, 0.0, 0.0)
C = Input("key", "c")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))

ASSETS = {
    "subd_cube": "SubD_Cube.obj",
    "head_basemesh": "head_basemesh.obj",
    "man_with_shoes_basemesh": "Man_With_Shoes_basemesh.obj",
}
PAIRED_ASSETS = ("subd_cube", "head_basemesh")
_COUNTERS = ("vertex_id_counter", "edge_id_counter", "face_id_counter")


def make_app(asset: str, *, definition: bool = True) -> Application:
    app = Application()
    app.init_scene("obj", obj_path=_EXAMPLES / "meshes" / ASSETS[asset])
    app.frame_scene()
    app.set_viewport_size(800, 600)
    app.test_asset = asset  # lets a test rebuild an identical twin
    if definition:
        mesh = app.scene.mesh
        seam = frozenset(
            e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[0] == 0.0 for v in mesh.edge_vertices(e))
        )
        mesh.symmetry_definition = SymmetryDefinition(ORIGIN, X, seam)
    return app


def topology_state(app: Application) -> dict:
    """`export_state()` without the id counters: Undo and a rollback restore the elements, the
    counters stay forward (AD-001)."""
    return {k: v for k, v in app.scene.mesh.export_state().items() if k not in _COUNTERS}


def selection_state(app: Application) -> tuple:
    s = app.selection
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces))


def everything(app: Application) -> tuple:
    return (
        topology_state(app),
        len(app.history),
        selection_state(app),
        len(app._selection_undo_stack),
        len(app._selection_redo_stack),
    )


def plus_x_quad(mesh, *, touching_seam: bool):
    """A +X quad, with or without a vertex on the seam (ascending id, deterministic)."""
    seam_vertices = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    for f in sorted(mesh.all_face_ids()):
        vs = mesh.face_vertices(f)
        if len(vs) != 4:
            continue
        if min(mesh.vertex_position(v)[0] for v in vs) < 0 or all(mesh.vertex_position(v)[0] == 0 for v in vs):
            continue
        if bool(seam_vertices & set(vs)) == touching_seam:
            return f
    raise LookupError("no suitable +X quad")


def select_edges(app: Application, edges) -> None:
    app.selection.clear()
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = set(edges)


def select_vertices(app: Application, vertices) -> None:
    app.selection.clear()
    app.selection.mode = SelectionMode.VERTEX
    app.selection.vertices = set(vertices)


def opposite_edges(mesh, face):
    edges = mesh.face_edges(face)
    return {edges[0], edges[2]}


def diagonal_vertices(mesh, face):
    vs = mesh.face_vertices(face)
    return {vs[0], vs[2]}


def edge_side(mesh, edge) -> int:
    total = sum(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(edge))
    return (total > 0) - (total < 0)


def mirror_face(mesh, face):
    partner = SymmetryIndex(mesh).face_partner(face)
    assert partner is not None and partner != face
    return partner


def assert_clean(mesh) -> None:
    report = completeness_report(mesh)
    assert not report.unpaired_vertices
    assert not report.faces_without_partner
    assert not report.edges_without_partner
    assert not report.self_mirrored_faces
    assert not report.dead_seam_ids
    assert symmetry_state(mesh) is SymmetryState.VALID


# -- declarations and layering -----------------------------------------------------------------


def test_declarations_hold_exactly_the_connect_and_removal_coordinators():
    table = symmetry_declarations.C_CONTEXT_COORDINATORS
    assert dict(table) == {
        CContext.EDGE_CONNECT: coordinate_edge_connect,
        CContext.VERTEX_CONNECT: coordinate_vertex_connect,
    }
    assert CContext.SPLIT not in table and CContext.KNIFE not in table  # slices 4 and 6
    assert dict(symmetry_declarations.REMOVAL_COORDINATORS) == {  # slice 3c
        cmd.DELETE: symmetric_ops.coordinate_delete,
        cmd.DISSOLVE: symmetric_ops.coordinate_dissolve,
        cmd.DISSOLVE_NO_CLEANUP: symmetric_ops.coordinate_dissolve_no_cleanup,
    }
    with pytest.raises(TypeError):
        table[CContext.SPLIT] = coordinate_edge_connect  # type: ignore[index]


def test_symmetric_ops_never_imports_application():
    source = Path(symmetric_ops.__file__).read_text(encoding="utf-8")
    imported = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            imported.append(("." * node.level) + (node.module or ""))
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not [name for name in imported if "application" in name]


def test_a_coordinator_needs_a_definition():
    app = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    edges = opposite_edges(mesh, sorted(mesh.all_face_ids())[0])
    with pytest.raises(ValueError):
        coordinate_edge_connect(mesh, edges)


# -- the success path: one Undo step, symmetric result ----------------------------------------


@pytest.mark.parametrize("touching_seam", [False, True], ids=["interior_quad", "seam_quad"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_edge_connect_is_one_undo_step_and_symmetric(asset, touching_seam):
    app = make_app(asset)
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=touching_seam)
    if touching_seam:
        # The seam edge and the opposite edge: the S1 case (probe F).
        seam_edges = [e for e in mesh.face_edges(face) if e in mesh.symmetry_definition.seam_edges]
        assert seam_edges, "a seam quad has a seam edge"
        edges = mesh.face_edges(face)
        k = edges.index(seam_edges[0])
        selected = {edges[k], edges[(k + 2) % 4]}
    else:
        selected = opposite_edges(mesh, face)
    select_edges(app, selected)
    before = everything(app)
    before_definition = mesh.symmetry_definition
    selection_before = selection_state(app)
    faces_before = len(mesh.all_face_ids())

    assert app.key_press(C) is True
    assert app.status_message == "Connect Edges"
    assert len(app.history) == 1
    after = topology_state(app)
    assert_clean(mesh)

    assert len(mesh.all_face_ids()) > faces_before
    created = set(app.selection.edges)
    assert created and all(mesh.is_valid_edge(e) for e in created)
    # Residue: the live selection was on the +X side only, so the created edges of +X.
    assert 1 in {edge_side(mesh, e) for e in created} and -1 not in {edge_side(mesh, e) for e in created}

    assert app.key_press(CTRL_Z) is True
    assert everything(app) == (before[0], 0, selection_before, 0, 1)
    assert mesh.symmetry_definition == before_definition
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after
    assert len(app.history) == 1


@pytest.mark.parametrize("touching_seam", [False, True], ids=["interior_quad", "seam_quad"])
@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_vertex_connect_is_one_undo_step_and_symmetric(asset, touching_seam):
    app = make_app(asset)
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=touching_seam)
    selected = diagonal_vertices(mesh, face)
    select_vertices(app, selected)
    before = everything(app)
    selection_before = selection_state(app)
    edges_before = len(mesh.all_edge_ids())

    assert app.key_press(C) is True
    assert app.status_message == "Vertex Connect"
    assert len(app.history) == 1
    assert len(mesh.all_edge_ids()) - edges_before == 2  # one diagonal on each side
    assert_clean(mesh)
    assert selection_state(app) == selection_before  # residue: the live selection is untouched

    after = topology_state(app)
    assert app.key_press(CTRL_Z) is True
    assert everything(app) == (before[0], 0, selection_before, 0, 1)
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after


def test_a_two_sided_selection_counts_once_and_gives_the_same_result():
    """A2 = A: a mirror pair is one intent, the result equals the one-sided selection's."""
    one = make_app("subd_cube")
    two = make_app("subd_cube")
    face = plus_x_quad(one.scene.mesh, touching_seam=False)
    edges = opposite_edges(one.scene.mesh, face)
    index = SymmetryIndex(two.scene.mesh)
    select_edges(one, edges)
    select_edges(two, edges | {index.edge_partner(e) for e in edges})
    assert one.key_press(C) is True and two.key_press(C) is True
    assert topology_state(one) == topology_state(two)


def test_vertex_connect_with_nothing_connectable_makes_no_history_entry():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    a, b = mesh.face_vertices(face)[:2]  # adjacent: skipped by the pairing rule
    select_vertices(app, {a, b})
    before = everything(app)
    assert app.key_press(C) is False
    assert app.status_message == "Vertex Connect: nothing connectable"
    assert everything(app) == before


# -- residue: the created edges on the side(s) of the live selection ----------------------------


def connect_and_created(app: Application) -> set:
    """Presses C; returns the connecting edges the op created (`EdgeConnectResult.created`, read
    from an identical twin: ids are deterministic) — the split halves are no residue."""
    mesh = app.scene.mesh
    twin = make_app(app.test_asset, definition=app.scene.mesh.symmetry_definition is not None)
    twin_selection = set(app.selection.edges)
    index = SymmetryIndex(twin.scene.mesh)
    canonical = (
        canonical_edges(index, twin_selection) if twin.scene.mesh.symmetry_definition else twin_selection
    )
    twin_mesh = twin.scene.mesh
    if twin_mesh.symmetry_definition is not None:
        created = coordinate_edge_connect(twin_mesh, canonical).created
    else:
        created = apply_connect_edges(twin_mesh, set(canonical)).created
    assert app.key_press(C) is True
    assert topology_state(app) == topology_state(twin)
    return set(created)


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("worked_on", [1, -1], ids=["plus_x", "minus_x"])
def test_residue_is_the_created_edges_of_the_side_the_artist_worked_on(asset, worked_on):
    app = make_app(asset)
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    if worked_on < 0:
        face = mirror_face(mesh, face)
    select_edges(app, opposite_edges(mesh, face))
    new_edges = connect_and_created(app)
    selected = set(app.selection.edges)
    on_side = {e for e in new_edges if edge_side(mesh, e) == worked_on}
    mirrored = {e for e in new_edges if edge_side(mesh, e) == -worked_on}
    assert on_side and mirrored  # both sides were cut
    # The edge into the midpoint ring: only the worked-on side's created edges are selected.
    assert selected and selected <= new_edges
    assert {edge_side(mesh, e) for e in selected} == {worked_on}
    assert app.selection.mode is SelectionMode.EDGE
    assert not selected & mirrored


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_residue_of_a_deliberate_two_sided_selection_is_the_created_edges_of_both_sides(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    edges = opposite_edges(mesh, face)
    index = SymmetryIndex(mesh)
    select_edges(app, edges | {index.edge_partner(e) for e in edges})
    new_edges = connect_and_created(app)
    selected = set(app.selection.edges)
    assert {edge_side(mesh, e) for e in selected} == {1, -1}
    assert selected == new_edges
    assert_clean(mesh)


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_residue_with_a_seam_edge_in_the_selection_follows_the_non_seam_edges_side(asset):
    """The seam edge has no side; the opposite edge decides (probe F case). Created edges that are
    their own mirror stay selected."""
    app = make_app(asset)
    mesh = app.scene.mesh
    for worked_on in (1, -1):
        app = make_app(asset)
        mesh = app.scene.mesh
        face = plus_x_quad(mesh, touching_seam=True)
        if worked_on < 0:
            face = mirror_face(mesh, face)
        edges = mesh.face_edges(face)
        k = next(i for i, e in enumerate(edges) if e in mesh.symmetry_definition.seam_edges)
        select_edges(app, {edges[k], edges[(k + 2) % 4]})
        new_edges = connect_and_created(app)
        selected = set(app.selection.edges)
        assert selected and selected <= new_edges
        assert {edge_side(mesh, e) for e in selected} <= {worked_on, 0}
        assert worked_on in {edge_side(mesh, e) for e in selected}
        assert not {e for e in new_edges if edge_side(mesh, e) == -worked_on} & selected


def test_residue_sides_helper_rules():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    seam = sorted(mesh.symmetry_definition.seam_edges)
    face = plus_x_quad(mesh, touching_seam=False)
    plus = opposite_edges(mesh, face)
    minus = {SymmetryIndex(mesh).edge_partner(e) for e in plus}
    sides = lambda live: symmetric_ops.residue_sides(mesh, live, mesh.edge_vertices)  # noqa: E731
    assert sides(plus) == {1}
    assert sides(minus) == {-1}
    assert sides(plus | minus) == {1, -1}
    assert sides(seam) == {1}  # only the plane: the normal's side
    assert sides(set(seam) | minus) == {-1}  # the plane has no say
    assert sides([]) == {1}
    kept = symmetric_ops.on_residue_sides(mesh, set(seam) | plus | minus, frozenset({-1}), mesh.edge_vertices)
    assert kept == set(seam) | minus  # an edge on the plane is its own mirror: it stays


def test_residue_undo_restores_the_previous_selection_and_redo_the_residue():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    select_edges(app, opposite_edges(mesh, face))
    selection_before = selection_state(app)
    connect_and_created(app)
    residue = selection_state(app)
    assert residue != selection_before
    assert len(app._selection_undo_stack) == 1  # one mirror entry per push, `before` pre-transaction
    assert app.key_press(CTRL_Z) is True
    assert selection_state(app) == selection_before
    assert app.key_press(CTRL_Y) is True
    assert selection_state(app) == residue


def test_a_refused_press_leaves_the_selection_untouched():
    app, face = displaced_cube()
    mesh = app.scene.mesh
    select_edges(app, opposite_edges(mesh, face))
    selection_before = selection_state(app)
    assert_refused(app, TEXT_UNPAIRED)
    assert selection_state(app) == selection_before


def test_without_a_definition_the_residue_is_all_created_edges():
    app = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    face = plus_x_quad_no_seam(app)
    select_edges(app, opposite_edges(mesh, face))
    created = connect_and_created(app)
    assert created and set(app.selection.edges) == created  # unchanged behaviour, nothing filtered


# -- the seam (S1) ---------------------------------------------------------------------------


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_a_split_seam_edge_is_replaced_by_its_halves_and_undo_restores_the_seam(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=True)
    seam_before = mesh.symmetry_definition.seam_edges
    edges = mesh.face_edges(face)
    k = next(i for i, e in enumerate(edges) if e in seam_before)
    old = edges[k]
    ends = set(mesh.edge_vertices(old))
    select_edges(app, {old, edges[(k + 2) % 4]})
    state_before = topology_state(app)

    assert app.key_press(C) is True
    seam_after = mesh.symmetry_definition.seam_edges
    assert old not in seam_after and not mesh.is_valid_edge(old)
    assert len(seam_after) == len(seam_before) + 1
    assert all(mesh.is_valid_edge(e) for e in seam_after)
    halves = seam_after - seam_before
    assert len(halves) == 2
    midpoint = (set(mesh.edge_vertices(next(iter(halves)))) & set(mesh.edge_vertices(sorted(halves)[1]))).pop()
    assert {frozenset(mesh.edge_vertices(h)) - {midpoint} for h in halves} == {frozenset({v}) for v in ends}
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert_clean(mesh)

    assert app.key_press(CTRL_Z) is True
    assert topology_state(app) == state_before
    assert mesh.symmetry_definition.seam_edges == seam_before


# -- refusals: visible, no history entry, mesh and selection unchanged --------------------------


def assert_refused(app: Application, text: str) -> None:
    before = everything(app)
    definition = app.scene.mesh.symmetry_definition
    serial = app.status_serial
    assert app.key_press(C) is False
    assert app.status_message == text
    assert app.status_serial == serial + 1
    assert everything(app) == before
    assert app.scene.mesh.symmetry_definition == definition


def displaced_cube(delta: float = 0.01) -> tuple[Application, object]:
    """subd_cube with one +X vertex moved: it and its edges lose their partner."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=False)
    vertex = mesh.face_vertices(face)[0]
    x, y, z = mesh.vertex_position(vertex)
    mesh.set_vertex_position(vertex, (x + delta, y, z))
    return app, face


def test_refused_unpaired_selected_edge_changes_nothing_for_edge_connect():
    app, face = displaced_cube()
    select_edges(app, opposite_edges(app.scene.mesh, face))
    assert_refused(app, TEXT_UNPAIRED)


def test_refused_unpaired_selected_vertex_changes_nothing_for_vertex_connect():
    app, face = displaced_cube()
    select_vertices(app, diagonal_vertices(app.scene.mesh, face))
    assert_refused(app, TEXT_UNPAIRED)


def spanning_face_app() -> tuple[Application, object]:
    """subd_cube whose seam edge between two +/-X quads is dissolved programmatically: the merged
    face spans the plane (the both-sides case of AD-SYM-03 item 9)."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    seam_edge = next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)
    apply_removal(mesh, SelectionMode.EDGE, {seam_edge}, dissolve=True, cleanup=True)
    index = SymmetryIndex(mesh)
    spanning = next(f for f in mesh.all_face_ids() if index.face_partner(f) == f)
    return app, spanning


def plus_side_edges(mesh, face):
    index = SymmetryIndex(mesh)
    edges = [
        e
        for e in mesh.face_edges(face)
        if sum(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(e)) > 0 and index.edge_partner(e) is not None
    ]
    assert len(edges) >= 2
    return edges


def test_refused_both_sides_face_changes_nothing_for_edge_connect():
    app, spanning = spanning_face_app()
    mesh = app.scene.mesh
    select_edges(app, set(plus_side_edges(mesh, spanning)[:2]))
    assert_refused(app, TEXT_BOTH_SIDES_FACE)


def test_refused_both_sides_face_changes_nothing_for_vertex_connect():
    app, spanning = spanning_face_app()
    mesh = app.scene.mesh
    vertices = [v for v in mesh.face_vertices(spanning) if mesh.vertex_position(v)[0] > 0]
    assert len(vertices) >= 2
    select_vertices(app, set(vertices[:2]))
    assert_refused(app, TEXT_BOTH_SIDES_FACE)


@pytest.mark.parametrize(
    "definition",
    [
        SymmetryDefinition(ORIGIN, (0.6, 0.8, 0.0)),  # oblique
        SymmetryDefinition((0.3, 0.0, 0.0), X),  # axis plane off the origin
    ],
    ids=["oblique", "off_origin"],
)
@pytest.mark.parametrize("mode", ["edge", "vertex"])
def test_refused_non_exact_plane_changes_nothing(mode, definition):
    app = make_app("subd_cube", definition=False)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition
    face = sorted(mesh.all_face_ids())[0]
    if mode == "edge":
        select_edges(app, opposite_edges(mesh, face))
    else:
        select_vertices(app, diagonal_vertices(mesh, face))
    assert_refused(app, TEXT_NON_EXACT_PLANE)


def unpaired_corner_cases(mesh):
    """Quads with exactly one unpaired vertex `u`, with the two edges of the opposite corner `b`
    (both edges paired: no 'unpaired selection' refusal) — their connect cuts off the corner and
    leaves a pentagon holding `u`, a created face without a partner."""
    index = SymmetryIndex(mesh)
    for f in sorted(mesh.all_face_ids()):
        vs = mesh.face_vertices(f)
        if len(vs) != 4:
            continue
        bad = [i for i, v in enumerate(vs) if index.vertex_partner(v) is None]
        if len(bad) != 1:
            continue
        b = vs[(bad[0] + 2) % 4]
        edges = [e for e in mesh.face_edges(f) if b in mesh.edge_vertices(e)]
        if len(edges) == 2 and all(index.edge_partner(e) is not None for e in edges):
            yield f, edges


def far_from_unpaired(mesh):
    """A +X quad none of whose vertices is unpaired or on the seam."""
    index = SymmetryIndex(mesh)
    seam_vertices = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    for f in sorted(mesh.all_face_ids()):
        vs = mesh.face_vertices(f)
        if len(vs) == 4 and all(
            index.vertex_partner(v) is not None and v not in seam_vertices and mesh.vertex_position(v)[0] > 0 for v in vs
        ):
            return f
    raise LookupError("no clean +X quad")


def test_d_strict_refuses_next_to_an_unpaired_vertex_and_works_far_from_it():
    """A3 = S: the same operation on a partial mesh — refused where it would create a face
    without a partner, symmetric where it does not."""
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    face, edges = next(unpaired_corner_cases(mesh))
    select_edges(app, set(edges))
    assert_refused(app, TEXT_DELTA)

    # An element that was incomplete before stays incomplete: not a violation (INV-10).
    far = far_from_unpaired(mesh)
    before_report = completeness_report(mesh)
    select_edges(app, opposite_edges(mesh, far))
    assert app.key_press(C) is True
    assert len(app.history) == 1
    after_report = completeness_report(mesh)
    assert after_report.unpaired_vertices == before_report.unpaired_vertices
    assert after_report.faces_without_partner == before_report.faces_without_partner
    assert after_report.edges_without_partner == before_report.edges_without_partner
    assert not after_report.dead_seam_ids and not after_report.self_mirrored_faces
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == 0


def test_delta_refusal_carries_the_violations_and_rolls_back_the_mutation():
    app = make_app("man_with_shoes_basemesh")
    mesh = app.scene.mesh
    _face, edges = next(unpaired_corner_cases(mesh))
    state = topology_state(app)
    with pytest.raises(SymmetryRefusal) as caught:
        coordinate_edge_connect(mesh, set(edges))  # a bare mutation: the caller owns the rollback
    assert str(caught.value) == TEXT_DELTA
    assert any("without a partner" in v for v in caught.value.violations)
    assert topology_state(app) != state  # the coordinator itself restores nothing


def test_the_delta_refusal_restores_the_seam_definition_too():
    """The definition is part of the mesh state the transaction restores."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    face = plus_x_quad(mesh, touching_seam=True)
    edges = mesh.face_edges(face)
    k = next(i for i, e in enumerate(edges) if e in mesh.symmetry_definition.seam_edges)
    select_edges(app, {edges[k], edges[(k + 2) % 4]})
    original = symmetric_ops._check_delta

    def failing(before, mesh):  # force the violation after the seam was rewritten
        raise SymmetryRefusal(TEXT_DELTA)

    symmetric_ops._check_delta = failing
    try:
        assert_refused(app, TEXT_DELTA)
    finally:
        symmetric_ops._check_delta = original


# -- no definition: the unchanged operation ----------------------------------------------------


def test_without_a_definition_edge_connect_is_the_unchanged_operation():
    app = make_app("subd_cube", definition=False)
    twin = make_app("subd_cube", definition=False)
    face = plus_x_quad_no_seam(app)
    edges = opposite_edges(app.scene.mesh, face)
    select_edges(app, edges)
    assert app.key_press(C) is True
    apply_connect_edges(twin.scene.mesh, set(edges))
    assert topology_state(app) == topology_state(twin)
    assert len(app.history) == 1


def plus_x_quad_no_seam(app: Application):
    mesh = app.scene.mesh
    for f in sorted(mesh.all_face_ids()):
        vs = mesh.face_vertices(f)
        if len(vs) == 4 and min(mesh.vertex_position(v)[0] for v in vs) > 0:
            return f
    raise LookupError("no +X quad")
