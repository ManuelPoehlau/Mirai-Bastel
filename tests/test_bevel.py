"""Bevel / Chamfer (2026-10-29, Manu "Chamfer/Bevel (Edges, Vertices)"; `PROVISIONAL`): hold Ctrl+B.

Pinned (one segment): edge mode bevels the selected edges, face mode the faces' inner edges, vertex mode
the selected vertices. A cube stays closed and manifold: one edge -> one strip, a corner of three edges ->
three strips and a triangle cap, all edges -> 26 faces, all vertices -> the truncated cube. On a grid a
single edge becomes a hexagon (its valence-4 ends stay), a loop a band of quads, an edge to the border
ends on the border. The new edges lie at the width from the old edge. One History entry, Undo / Redo
exact, Esc / a tap / width 0 change nothing; refusals at the press; under symmetry the mirror bevels too
and stays exact."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.scene_factory import create_cube
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import set_symmetry_axis
from mirai.topology.bevel import BevelRefused, build_bevel, fan, plan_bevel
from tests.mesh_invariants import assert_mesh_invariants

WIDTH, HEIGHT = 800, 600
V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_B, B, ESC, CTRL_Z, CTRL_Y = _key("b", "ctrl"), _key("b"), _key("ESCAPE"), _key("z", "ctrl"), _key("y", "ctrl")
K1, K2, K3 = _key("1"), _key("2"), _key("3")


def _grid(n: int = 4, size: float = 4.0) -> Mesh:
    mesh = Mesh()
    step = size / n
    half = size / 2.0
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((c * step - half, r * step - half, 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def _vertex(mesh, x, y, z=None):
    (vid,) = [
        v for v in mesh.all_vertex_ids()
        if mesh.vertex_position(v)[:2] == (x, y) and (z is None or mesh.vertex_position(v)[2] == z)
    ]
    return vid


def _edge(mesh, a, b):
    (eid,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    return eid


def _closed(mesh) -> bool:
    return all(len(mesh.edge_faces(e)) == 2 for e in mesh.all_edge_ids())


def _counts(mesh) -> tuple[int, int, int]:
    return len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())


def _bevel(mesh, mode, ids, width=0.2):
    result = build_bevel(mesh, plan_bevel(mesh, mode, ids))
    for vid, position in result.positions(width).items():
        mesh.set_vertex_position(vid, position)
    assert_mesh_invariants(mesh)
    return result


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K2)
    return app


def _state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def _drag(app, dx: float, steps: int = 4) -> None:
    for _ in range(steps):
        app.pointer_motion(400.0, 300.0, dx, 0.0)


# -- topology ---------------------------------------------------------------------------------------


def test_cube_edge_corner_all_edges_and_all_vertices_stay_closed():
    cube = create_cube()
    v0 = cube.all_vertex_ids()[0]
    result = _bevel(cube, E, [cube.vertex_edges(v0)[0]])
    assert _counts(cube) == (10, 15, 7) and _closed(cube) and [len(cube.face_vertices(f)) for f in result.faces] == [4]

    cube = create_cube()
    v0 = cube.all_vertex_ids()[0]
    result = _bevel(cube, E, cube.vertex_edges(v0))
    assert _counts(cube) == (13, 21, 10) and _closed(cube)
    assert sorted(len(cube.face_vertices(f)) for f in result.faces) == [3, 4, 4, 4]

    cube = create_cube()
    _bevel(cube, E, cube.all_edge_ids())
    assert _counts(cube) == (24, 48, 26) and _closed(cube)

    cube = create_cube()
    _bevel(cube, V, cube.all_vertex_ids())
    assert _counts(cube) == (24, 36, 14) and _closed(cube)


def test_face_mode_bevels_the_faces_inner_edges():
    cube = create_cube()
    _bevel(cube, F, [cube.all_face_ids()[0]])
    assert _counts(cube) == (12, 20, 10) and _closed(cube)


def test_grid_single_edge_is_a_hexagon_with_its_ends_kept():
    mesh = _grid()
    a, b = _vertex(mesh, -1.0, 0.0), _vertex(mesh, 0.0, 0.0)
    result = _bevel(mesh, E, [_edge(mesh, a, b)], width=0.25)
    (strip,) = result.faces
    corners = {tuple(round(c, 9) for c in mesh.vertex_position(v)) for v in mesh.face_vertices(strip)}
    assert corners == {
        (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0),
        (-1.0, 0.25, 0.0), (0.0, 0.25, 0.0), (-1.0, -0.25, 0.0), (0.0, -0.25, 0.0),
    }
    assert mesh.is_valid_vertex(a) and mesh.is_valid_vertex(b)


def test_grid_loop_is_a_band_at_the_width_and_ends_on_the_border():
    mesh = _grid()
    loop = [_edge(mesh, _vertex(mesh, x, 0.0), _vertex(mesh, x + 1.0, 0.0)) for x in (-2.0, -1.0, 0.0, 1.0)]
    result = _bevel(mesh, E, loop, width=0.3)
    assert [len(mesh.face_vertices(f)) for f in result.faces] == [4, 4, 4, 4]
    ys = {round(mesh.vertex_position(v)[1], 9) for f in result.faces for v in mesh.face_vertices(f)}
    assert ys == {0.3, -0.3}
    assert not any(mesh.vertex_position(v)[1] == 0.0 for v in mesh.all_vertex_ids())


def test_vertex_bevel_cuts_the_corner_at_the_width_along_each_edge():
    mesh = _grid()
    centre = _vertex(mesh, 0.0, 0.0)
    result = _bevel(mesh, V, [centre], width=0.4)
    assert not mesh.is_valid_vertex(centre)
    (cap,) = result.faces
    assert {tuple(round(c, 9) for c in mesh.vertex_position(v)) for v in mesh.face_vertices(cap)} == {
        (0.4, 0.0, 0.0), (-0.4, 0.0, 0.0), (0.0, 0.4, 0.0), (0.0, -0.4, 0.0)
    }
    corner = Mesh.from_state(_grid().export_state())
    result = _bevel(corner, V, [_vertex(corner, -2.0, -2.0)])
    assert result.faces == [] and _counts(corner) == (26, 41, 16)  # a corner of one face: cut, no cap


def test_the_limit_stops_before_an_edge_collapses():
    mesh = _grid()
    a, b = _vertex(mesh, 0.0, 0.0), _vertex(mesh, 1.0, 0.0)
    result = build_bevel(mesh, plan_bevel(mesh, V, [a, b]))
    assert result.limit == pytest.approx(0.49)  # both ends of the shared edge move towards each other
    assert result.positions(10.0) == result.positions(result.limit)


def test_refusals_before_any_mutation():
    mesh = _grid()
    border = _edge(mesh, _vertex(mesh, -2.0, -2.0), _vertex(mesh, -1.0, -2.0))
    with pytest.raises(BevelRefused, match="border"):
        plan_bevel(mesh, E, [border])
    with pytest.raises(BevelRefused):
        plan_bevel(mesh, E, [])
    wire = Mesh.from_state(mesh.export_state())
    v = _vertex(wire, 0.0, 0.0)
    wire.add_edge(v, wire.add_vertex((5.0, 5.0, 0.0)))
    with pytest.raises(BevelRefused, match="without faces"):
        plan_bevel(wire, V, [v])


def test_an_edge_ending_at_a_two_edge_vertex_is_refused():
    """A closed pillow of two triangles: every vertex has two edges and two faces."""
    mesh = Mesh()
    a, b, m = (mesh.add_vertex(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)))
    mesh.add_face([a, b, m])
    mesh.add_face([a, m, b])
    with pytest.raises(BevelRefused, match="two edges"):
        plan_bevel(mesh, E, [_edge(mesh, a, b)])


def test_fan_orders_the_faces_around_a_vertex():
    mesh = _grid()
    inner = fan(mesh, _vertex(mesh, 0.0, 0.0))
    assert inner.closed and len(inner.faces) == len(inner.edges) == 4
    border = fan(mesh, _vertex(mesh, 0.0, -2.0))
    assert not border.closed and len(border.faces) == 2 and len(border.edges) == 3


def test_uvs_are_kept_on_the_rebuilt_faces():
    mesh = _grid(2, 2.0)
    for f in mesh.all_face_ids():
        mesh.set_face_uvs(f, tuple((p[0], p[1]) for p in map(mesh.vertex_position, mesh.face_vertices(f))))
    _bevel(mesh, V, [_vertex(mesh, 0.0, 0.0)])
    assert all(mesh.face_uvs(f) is not None for f in mesh.all_face_ids())


# -- app ----------------------------------------------------------------------------------------------


def test_ctrl_b_is_the_default_key():
    assert build_default_bindings().command_for(CTRL_B) == cmd.BEVEL
    assert build_default_bindings().command_for(B) == cmd.BORDER_SELECT


def test_hold_ctrl_b_bevels_the_selected_edge_one_undo_step(app):
    mesh = app.scene.mesh
    edge = _edge(mesh, _vertex(mesh, -1.0, 0.0), _vertex(mesh, 0.0, 0.0))
    app.selection.edges = {edge}
    before = _state(app)
    assert app.key_press(CTRL_B) is True
    assert app.status_message.startswith("Bevel: 1 edge")
    _drag(app, 10.0)
    assert app.key_release(B) is True
    assert app.status_message == "Bevel committed"
    assert _counts(mesh) == (29, 45, 17)
    assert app.selection.mode is E and len(app.selection.edges) == 6  # the strip's edges
    assert_mesh_invariants(mesh)
    assert app.key_press(CTRL_Z) is True
    assert _state(app) == before
    assert app.key_press(CTRL_Y) is True
    assert _counts(mesh) == (29, 45, 17)


def test_vertex_and_face_mode(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    app.selection.vertices = {_vertex(mesh, 0.0, 0.0)}
    app.key_press(CTRL_B)
    _drag(app, 10.0)
    app.key_release(B)
    assert app.status_message == "Bevel committed"
    assert app.selection.mode is V and len(app.selection.vertices) == 4
    app.key_press(K3)
    app.selection.faces = {next(iter(app.selection.faces), None) or mesh.all_face_ids()[0]}
    app.key_press(CTRL_B)
    _drag(app, 5.0)
    app.key_release(B)
    assert app.status_message == "Bevel committed"
    assert app.selection.mode is F
    assert_mesh_invariants(mesh)


def test_esc_tap_and_zero_width_change_nothing(app):
    mesh = app.scene.mesh
    app.selection.edges = {_edge(mesh, _vertex(mesh, -1.0, 0.0), _vertex(mesh, 0.0, 0.0))}
    before = _state(app)
    app.key_press(CTRL_B)
    _drag(app, 10.0)
    assert app.key_press(ESC) is True
    assert app.status_message == "Bevel cancelled"
    assert _state(app) == before
    app.key_press(CTRL_B)
    app.key_release(B)
    assert app.status_message == "Bevel: no change"
    app.key_press(CTRL_B)
    _drag(app, 10.0)
    _drag(app, -30.0)
    app.key_release(B)
    assert app.status_message == "Bevel: no change"
    assert _state(app) == before
    assert not app.history.can_undo()


def test_refused_at_the_press_with_a_status(app):
    mesh = app.scene.mesh
    assert app.key_press(CTRL_B) is False
    assert "select or hover" in app.status_message
    app.selection.edges = {_edge(mesh, _vertex(mesh, -2.0, -2.0), _vertex(mesh, -1.0, -2.0))}
    before = _state(app)
    assert app.key_press(CTRL_B) is False
    assert "border" in app.status_message
    assert _state(app) == before


def test_under_symmetry_the_mirror_bevels_too(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    app.selection.edges = {_edge(mesh, _vertex(mesh, 1.0, 0.0), _vertex(mesh, 1.0, 1.0))}
    app.key_press(CTRL_B)
    _drag(app, 10.0)
    app.key_release(B)
    assert app.status_message == "Bevel committed", app.status_message
    positions = {mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert all((-x, y, z) in positions for x, y, z in positions)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert_mesh_invariants(mesh)


def test_under_symmetry_a_loop_across_the_plane_bevels_with_the_seam(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    app.selection.edges = {_edge(mesh, _vertex(mesh, 0.0, 0.0), _vertex(mesh, 1.0, 0.0))}
    app.key_press(CTRL_B)
    _drag(app, 10.0)
    app.key_release(B)
    assert app.status_message == "Bevel committed", app.status_message
    positions = {mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert all((-x, y, z) in positions for x, y, z in positions)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert app.key_press(CTRL_Z) is True
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_under_symmetry_an_edge_on_the_plane_is_refused(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    app.selection.edges = {_edge(mesh, _vertex(mesh, 0.0, 0.0), _vertex(mesh, 0.0, 1.0))}
    before = _state(app)
    assert app.key_press(CTRL_B) is False
    assert "Mitte" in app.status_message
    assert _state(app) == before


def test_vertex_bevel_width_is_the_distance_along_the_edges():
    mesh = _grid()
    result = _bevel(mesh, V, [_vertex(mesh, 1.0, 1.0)], width=0.5)
    (cap,) = result.faces
    for v in mesh.face_vertices(cap):
        x, y, _ = mesh.vertex_position(v)
        assert math.isclose(math.hypot(x - 1.0, y - 1.0), 0.5)
