"""Vertex Slide (2026-10-29, Manu "Slide (Vertices)"; `PROVISIONAL`): hold G in vertex mode.

Pinned: each selected (else the hovered) vertex slides along the edge whose screen direction best
matches the drag, from 0 (start) to 1 (on the neighbour); one History entry, Esc / a tap leave the
mesh exactly as it was, dragging back restores the start; under symmetry the partner follows exactly
and a seam vertex only slides along the seam; fully masked vertices stay. G in edge mode stays Loop
Slide."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import set_symmetry_axis
from mirai.topology.vertex_slide import (
    VertexSlideRefused,
    best_neighbour,
    plan_vertex_slide,
    vertex_slide_positions,
)
from tests.mesh_invariants import assert_mesh_invariants

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


G, ESC, CTRL_Z, CTRL_M = _key("g"), _key("ESCAPE"), _key("z", "ctrl"), _key("m", "ctrl")
K1, K2 = _key("1"), _key("2")


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


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K1)
    return app


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def _towards(app, start, target) -> tuple[float, float]:
    """Screen vector (px) from world point `start` to world point `target`."""
    camera = app._edit_camera
    a = camera.project_to_screen(start, WIDTH, HEIGHT)
    b = camera.project_to_screen(target, WIDTH, HEIGHT)
    return (b[0] - a[0], b[1] - a[1])


def _drag(app, vector, fraction: float, steps: int = 5) -> None:
    x, y = 400.0, 300.0
    dx, dy = vector[0] * fraction / steps, vector[1] * fraction / steps
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)


def test_g_in_vertex_mode_slides_towards_the_dragged_edge_one_undo_step(app):
    mesh = app.scene.mesh
    vid = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {vid}
    before = _state(app)
    assert app.key_press(G) is True
    assert "Vertex Slide" in app.status_message
    _drag(app, _towards(app, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), 0.5)
    x, y, z = mesh.vertex_position(vid)
    assert x == pytest.approx(0.5) and y == pytest.approx(0.0) and z == pytest.approx(0.0)
    assert app.key_release(G) is True
    assert app.status_message == "Vertex Slide committed"
    assert_mesh_invariants(mesh)
    assert app.key_press(CTRL_Z) is True
    assert _state(app) == before


def test_the_drag_direction_picks_the_edge_and_the_amount_is_clamped(app):
    mesh = app.scene.mesh
    vid = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {vid}
    app.key_press(G)
    _drag(app, _towards(app, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)), 3.0)  # far past the neighbour
    assert mesh.vertex_position(vid) == pytest.approx((0.0, 1.0, 0.0))
    app.key_release(G)


def test_dragging_back_restores_the_start_and_esc_and_tap_change_nothing(app):
    mesh = app.scene.mesh
    vid = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {vid}
    before = _state(app)
    app.key_press(G)
    vector = _towards(app, (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    _drag(app, vector, 0.6)
    assert mesh.vertex_position(vid) != (0.0, 0.0, 0.0)
    _drag(app, vector, -0.6)
    assert mesh.vertex_position(vid) == (0.0, 0.0, 0.0)
    assert app.key_press(ESC) is True
    assert "Vertex Slide cancelled" == app.status_message
    assert _state(app) == before
    app.key_press(G)
    app.key_release(G)
    assert _state(app) == before
    assert not app.history.can_undo()


def test_several_vertices_each_take_their_own_best_edge(app):
    mesh = app.scene.mesh
    a, b = _vertex(mesh, -1.0, 0.0), _vertex(mesh, 1.0, -1.0)
    app.selection.vertices = {a, b}
    app.key_press(G)
    _drag(app, _towards(app, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), 0.5)
    app.key_release(G)
    # One common amount (the drag along the mean screen direction); each moved right along its own edge.
    ax, ay, _ = mesh.vertex_position(a)
    bx, by, _ = mesh.vertex_position(b)
    assert ay == 0.0 and by == -1.0
    assert -1.0 < ax < 0.0 and 1.0 < bx < 2.0
    assert ax + 1.0 == pytest.approx(bx - 1.0)


def test_hovered_vertex_without_selection(app):
    mesh = app.scene.mesh
    vid = _vertex(mesh, 1.0, 1.0)
    app.selection.hovered = vid
    assert app.key_press(G) is True
    _drag(app, _towards(app, (1.0, 1.0, 0.0), (1.0, 0.0, 0.0)), 0.25)
    app.key_release(G)
    assert mesh.vertex_position(vid) == pytest.approx((1.0, 0.75, 0.0))


def test_g_in_edge_mode_stays_loop_slide(app):
    app.key_press(K2)
    mesh = app.scene.mesh
    a, b = _vertex(mesh, 0.0, 0.0), _vertex(mesh, 0.0, 1.0)
    (edge,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    app.selection.edges = {edge}
    assert app.key_press(G) is True
    assert app.status_message.startswith("Loop Slide")


def test_nothing_to_slide_and_masked_vertices_refuse(app):
    assert app.key_press(G) is False
    assert "select or hover a vertex" in app.status_message
    mesh = app.scene.mesh
    vid = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {vid}
    app.key_press(CTRL_M)
    assert app.key_press(G) is False
    assert "masked" in app.status_message


def test_under_symmetry_the_partner_follows_exactly(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    vid, partner = _vertex(mesh, -1.0, 0.0), _vertex(mesh, 1.0, 0.0)
    app.selection.vertices = {vid}
    app.key_press(G)
    _drag(app, _towards(app, (-1.0, 0.0, 0.0), (-1.0, 1.0, 0.0)), 0.3)
    app.key_release(G)
    assert app.status_message == "Vertex Slide committed"
    px, py, pz = mesh.vertex_position(vid)
    assert mesh.vertex_position(partner) == (-px, py, pz)
    assert 0.0 < py < 1.0 and abs(px) == 1.0
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_under_symmetry_a_seam_vertex_only_slides_along_the_seam(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    vid = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {vid}
    app.key_press(G)
    # Dragging sideways (out of the plane) has no in-plane edge to follow ...
    _drag(app, _towards(app, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), 0.5)
    assert mesh.vertex_position(vid)[0] == 0.0
    # ... dragging up slides along the seam.
    _drag(app, _towards(app, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)), 0.4)
    app.key_release(G)
    x, y, _ = mesh.vertex_position(vid)
    assert x == 0.0 and y > 0.0
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_under_symmetry_the_slide_stops_short_of_the_neighbour(app):
    """Two vertices on one position would break the position-based mirror pairing."""
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    vid = _vertex(mesh, -1.0, 0.0)
    app.selection.vertices = {vid}
    app.key_press(G)
    _drag(app, _towards(app, (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)), 5.0)
    assert app.status_message == "Vertex Slide: 98 %"
    app.key_release(G)
    assert mesh.vertex_position(vid)[1] == pytest.approx(0.98)
    assert symmetry_state(mesh) is SymmetryState.VALID


# -- module -----------------------------------------------------------------------------------


def test_plan_lists_the_neighbours_and_positions_interpolate():
    mesh = _grid()
    vid = _vertex(mesh, 0.0, 0.0)
    plan = plan_vertex_slide(mesh, {vid})
    assert {p for _, p in plan.candidates[vid]} == {
        (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
    }
    right = next(n for n, p in plan.candidates[vid] if p == (1.0, 0.0, 0.0))
    assert vertex_slide_positions(plan, {vid: right}, 0.25)[vid] == (0.25, 0.0, 0.0)
    assert vertex_slide_positions(plan, {vid: right}, 7.0)[vid] == (1.0, 0.0, 0.0)
    assert vertex_slide_positions(plan, {}, 0.5)[vid] == (0.0, 0.0, 0.0)


def test_partial_mask_slides_part_of_the_way_and_hidden_neighbours_are_no_targets():
    mesh = _grid()
    vid = _vertex(mesh, 0.0, 0.0)
    right = _vertex(mesh, 1.0, 0.0)
    plan = plan_vertex_slide(mesh, {vid}, mask={vid: 0.5}, blocked=frozenset({right}))
    assert right not in {n for n, _ in plan.candidates[vid]}
    up = _vertex(mesh, 0.0, 1.0)
    assert vertex_slide_positions(plan, {vid: up}, 1.0)[vid] == (0.0, 0.5, 0.0)
    with pytest.raises(VertexSlideRefused):
        plan_vertex_slide(mesh, set())


def test_best_neighbour_takes_the_largest_cosine():
    assert best_neighbour((0, 0), [(10, 0), (0, 10), (-10, 0)], (1, 3)) == 1
    assert best_neighbour((0, 0), [(10, 0)], (0, 0)) is None
    assert best_neighbour(None, [(10, 0)], (1, 0)) is None
