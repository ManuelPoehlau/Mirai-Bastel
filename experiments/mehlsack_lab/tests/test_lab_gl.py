"""§7.8 GL smoke test under `xvfb-run -a` (hidden 640x480 window): the window opens, a frame
draws, the curve panel draws; plus the event path a mouse would take (wheel → box, Enter,
hover → target + bands, LMB drag → one History entry without a structural rebuild, panel drag
→ Nachführen, RMB cancel, Undo → re-pick). GL tests skip cleanly when no GL is available."""

from __future__ import annotations

import pytest

from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()

from pyglet.window import key, mouse  # noqa: E402

from mehlsack_lab import lab_bindings as lb  # noqa: E402
from mehlsack_lab.box import BoxParams  # noqa: E402

WIDTH, HEIGHT = 640, 480


@pytest.fixture()
def window():
    from pyglet import gl

    from mehlsack_lab.lab_window import MehlsackLabWindow

    try:
        win = MehlsackLabWindow(WIDTH, HEIGHT, visible=False, box=BoxParams(height=2.5, width=1.5, h=1, n=1))
    except Exception as exc:  # no GL / no display in this environment
        pytest.skip(f"no GL context available: {exc}")
    win.switch_to()
    fb_width, fb_height = win.get_framebuffer_size()
    gl.glViewport(0, 0, fb_width, fb_height)
    yield win
    win.close()


def gl_error() -> int:
    from pyglet import gl

    return int(gl.glGetError())


def read_rgb():
    from pyglet import gl

    gl.glFinish()
    image = pyglet.image.get_buffer_manager().get_color_buffer().get_region(0, 0, WIDTH, HEIGHT).get_image_data()
    data = image.get_data("RGBA", WIDTH * 4)
    return data


def pixel(data, x, y):
    i = (y * WIDTH + x) * 4
    return tuple(data[i:i + 3])


def frame(window):
    window.switch_to()
    window.on_draw()
    return read_rgb()


def wheel(window, steps, modifier_key=None):
    if modifier_key is not None:
        window.on_key_press(modifier_key, 0)
    for _ in range(abs(steps)):
        window.on_mouse_scroll(0, 0, 0, 1 if steps > 0 else -1)
    if modifier_key is not None:
        window.on_key_release(modifier_key, 0)


def to_edit(window, h=6, n=3):
    wheel(window, h - window.state.box.h, key.LSHIFT)
    wheel(window, n - window.state.box.n, key.LCTRL)
    window.on_key_press(key.RETURN, 0)
    assert window.state.phase == lb.PHASE_EDIT
    window.on_draw()


def find_hover(window, want=lambda t: t.closed):
    """Scans the window for a cursor position whose hover target satisfies `want`."""
    for y in range(HEIGHT // 2 - 60, HEIGHT // 2 + 60, 4):
        for x in range(WIDTH // 2 - 160, WIDTH // 2 + 160, 4):
            if window.panel.contains(x, y):
                continue
            window.on_mouse_motion(x, y, 0, 0)
            target = window.scene.target
            if target is not None and want(target):
                return x, y
    pytest.fail("no hover target found")


def test_window_opens_and_draws_box_and_panel(window):
    data = frame(window)
    assert gl_error() == 0
    background = pixel(data, 2, HEIGHT - 2)
    centre = pixel(data, WIDTH // 2, HEIGHT // 2)
    assert centre != background  # the box is drawn
    # no curve panel in the creation phase
    px, py = int(window.panel.x + 30), int(window.panel.y + 20)
    before_panel = pixel(data, px, py)
    to_edit(window)
    data = frame(window)
    assert gl_error() == 0
    assert pixel(data, px, py) != before_panel  # panel background/tint drawn in the edit phase
    zero_y = int(round(window.panel.zero_y()))
    zx = int(window.panel.plot[0] + 5)
    assert max(pixel(data, zx, zero_y)) > 180  # bright zero line


def test_creation_wheel_rebuilds_the_box(window):
    wheel(window, 2, key.LSHIFT)
    wheel(window, 1, key.LCTRL)
    wheel(window, 1, key.LALT)
    wheel(window, -1)
    box = window.state.box
    assert (box.h, box.n, box.width, box.height) == (3, 2, 1.75, 2.25)
    assert len(window.scene.mesh.all_face_ids()) == box.counts()[2]
    frame(window)
    assert gl_error() == 0


def test_hover_drag_commit_undo_without_structural_rebuild(window):
    to_edit(window)
    x, y = find_hover(window)
    target = window.scene.target
    window.on_draw()
    assert len(window.scene.points.points("hover")) == len(target.seeds)  # seeds as hover points
    rm = window.scene.render_mesh
    before_ids = dict(rm.resource_ids())
    before_topology = rm.benchmark_counters.get("topology_updates", 0)
    start = {v: window.scene.mesh.vertex_position(v) for v in window.scene.mesh.all_vertex_ids()}
    window.on_mouse_press(x, y, mouse.LEFT, 0)
    assert window.state.dragging
    for i in range(12):
        window.on_mouse_drag(x, y + i, 0, 2, mouse.LEFT, 0)
        window.on_draw()
    window.on_mouse_release(x, y + 12, mouse.LEFT, 0)
    assert not window.state.dragging and len(window.state.session.history) == 1
    assert dict(rm.resource_ids()) == before_ids
    assert rm.benchmark_counters.get("topology_updates", 0) == before_topology
    assert all(window.scene.mesh.vertex_position(v) != start[v] for v in target.seeds)
    assert gl_error() == 0
    window.on_key_press(key.Z, key.MOD_CTRL)
    window.on_draw()
    assert {v: window.scene.mesh.vertex_position(v) for v in start} == start
    assert gl_error() == 0


def test_panel_drag_retunes_the_last_gesture(window):
    to_edit(window, h=8, n=4)
    wheel(window, 4, key.LSHIFT)  # bigger radius, so the curve matters
    x, y = find_hover(window, lambda t: t.closed and len(t.edges) == 16)
    window.on_mouse_press(x, y, mouse.LEFT, 0)
    for i in range(10):
        window.on_mouse_drag(x, y + i, 0, 3, mouse.LEFT, 0)
    window.on_mouse_release(x, y + 10, mouse.LEFT, 0)
    end = {v: window.scene.mesh.vertex_position(v) for v in window.scene.mesh.all_vertex_ids()}
    p = window.panel
    px, py = p.to_screen(0.6, window.state.curve.interior[2])
    window.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
    assert window.state.dragging is False  # the press went to the panel, not the mesh
    low = int(p.to_screen(0.6, -0.8)[1])
    window.on_mouse_drag(int(px), low, 0, low - int(py), mouse.LEFT, 0)
    window.on_mouse_release(int(px), low, mouse.LEFT, 0)
    assert window.state.curve.interior[2] < 0.0
    assert len(window.state.session.history) == 1
    assert window.state.session.last.retunes >= 1
    after = {v: window.scene.mesh.vertex_position(v) for v in end}
    assert after != end
    window.on_draw()
    assert gl_error() == 0


def test_rmb_cancels_exactly(window):
    to_edit(window)
    x, y = find_hover(window)
    start = {v: window.scene.mesh.vertex_position(v) for v in window.scene.mesh.all_vertex_ids()}
    window.on_mouse_press(x, y, mouse.LEFT, 0)
    for i in range(5):
        window.on_mouse_drag(x, y + i, 0, 4, mouse.LEFT, 0)
    window.on_mouse_press(x, y + 5, mouse.RIGHT, 0)
    assert not window.state.dragging
    window.on_mouse_drag(x, y + 9, 0, 4, mouse.LEFT | mouse.RIGHT, 0)  # ignored until release
    window.on_mouse_release(x, y + 9, mouse.LEFT, 0)
    assert {v: window.scene.mesh.vertex_position(v) for v in start} == start
    assert len(window.state.session.history) == 0


def test_help_overlay_and_esc(window):
    window.on_key_press(key.H, 0)
    data = frame(window)
    assert window.state.help_visible and gl_error() == 0
    window.on_key_press(key.H, 0)
    assert pixel(frame(window), WIDTH // 2, HEIGHT // 2) != pixel(data, WIDTH // 2, HEIGHT // 2)
