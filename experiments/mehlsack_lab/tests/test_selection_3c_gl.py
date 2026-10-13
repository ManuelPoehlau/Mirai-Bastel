"""Slice 3c GL event path under `xvfb-run -a` (fixtures from `test_lab_gl`): a double click in
Vertex mode selects a vertex loop through the clicked vertex; an `L`-mode click in Face mode
selects the hovered Ring's faces. Skips cleanly without GL."""

from __future__ import annotations

from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()

from pyglet.window import key  # noqa: E402

from core import VertexId  # noqa: E402
from mehlsack_lab.lab_selection import ring_faces  # noqa: E402

from .test_lab_gl import find_hover, gl_error, to_edit, window  # noqa: E402,F401
from .test_selection_gl import click, find_pick  # noqa: E402


def test_vertex_double_click_selects_a_vertex_loop(window):
    to_edit(window, h=6, n=3, loop_mode=False)
    x, y = find_pick(window)
    vertex = window.state.selection.hovered
    assert isinstance(vertex, VertexId)
    click(window, x, y)
    click(window, x, y)
    selected = window.state.selection.vertices
    assert vertex in selected and len(selected) > 2, window.state.note
    window.on_draw()
    assert len(window.scene.points.points("selected")) == len(selected) and gl_error() == 0


def test_l_mode_face_click_selects_the_ring_faces(window):
    to_edit(window, h=6, n=3)  # L mode
    window.on_key_press(key._3, 0)
    x, y = find_hover(window)
    edge = window.scene.hover.edge
    faces, _closed = ring_faces(window.state.session.finder, edge)
    window.on_draw()
    assert window.scene.faces.triangle_count("hover") == 2 * len(faces)
    click(window, x, y)
    assert window.state.selection.faces == set(faces)
    window.on_draw()
    assert window.scene.faces.triangle_count("selected") == 2 * len(faces) and gl_error() == 0
