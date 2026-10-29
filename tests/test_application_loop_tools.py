"""Loop tools in the production app (2026-10-15, promoted from the Playground, Manu):
Shift+L / Shift+R (loop / ring to the selection), I (Loop Insert), hold G (Loop Slide).

Pinned: edge mode only; seeds = selected edges, else the hovered edge; Loop Insert = Edge
Connect of the ring (one History entry, new loop selected); Loop Slide = hold-key gesture like
T (one History entry, Esc exact, tap = no change), open loop pieces slide too; under symmetry
both sides stay exact mirrors (`symmetry_state` VALID)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import set_symmetry_axis
from mirai.topology.loop_slide import LoopSlideRefused, plan_loop_slide, slide_positions

WIDTH, HEIGHT = 800, 600
N = 4


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


SHIFT_L, SHIFT_R, I, G = _key("l", "shift"), _key("r", "shift"), _key("i"), _key("g")
ESC, CTRL_Z, CTRL_Y = _key("ESCAPE"), _key("z", "ctrl"), _key("y", "ctrl")
K1, K2 = _key("1"), _key("2")


def _grid(n: int = N, size: float = 4.0) -> Mesh:
    """n x n quads in the XY plane, centred on the origin (symmetric about X = 0)."""
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
    app.key_press(K2)
    return app


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _edge(mesh, a, b):
    (eid,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    return eid


def _h_edge(mesh, x: float, y: float):
    """The horizontal edge from (x, y) to (x + 1, y)."""
    return _edge(mesh, _vertex(mesh, x, y), _vertex(mesh, x + 1.0, y))


def _v_edge(mesh, x: float, y: float):
    """The vertical edge from (x, y) to (x, y + 1)."""
    return _edge(mesh, _vertex(mesh, x, y), _vertex(mesh, x, y + 1.0))


def _state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def _select(app, *edges) -> None:
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = set(edges)


def _slide(app, dx: float = 6.0, dy: float = 0.0, steps: int = 5) -> None:
    x, y = 400.0, 300.0
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)


# -- bindings -------------------------------------------------------------------------------


def test_default_bindings_follow_the_artist_input_truth():
    bindings = build_default_bindings()
    assert bindings.command_for(SHIFT_L) == cmd.EDGE_LOOP
    assert bindings.command_for(SHIFT_R) == cmd.EDGE_RING
    assert bindings.command_for(I) == cmd.LOOP_INSERT
    assert bindings.command_for(G) == cmd.LOOP_SLIDE
    # R stays Scale; Shift+R is a different input.
    assert bindings.command_for(_key("r")) == cmd.SCALE


# -- Shift+L / Shift+R ----------------------------------------------------------------------


def test_shift_l_adds_the_loop_of_the_selected_edge(app):
    mesh = app.scene.mesh
    seed = _h_edge(mesh, -1.0, 0.0)
    _select(app, seed)
    assert app.key_press(SHIFT_L) is True
    # The middle row: four horizontal edges at y = 0 (open loop, ends on the border).
    assert app.selection.edges == {_h_edge(mesh, x, 0.0) for x in (-2.0, -1.0, 0.0, 1.0)}
    assert not app.history.can_undo()  # a selection change, not a History step


def test_shift_r_adds_the_ring_of_the_selected_edge(app):
    mesh = app.scene.mesh
    _select(app, _h_edge(mesh, -1.0, 0.0))
    assert app.key_press(SHIFT_R) is True
    assert app.selection.edges == {_h_edge(mesh, -1.0, y) for y in (-2.0, -1.0, 0.0, 1.0, 2.0)}


def test_loop_select_uses_the_hovered_edge_without_selection(app):
    mesh = app.scene.mesh
    hovered = _v_edge(mesh, 0.0, -1.0)
    app.selection.hovered = hovered
    assert app.key_press(SHIFT_L) is True
    assert app.selection.edges == {_v_edge(mesh, 0.0, y) for y in (-2.0, -1.0, 0.0, 1.0)}


def test_loop_tools_need_edge_mode(app):
    app.key_press(K1)
    before = _state(app)
    for key in (SHIFT_L, SHIFT_R, I):
        assert app.key_press(key) is False
        assert "edge mode" in app.status_message
    assert app.key_press(G) is False
    assert _state(app) == before


# -- I (Loop Insert) ------------------------------------------------------------------------


def test_loop_insert_cuts_a_loop_through_the_ring_one_undo_step(app):
    mesh = app.scene.mesh
    before = _state(app)
    faces = len(mesh.all_face_ids())
    _select(app, _h_edge(mesh, -1.0, 0.0))
    assert app.key_press(I) is True
    assert app.status_message == "Loop Insert"
    assert len(mesh.all_face_ids()) == faces + N  # one column of four quads split
    new_edges = app.selection.edges
    assert len(new_edges) == N
    assert all(mesh.vertex_position(v)[0] == -0.5 for e in new_edges for v in mesh.edge_vertices(e))
    assert app.key_press(CTRL_Z) is True
    assert _state(app) == before
    assert app.key_press(CTRL_Y) is True
    assert len(mesh.all_face_ids()) == faces + N


def test_loop_insert_under_symmetry_mirrors_the_loop(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    faces = len(mesh.all_face_ids())
    _select(app, _h_edge(mesh, -2.0, 0.0))
    assert app.key_press(I) is True, app.status_message
    assert len(mesh.all_face_ids()) == faces + 2 * N
    xs = {mesh.vertex_position(v)[0] for v in mesh.all_vertex_ids()}
    assert {-1.5, 1.5} <= xs
    assert symmetry_state(mesh) is SymmetryState.VALID


# -- G (Loop Slide) -------------------------------------------------------------------------


def test_slide_moves_the_loop_and_commits_one_undo_step(app):
    mesh = app.scene.mesh
    loop = {_v_edge(mesh, -1.0, y) for y in (-2.0, -1.0, 0.0, 1.0)}
    _select(app, *loop)
    before = _state(app)
    assert app.key_press(G) is True
    assert app.interaction_owner == "transform"
    _slide(app)
    xs = {mesh.vertex_position(v)[0] for e in loop for v in mesh.edge_vertices(e)}
    assert len(xs) == 1 and xs != {-1.0} and -2.0 < xs.pop() < 0.0
    assert app.key_release(G) is True
    assert app.status_message == "Loop Slide committed"
    assert app.key_press(CTRL_Z) is True
    assert _state(app) == before


def test_slide_esc_restores_exactly_and_a_tap_changes_nothing(app):
    mesh = app.scene.mesh
    _select(app, *{_v_edge(mesh, 0.0, y) for y in (-2.0, -1.0, 0.0, 1.0)})
    before = _state(app)
    app.key_press(G)
    _slide(app)
    assert _state(app) != before
    assert app.key_press(ESC) is True
    assert _state(app) == before
    assert app.key_release(G) is False  # already ended
    app.key_press(G)
    app.key_release(G)
    assert _state(app) == before
    assert not app.history.can_undo()


def test_slide_under_symmetry_keeps_the_mirror_exact(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    _select(app, *{_v_edge(mesh, -1.0, y) for y in (-2.0, -1.0, 0.0, 1.0)})
    app.key_press(G)
    _slide(app)
    app.key_release(G)
    assert app.status_message == "Loop Slide committed"
    left = {mesh.vertex_position(v)[0] for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] < 0}
    right = {mesh.vertex_position(v)[0] for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 0}
    assert {-x for x in left} == right
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_slide_under_symmetry_stops_short_of_the_next_loop(app):
    """2026-10-29: all the way would put two vertices on one position (ambiguous mirror pairing)."""
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    _select(app, *{_v_edge(mesh, -1.0, y) for y in (-2.0, -1.0, 0.0, 1.0)})
    app.key_press(G)
    _slide(app, dx=40.0, steps=40)
    app.key_release(G)
    assert app.status_message == "Loop Slide committed"
    assert symmetry_state(mesh) is SymmetryState.VALID
    xs = sorted({round(mesh.vertex_position(v)[0], 9) for v in mesh.all_vertex_ids()})
    assert len(xs) == 5  # no loop landed on its neighbour


def test_slide_refuses_the_seam_loop_under_symmetry(app):
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    _select(app, *{_v_edge(mesh, 0.0, y) for y in (-2.0, -1.0, 0.0, 1.0)})
    before = _state(app)
    assert app.key_press(G) is False
    assert "mirror plane" in app.status_message
    assert _state(app) == before


# -- loop_slide module ----------------------------------------------------------------------


def test_plan_refuses_branches_and_border_edges():
    mesh = _grid()
    corner = _vertex(mesh, 0.0, 0.0)
    branch = [e for e in mesh.vertex_edges(corner)][:3]
    with pytest.raises(LoopSlideRefused):
        plan_loop_slide(mesh, branch)
    with pytest.raises(LoopSlideRefused):
        plan_loop_slide(mesh, [_h_edge(mesh, -2.0, -2.0)])  # bottom border


def test_slide_positions_interpolate_towards_either_side():
    mesh = _grid()
    edge = _v_edge(mesh, 0.0, -1.0)
    plan = plan_loop_slide(mesh, [edge])
    full_a = slide_positions(plan, 1.0)
    full_b = slide_positions(plan, -1.0)
    xs_a = {p[0] for p in full_a.values()}
    xs_b = {p[0] for p in full_b.values()}
    assert {xs_a.pop(), xs_b.pop()} == {-1.0, 1.0}
    assert slide_positions(plan, 5.0) == full_a  # clamped
