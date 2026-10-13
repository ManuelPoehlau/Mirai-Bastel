"""Slice 3b GL event path under `xvfb-run -a` (fixtures from `test_lab_gl`): component hover by
default (vertex point, face fill), `L` switches to the Loop/Ring hover and back, an LMB drag with
an empty selection moves the hovered edge, a double click selects the edge loop, Shift+double
click a loop section, an `L`-mode click a whole loop, Shift+L over a vertex hover picks the edge
under the cursor. Skips cleanly without GL."""

from __future__ import annotations

from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()

from pyglet.window import key, mouse  # noqa: E402

from core import EdgeId, FaceId, SelectionMode, VertexId  # noqa: E402
from mehlsack_lab.lab_selection import MODE_COMPONENT  # noqa: E402
from mehlsack_lab.targets import MODE_LOOP  # noqa: E402

from .test_lab_gl import find_hover, gl_error, to_edit, window  # noqa: E402,F401
from .test_selection_gl import click, drag, find_pick, mesh_positions  # noqa: E402


def test_component_hover_by_default_and_l_switches(window):
    to_edit(window, loop_mode=False)
    scene, state = window.scene, window.state
    find_pick(window)
    assert isinstance(state.selection.hovered, VertexId) and scene.target.mode == MODE_COMPONENT
    window.on_draw()
    assert len(scene.points.points("hover")) >= 1 and gl_error() == 0
    window.on_key_press(key._3, 0)
    find_pick(window)
    window.on_draw()
    assert isinstance(state.selection.hovered, FaceId) and scene.faces.triangle_count("hover") == 2
    window.on_key_press(key.L, 0)
    assert state.loop_mode and state.selection.hovered is None
    find_hover(window)
    assert scene.hover.mode == MODE_LOOP and scene.hover.closed
    window.on_draw()
    assert scene.faces.triangle_count("hover") == 0 and gl_error() == 0
    window.on_key_press(key.L, 0)
    find_pick(window)
    assert isinstance(state.selection.hovered, FaceId)


def test_drag_without_selection_moves_the_hovered_edge(window):
    to_edit(window, h=6, n=3, loop_mode=False)
    window.on_key_press(key._2, 0)
    x, y = find_pick(window)
    edge = window.state.selection.hovered
    assert isinstance(edge, EdgeId)
    ends = set(window.scene.mesh.edge_vertices(edge))
    start = mesh_positions(window)
    drag(window, x, y, 10)
    assert window.state.session.last.seeds == ends and window.state.selection.is_empty()
    assert all(window.scene.mesh.vertex_position(v) != start[v] for v in ends)


def test_double_click_selects_the_loop_and_shift_double_click_a_section(window):
    to_edit(window, h=6, n=3, loop_mode=False)
    window.on_key_press(key._2, 0)
    x, y = find_pick(window, lambda hit, hover: True)
    edge = window.state.selection.hovered
    click(window, x, y)
    click(window, x, y)  # double click
    loop = window.state.session.target(edge, MODE_LOOP)
    assert window.state.selection.edges == set(loop.edges) and len(loop.edges) > 2
    window.on_draw()
    assert window.scene.lines.segment_count("selected") == len(loop.edges) and gl_error() == 0
    # Shift+double click on another edge of the same loop: only the section from `edge`
    other = find_pick(window, lambda hit, hover: hit in loop.edges and hit != edge)
    target = window.state.selection.hovered
    click(window, x, y)  # replace: just `edge` (a fresh series: the last click was a double)
    assert window.state.selection.edges == {edge}
    click(window, *other, key.MOD_SHIFT)
    click(window, *other, key.MOD_SHIFT)
    edges = window.state.selection.edges
    assert {edge, target} <= edges and edges <= set(loop.edges) and len(edges) < len(loop.edges)


def test_l_mode_click_takes_the_whole_loop(window):
    to_edit(window, h=6, n=3)  # L mode
    window.on_key_press(key._2, 0)
    x, y = find_hover(window)
    loop = window.scene.hover
    click(window, x, y)
    assert window.state.selection.edges == set(loop.edges)
    click(window, x, y, key.MOD_CTRL)
    assert window.state.selection.is_empty()


def test_shift_l_over_a_vertex_hover_uses_the_edge_under_the_cursor(window):
    to_edit(window, h=6, n=3, loop_mode=False)
    assert window.state.selection.mode is SelectionMode.VERTEX
    x, y = find_hover(window, lambda t: True)
    window.on_key_press(key.L, key.MOD_SHIFT)
    assert window.state.selection.vertices, window.state.note
    assert window.state.edge_under_cursor is None  # used once, then dropped
    assert not window.state.loop_mode
