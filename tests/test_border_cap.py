"""Border Select (B) and Cap (Shift+B) (Manu 2026-10-25, `mirai.topology.border`).

Module level on hand-built meshes (grid with a hole, open grid, bow-tie), then the App path:
`key_press` → `dispatch_command` → `_border_select` / `_cap_command` (with a symmetry definition
`symmetric_ops.coordinate_cap`). Cap is one history entry, mesh and history untouched on refusal.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from core.mesh import Mesh
from mirai import symmetry_declarations
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.symmetric_ops import coordinate_cap
from mirai.topology.border import CapRefused, apply_cap, border_edges, border_loops, border_select
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_delete_dissolve import _app, _edge, _grid_face, _grid_vertex, _select, _topology
from tests.test_symmetric_ops import PAIRED_ASSETS, assert_clean, everything, make_app

B = Input("key", "b")
F_KEY = Input("key", "b", frozenset({"shift"}))
DELETE = Input("key", "delete")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


def _grid(n: int) -> tuple[Mesh, dict]:
    mesh = Mesh()
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p


def _holed_grid() -> tuple[Mesh, dict]:
    """3x3 grid without its middle face: an outer border (12 edges) and a hole (4 edges)."""
    mesh, p = _grid(3)
    middle = next(f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == {p[(1, 1)], p[(1, 2)], p[(2, 2)], p[(2, 1)]})
    mesh.delete_faces([middle])
    return mesh, p


def _normal(mesh, face):
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


# -- module ---------------------------------------------------------------------------------------


def test_border_loops_of_a_holed_grid():
    mesh, _ = _holed_grid()
    loops = border_loops(mesh, border_edges(mesh))
    assert sorted(len(loop.edges) for loop in loops) == [4, 12]
    assert all(loop.closed for loop in loops)


def test_border_select_grows_one_edge_to_its_hole_and_face_mode_gives_the_outline():
    mesh, p = _holed_grid()
    seed = _edge(mesh, p[(1, 1)], p[(1, 2)])
    mode, edges = border_select(mesh, E, {seed})
    assert mode is E and len(edges) == 4
    mode, vertices = border_select(mesh, V, {p[(2, 2)]})
    assert mode is V and vertices == {p[(1, 1)], p[(1, 2)], p[(2, 2)], p[(2, 1)]}
    mode, everything_ = border_select(mesh, E, set())
    assert len(everything_) == 16
    corner = next(f for f in mesh.all_face_ids() if p[(0, 0)] in mesh.face_vertices(f))
    mode, outline = border_select(mesh, F, {corner})
    assert mode is E and outline == set(mesh.face_edges(corner))
    assert border_select(mesh, E, {_edge(mesh, p[(0, 1)], p[(1, 1)])})[1] == set()  # inner edge


def test_cap_closes_the_hole_with_the_neighbours_winding():
    mesh, p = _holed_grid()
    (face,) = apply_cap(mesh, E, {_edge(mesh, p[(1, 1)], p[(1, 2)])})
    assert set(mesh.face_vertices(face)) == {p[(1, 1)], p[(1, 2)], p[(2, 2)], p[(2, 1)]}
    assert _normal(mesh, face)[2] > 0  # the grid faces point +Z
    assert all(len(mesh.edge_faces(e)) == 2 for e in mesh.face_edges(face))
    assert_mesh_invariants(mesh)


def test_cap_of_the_outer_border_is_an_ngon_and_flips_against_the_grid():
    mesh, p = _grid(2)
    (face,) = apply_cap(mesh, V, {p[(0, 0)]})
    assert len(mesh.face_vertices(face)) == 8
    assert _normal(mesh, face)[2] < 0
    assert not border_edges(mesh)
    assert_mesh_invariants(mesh)


def test_cap_refusals_leave_the_mesh_untouched():
    mesh, _ = _grid(1)
    before = mesh.export_state()
    with pytest.raises(CapRefused, match="same points"):
        apply_cap(mesh, F, set(mesh.all_face_ids()))
    mesh, p = _holed_grid()
    with pytest.raises(CapRefused, match="no open border"):
        apply_cap(mesh, E, {_edge(mesh, p[(0, 1)], p[(1, 1)])})
    # Bow-tie: two triangles sharing one vertex - their borders meet there and are not closed loops.
    mesh = Mesh()
    a, b, c, d, e = (mesh.add_vertex(q) for q in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)))
    mesh.add_face([a, b, c])
    mesh.add_face([a, d, e])
    before = mesh.export_state()
    with pytest.raises(CapRefused, match="not closed"):
        apply_cap(mesh, E, {_edge(mesh, b, c)})
    assert mesh.export_state() == before


# -- App ------------------------------------------------------------------------------------------


def _holed_app():
    app = _app(3)
    mesh = app.scene.mesh
    _select(app, F, {_grid_face(app, 1, 1)})
    assert app.key_press(DELETE) is True
    return app, mesh


def test_default_bindings():
    app = _app()
    assert app.bindings.command_for(B) == cmd.BORDER_SELECT
    assert app.bindings.command_for(F_KEY) == cmd.CAP


def test_b_selects_the_hole_from_one_edge_without_a_history_step():
    app, mesh = _holed_app()
    a, b = _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2)
    _select(app, E, {_edge(mesh, a, b)})
    history = len(app.history)
    assert app.key_press(B) is True
    assert len(app.selection.edges) == 4
    assert len(app.history) == history


def test_b_with_nothing_selected_takes_the_hovered_border_else_all_borders():
    app, mesh = _holed_app()
    _select(app, E, set())
    app.selection.hovered = _edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))
    assert app.key_press(B) is True
    assert len(app.selection.edges) == 4
    _select(app, E, set())
    app.selection.hovered = None
    assert app.key_press(B) is True
    assert len(app.selection.edges) == 16


def test_b_in_face_mode_selects_the_outline_in_edge_mode():
    app = _app(3)
    _select(app, F, {_grid_face(app, 0, 0), _grid_face(app, 0, 1)})
    assert app.key_press(B) is True
    assert app.selection.mode is E and len(app.selection.edges) == 6


def test_f_caps_in_one_undo_step_and_selects_the_new_face():
    app, mesh = _holed_app()
    before = _topology(mesh)
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))})
    history = len(app.history)
    assert app.key_press(F_KEY) is True
    assert len(app.history) == history + 1
    assert app.history._undo_stack[-1].description == "Cap"
    (face,) = app.selection.faces
    assert app.selection.mode is F and len(mesh.face_vertices(face)) == 4
    assert_mesh_invariants(mesh)
    app.update_viewport(0.0)
    after = _topology(mesh)
    app.key_press(CTRL_Z)
    assert _topology(mesh) == before
    app.key_press(CTRL_Y)
    assert _topology(mesh) == after


def test_f_on_a_closed_surface_is_refused_untouched():
    app = _app()
    _select(app, F, {next(iter(app.scene.mesh.all_face_ids()))})
    before = everything(app)
    assert app.key_press(F_KEY) is False
    assert "no open border" in app.status_message
    assert everything(app) == before


# -- symmetry -------------------------------------------------------------------------------------


def test_cap_is_declared():
    assert dict(symmetry_declarations.CAP_COORDINATORS) == {cmd.CAP: coordinate_cap}


def _seam_face_pair(mesh):
    """Two quads that share a seam edge (one each side)."""
    for e in sorted(mesh.symmetry_definition.seam_edges):
        faces = mesh.edge_faces(e)
        if len(faces) == 2 and all(len(mesh.face_vertices(f)) == 4 for f in faces):
            return set(faces)
    raise LookupError("no quad pair across the seam")


def _off_seam_quad(mesh):
    seam_vertices = {v for e in mesh.symmetry_definition.seam_edges for v in mesh.edge_vertices(e)}
    for f in sorted(mesh.all_face_ids()):
        vs = mesh.face_vertices(f)
        if len(vs) == 4 and min(mesh.vertex_position(v)[0] for v in vs) > 0 and not seam_vertices & set(vs):
            return f
    raise LookupError("no +X quad off the seam")


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_symmetric_cap_closes_the_mirror_hole_too(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    _select(app, F, {_off_seam_quad(mesh)})
    assert app.key_press(DELETE) is True  # coordinated: both holes
    assert len(border_loops(mesh, border_edges(mesh))) == 2
    hole_edge = next(iter(e for e in border_edges(mesh) if mesh.vertex_position(mesh.edge_vertices(e)[0])[0] > 0))
    _select(app, E, {hole_edge})
    assert app.key_press(F_KEY) is True, app.status_message
    assert not border_edges(mesh)
    assert len(app.selection.faces) == 1  # residue on the side the artist worked on
    assert_clean(mesh)
    assert_mesh_invariants(mesh)


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
def test_symmetric_cap_of_a_hole_across_the_plane_gives_two_mirror_faces_on_the_seam(asset):
    app = make_app(asset)
    mesh = app.scene.mesh
    seam_before = len(mesh.symmetry_definition.seam_edges)
    _select(app, F, _seam_face_pair(mesh))
    assert app.key_press(DELETE) is True, app.status_message
    (loop,) = border_loops(mesh, border_edges(mesh))
    assert len(loop.edges) == 6
    _select(app, E, {loop.edges[0]})
    assert app.key_press(F_KEY) is True, app.status_message
    assert not border_edges(mesh)
    assert len(mesh.symmetry_definition.seam_edges) == seam_before
    assert_clean(mesh)
    assert_mesh_invariants(mesh)
    app.key_press(CTRL_Z)
    assert len(border_loops(mesh, border_edges(mesh))) == 1
