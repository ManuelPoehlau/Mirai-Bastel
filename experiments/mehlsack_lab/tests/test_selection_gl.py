"""Slice 3 GL event path under `xvfb-run -a` (hidden window, fixtures from `test_lab_gl`): a click
selects in each mode and the selection draws with the production selected layers; Shift / Ctrl /
Alt clicks and the click into empty space; an LMB drag moves the selection; without a selection
the LMB drag is bit-identical to the Slice 1–2b path (drag began at the press); a press in empty
space with a selection drags nothing; Alt+LMB click toggles, Alt+LMB drag orbits; Esc drops an
undecided press; Shift+R adds the ring and never arms Scale. Skips cleanly without GL."""

from __future__ import annotations

from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()

from pyglet.window import key, mouse  # noqa: E402

import pytest  # noqa: E402

from core import SelectionMode  # noqa: E402
from mirai.viewport.picking import pick_component  # noqa: E402
from mehlsack_lab.lab_selection import selection_target  # noqa: E402
from mehlsack_lab.targets import MODE_LOOP, MODE_RING  # noqa: E402

from .test_lab_gl import HEIGHT, WIDTH, find_hover, gl_error, to_edit, window  # noqa: E402,F401

EMPTY = (WIDTH - 6, HEIGHT // 2)  # right edge, beside the box, outside panel and HUD


def click(win, x, y, modifiers=0):
    win.on_mouse_motion(x, y, 0, 0)
    win.on_mouse_press(x, y, mouse.LEFT, modifiers)
    win.on_mouse_release(x, y, mouse.LEFT, modifiers)


def drag(win, x, y, steps, modifiers=0, dy=2):
    win.on_mouse_motion(x, y, 0, 0)
    win.on_mouse_press(x, y, mouse.LEFT, modifiers)
    for i in range(steps):
        win.on_mouse_drag(x, y + (i + 1) * dy, 0, dy, mouse.LEFT, modifiers)
    win.on_mouse_release(x, y + steps * dy, mouse.LEFT, modifiers)


def find_pick(win, want=lambda hit, hover: True):
    """A cursor position with a hover target where a click in the active mode hits a handle."""
    mesh, mode = win.scene.mesh, win.state.selection.mode
    for y in range(HEIGHT // 2 - 100, HEIGHT // 2 + 100, 3):
        for x in range(WIDTH // 2 - 160, WIDTH // 2 + 160, 3):
            if win.panel.contains(x, y):
                continue
            win.on_mouse_motion(x, y, 0, 0)
            hover = win.scene.hover
            if hover is None:
                continue
            hit = pick_component(win.scene.camera, mesh, mode, x, y, WIDTH, HEIGHT, occlusion=True)
            if hit is not None and want(hit, hover):
                return x, y
    pytest.fail("no pickable position found")


def mesh_positions(win):
    mesh = win.scene.mesh
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def selected(win):
    sel = win.state.selection
    return {SelectionMode.VERTEX: sel.vertices, SelectionMode.EDGE: sel.edges, SelectionMode.FACE: sel.faces}[sel.mode]


def test_click_selects_in_each_mode_and_draws(window):
    to_edit(window)
    for symbol, mode in ((key._1, SelectionMode.VERTEX), (key._2, SelectionMode.EDGE), (key._3, SelectionMode.FACE)):
        window.on_key_press(symbol, 0)
        assert window.state.selection.mode is mode and window.state.selection.is_empty()
        x, y = find_pick(window)
        click(window, x, y)
        assert len(selected(window)) == 1, mode
        window.on_draw()
        assert gl_error() == 0
        scene = window.scene
        counts = (len(scene.points.points("selected")), scene.lines.segment_count("selected"),
                  scene.faces.triangle_count("selected"))
        assert counts == {SelectionMode.VERTEX: (1, 0, 0), SelectionMode.EDGE: (0, 1, 0),
                          SelectionMode.FACE: (0, 0, 2)}[mode]
        # bands and seed points now come from the selection, the hover line stays the hover's
        assert scene.target.seeds == selection_target(scene.mesh, window.state.selection).seeds
        assert scene.hover is not None and scene.lines.segment_count("hover") == len(scene.hover.edges)


def test_modifier_clicks_and_click_into_empty_space(window):
    to_edit(window)
    window.on_key_press(key._2, 0)
    a = find_hover(window)
    first = window.scene.hover.edge
    b = find_hover(window, lambda t: t.edge != first)
    click(window, *a)
    click(window, *b, key.MOD_SHIFT)
    assert len(selected(window)) == 2
    click(window, *a, key.MOD_CTRL)
    assert len(selected(window)) == 1
    click(window, *a, key.MOD_ALT)
    click(window, *b, key.MOD_ALT)
    assert selected(window) == {first}
    for mods in (key.MOD_SHIFT, key.MOD_CTRL, key.MOD_ALT):
        click(window, *EMPTY, mods)
        assert selected(window) == {first}
    click(window, *EMPTY)
    assert window.state.selection.is_empty()
    window.on_draw()
    assert window.scene.lines.segment_count("selected") == 0 and gl_error() == 0


def test_lmb_drag_moves_the_selection(window):
    to_edit(window, h=6, n=3)
    window.on_key_press(key._2, 0)
    x, y = find_pick(window)
    click(window, x, y)
    seeds = selection_target(window.scene.mesh, window.state.selection).seeds
    other = find_pick(window, lambda hit, hover: not (hover.seeds & seeds))  # press over another loop
    start = mesh_positions(window)
    drag(window, *other, 12)
    session = window.state.session
    assert len(session.history) == 1 and session.last.seeds == seeds
    assert all(window.scene.mesh.vertex_position(v) != start[v] for v in seeds)
    window.on_draw()
    segment = window.scene.selection_overlay.line_layers(window.scene.mesh)["selected"][0]
    edge = next(iter(window.state.selection.edges))
    a, b = window.scene.mesh.edge_vertices(edge)
    assert segment == (window.scene.mesh.vertex_position(a), window.scene.mesh.vertex_position(b))
    assert gl_error() == 0


def test_drag_without_selection_is_bit_identical_to_the_press_drag(window):
    to_edit(window, h=6, n=3)
    window.on_key_press(key.Y, 0)  # a mask: the anchor depth changes between events
    x, y = find_hover(window)
    target = window.scene.target
    start = mesh_positions(window)
    events = [(1, 1), (0, 2), (2, 1), (0, 3), (1, 4), (-1, 2), (0, 5)]
    window.on_mouse_press(x, y, mouse.LEFT, 0)
    for dx, dy in events:
        window.on_mouse_drag(x, y, dx, dy, mouse.LEFT, 0)
    window.on_mouse_release(x, y, mouse.LEFT, 0)
    via_pointer = mesh_positions(window)
    assert via_pointer != start and window.state.session.last.seeds == target.seeds
    window.on_key_press(key.Z, key.MOD_CTRL)
    assert mesh_positions(window) == start
    # the Slice 1–2b path: the drag begins at the press and every event is one step
    window.state.begin_drag(target)
    for dx, dy in events:
        window.drag_by(dx, dy)
    window.state.end_drag()
    assert mesh_positions(window) == via_pointer


def test_press_in_empty_space_with_a_selection_drags_nothing(window):
    to_edit(window)
    x, y = find_pick(window)
    click(window, x, y)
    before = set(window.state.selection.vertices)
    assert before
    drag(window, *EMPTY, 12)
    assert len(window.state.session.history) == 0 and window.state.selection.vertices == before


def test_alt_click_toggles_and_alt_drag_orbits(window):
    to_edit(window)
    x, y = find_pick(window)
    click(window, x, y, key.MOD_ALT)
    assert len(selected(window)) == 1
    yaw = window.scene.camera.yaw
    window.on_mouse_press(x, y, mouse.LEFT, key.MOD_ALT)
    for _ in range(5):
        window.on_mouse_drag(x, y, 3, 0, mouse.LEFT, key.MOD_ALT)
    window.on_mouse_release(x, y, mouse.LEFT, key.MOD_ALT)
    assert window.scene.camera.yaw != yaw and len(selected(window)) == 1
    assert len(window.state.session.history) == 0


def test_esc_drops_an_undecided_press(window):
    to_edit(window)
    x, y = find_hover(window)
    window.on_mouse_press(x, y, mouse.LEFT, 0)
    assert window.state.pointer_pending
    window.on_key_press(key.ESCAPE, 0)
    assert not window.state.pointer_pending and window.context is not None  # not closed
    window.on_mouse_release(x, y, mouse.LEFT, 0)
    assert window.state.selection.is_empty() and len(window.state.session.history) == 0
    window.on_key_press(key.W, 0)  # nothing pending any more: W arms again
    assert window.state.armed


def test_shift_l_and_shift_r_in_the_window(window):
    to_edit(window, h=6, n=3)
    window.on_key_press(key._2, 0)
    find_hover(window)
    edge = window.scene.hover.edge
    window.on_key_press(key.R, key.MOD_SHIFT)
    assert not window.state.armed
    window.on_key_release(key.R, key.MOD_SHIFT)
    ring = window.state.session.target(edge, MODE_RING)
    assert window.state.selection.edges == set(ring.edges)
    window.on_key_press(key.L, key.MOD_SHIFT)
    loop = window.state.session.target(edge, MODE_LOOP)
    assert window.state.selection.edges == set(ring.edges) | set(loop.edges)
    window.on_draw()
    assert window.scene.lines.segment_count("selected") == len(window.state.selection.edges)
    assert gl_error() == 0
