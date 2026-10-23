"""Application: Collapse V/E/F on Shift+C (WP Toolbox Gaps B1, `docs/WP_TOOLBOX_GAPS_PLAN.md`).

Headless. Path: Shift+C → `Application.key_press` → `dispatch_command(COLLAPSE)` →
`_collapse_command()` → `mirai.topology.collapse.apply_collapse` (or, with a symmetry definition,
`symmetric_ops.coordinate_collapse`) → `core.operations.collapse_elements`. One history entry per
success, mesh, history and selection untouched on refusal or no-op; residue = the result vertices
in Vertex mode (P-4, `PROVISIONAL`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai import symmetry_declarations
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_ops import coordinate_collapse
from mirai.symmetry_coordination import SymmetryIndex
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_delete_dissolve import _app, _edge, _grid_face, _grid_vertex, _select, _topology
from tests.test_symmetric_ops import PAIRED_ASSETS, assert_clean, everything, make_app, plus_x_quad

SHIFT_C = Input("key", "c", frozenset({"shift"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


def _assert_untouched(app, status_part: str) -> None:
    before = everything(app)
    assert app.key_press(SHIFT_C) is False
    assert status_part in app.status_message
    assert everything(app) == before


def _collapse(app) -> None:
    history = len(app.history)
    assert app.key_press(SHIFT_C) is True
    assert len(app.history) == history + 1
    assert app.history._undo_stack[-1].description == "Collapse"
    assert_mesh_invariants(app.scene.mesh)
    app.update_viewport(0.0)  # the render path copes with the removed ids


def test_shift_c_is_collapse_and_c_stays_connect():
    app = _app()
    assert app.bindings.command_for(SHIFT_C) == cmd.COLLAPSE
    assert app.bindings.command_for(Input("key", "c")) == cmd.CONNECT


def test_edge_collapse_is_one_undo_step_and_selects_the_point():
    app = _app(2)
    mesh = app.scene.mesh
    a, b = _grid_vertex(app, 1, 0), _grid_vertex(app, 1, 1)
    _select(app, E, {_edge(mesh, a, b)})
    before = _topology(mesh)
    selection_before = app._selection_snapshot()
    _collapse(app)

    (point,) = app.selection.vertices
    assert app.selection.mode is V and not app.selection.edges
    assert mesh.vertex_position(point) == (0.5, 1.0, 0.0)
    assert len(mesh.all_vertex_ids()) == 8
    after = _topology(mesh)

    app.key_press(CTRL_Z)
    assert _topology(mesh) == before
    assert app._selection_snapshot() == selection_before
    app.key_press(CTRL_Y)
    assert _topology(mesh) == after
    assert app.selection.mode is V and app.selection.vertices == {point}


def test_edge_chain_and_two_separate_edges():
    app = _app(3)
    mesh = app.scene.mesh
    row = [_grid_vertex(app, 1, c) for c in range(4)]
    far = _edge(mesh, _grid_vertex(app, 3, 0), _grid_vertex(app, 3, 1))
    _select(app, E, {_edge(mesh, row[i], row[i + 1]) for i in range(3)} | {far})
    _collapse(app)
    positions = sorted(mesh.vertex_position(v) for v in app.selection.vertices)
    assert positions == [(0.5, 3.0, 0.0), (1.5, 1.0, 0.0)]
    assert app.status_message == "Collapse: 2 point(s)"


def test_face_group_collapses_to_its_centroid():
    app = _app(4)
    mesh = app.scene.mesh
    faces = {_grid_face(app, r, c) for r in (1, 2) for c in (1, 2)}
    _select(app, F, faces)
    _collapse(app)
    (point,) = app.selection.vertices
    assert mesh.vertex_position(point) == (2.0, 2.0, 0.0)
    assert not any(mesh.is_valid_face(f) for f in faces)


def test_vertex_mode_merges_over_edges_between_selected_vertices():
    app = _app(2)
    mesh = app.scene.mesh
    _select(app, V, {_grid_vertex(app, 0, 0), _grid_vertex(app, 0, 1), _grid_vertex(app, 2, 2)})
    _collapse(app)
    assert sorted(mesh.vertex_position(v) for v in app.selection.vertices) == [(0.5, 0.0, 0.0), (2.0, 2.0, 0.0)]


def test_vertices_without_a_joining_edge_change_nothing():
    app = _app(2)
    _select(app, V, {_grid_vertex(app, 0, 0), _grid_vertex(app, 1, 1)})
    _assert_untouched(app, "nothing to do")


def test_empty_selection_changes_nothing():
    app = _app(2)
    _select(app, E, set())
    _assert_untouched(app, "nothing selected")


def test_a_pinching_collapse_is_refused_with_its_reason():
    app = _app(3)
    mesh = app.scene.mesh
    path = [(1, 1), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (2, 2)]
    vs = [_grid_vertex(app, r, c) for r, c in path]
    _select(app, E, {_edge(mesh, vs[i], vs[i + 1]) for i in range(len(vs) - 1)})
    _assert_untouched(app, "eingeschnürt")


def test_refused_in_object_mode():
    app = _app(2)
    app.key_press(Input("key", "4"))
    _assert_untouched(app, "Shift+C")


def test_ignored_while_w_is_held():
    app = _app(2)
    mesh = app.scene.mesh
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 0), _grid_vertex(app, 1, 1))})
    app.key_press(Input("key", "w"))
    before = everything(app)
    assert app.key_press(SHIFT_C) is False
    assert everything(app) == before
    app.key_release(Input("key", "w"))
    assert app.key_press(SHIFT_C) is True


# -- symmetry ------------------------------------------------------------------------------------


def test_collapse_is_declared():
    assert dict(symmetry_declarations.COLLAPSE_COORDINATORS) == {cmd.COLLAPSE: coordinate_collapse}
    assert symmetry_declarations.declared_collapse_commands() == {cmd.COLLAPSE}


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_symmetric_edge_collapse_mirrors_exactly_and_undoes_in_one_step(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    quad = plus_x_quad(mesh, touching_seam=False)
    edge = mesh.face_edges(quad)[0]
    partner_edge = SymmetryIndex(mesh).edge_partner(edge)
    _select(app, E, {edge})
    before = _topology(mesh)
    vertices = len(mesh.all_vertex_ids())
    _collapse(app)

    assert not mesh.is_valid_edge(edge) and not mesh.is_valid_edge(partner_edge)
    assert len(mesh.all_vertex_ids()) == vertices - 2
    assert_clean(mesh)
    (point,) = app.selection.vertices  # the residue stays on the side the selection was on
    assert mesh.vertex_position(point)[0] > 0
    app.key_press(CTRL_Z)
    assert _topology(mesh) == before


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_symmetric_face_collapse_at_the_seam_lands_on_the_plane(asset):
    """A quad with a seam edge and its mirror image share that edge: one group, one point on the
    plane, still a clean symmetric mesh."""
    app = make_app(asset)
    mesh = app.scene.mesh
    seam = mesh.symmetry_definition.seam_edges
    quad = next(
        f for f in sorted(mesh.all_face_ids())
        if len(mesh.face_vertices(f)) == 4
        and set(mesh.face_edges(f)) & seam
        and max(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0
    )
    _select(app, F, {quad})
    _collapse(app)
    assert_clean(mesh)
    (point,) = app.selection.vertices
    assert mesh.vertex_position(point)[0] == 0.0


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("kind", ["seam", "crossing"])
def test_symmetric_seam_and_crossing_edge(asset, kind):
    """A seam edge collapses on the plane, the seam keeps running through the point; an edge with
    one end on the seam merges with its mirror image into one point on the plane."""
    app = make_app(asset)
    mesh = app.scene.mesh
    seam = mesh.symmetry_definition.seam_edges
    on_seam = {v for e in seam for v in mesh.edge_vertices(e)}
    if kind == "seam":
        edge = sorted(seam)[0]
    else:
        edge = next(
            e for e in sorted(mesh.all_edge_ids())
            if len(set(mesh.edge_vertices(e)) & on_seam) == 1
            and max(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(e)) > 0
        )
    _select(app, E, {edge})
    before = _topology(mesh)
    _collapse(app)
    assert_clean(mesh)
    (point,) = app.selection.vertices
    assert mesh.vertex_position(point)[0] == 0.0
    assert point in {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    app.key_press(CTRL_Z)
    assert _topology(mesh) == before


def test_symmetric_collapse_of_an_unpaired_element_is_refused():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    quad = plus_x_quad(mesh, touching_seam=False)
    v = mesh.face_vertices(quad)[0]
    x, y, z = mesh.vertex_position(v)
    mesh.set_vertex_position(v, (x + 0.01, y, z))
    app.viewport.on_topology_changed()
    _select(app, E, {e for e in mesh.vertex_edges(v)})
    _assert_untouched(app, "Spiegelpartner")
