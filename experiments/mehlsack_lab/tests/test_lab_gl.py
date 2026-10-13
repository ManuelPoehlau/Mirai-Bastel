"""§7.8 GL smoke test under `xvfb-run -a` (hidden 640x480 window): the window opens, a frame
draws, the curve panel draws; plus the event path a mouse would take (wheel → box, Enter,
hover → target + bands, LMB drag → one History entry without a structural rebuild, panel drag
→ Nachführen, RMB cancel, Undo → re-pick). Slice 2a: Alt+Shift+wheel depth, panel handle drag
(aligned / Alt = corner), double-click reset, rim loop hover, surface preview (`P` on draws,
`P` off leaves the frame identical). GL tests skip cleanly when no GL is available."""

from __future__ import annotations

import pytest

from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()

from pyglet.window import key, mouse  # noqa: E402

from mehlsack_lab import lab_bindings as lb  # noqa: E402
from mehlsack_lab.box import BoxParams  # noqa: E402
from mirai.interaction.pointer import CLICK_THRESHOLD_PX  # noqa: E402

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


def to_edit(window, h=6, n=3, loop_mode=True):
    """Builds the box and enters the edit phase; `loop_mode` (default for the Slice 1–2b tests:
    the Loop/Ring hover they exercise) switches the Slice 3b `L` mode on."""
    wheel(window, h - window.state.box.h, key.LSHIFT)
    wheel(window, n - window.state.box.n, key.LCTRL)
    window.on_key_press(key.RETURN, 0)
    assert window.state.phase == lb.PHASE_EDIT
    if loop_mode != window.state.loop_mode:
        window.on_key_press(key.L, 0)
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
    window.on_key_press(key.LALT, 0)
    wheel(window, -2, key.LSHIFT)  # Alt+Shift+wheel = depth
    window.on_key_release(key.LALT, 0)
    box = window.state.box
    assert (box.h, box.n, box.width, box.height, box.depth) == (3, 2, 1.75, 2.25, 1.5)
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
    assert not window.state.dragging  # Slice 3 E24: click or drag is open until the threshold
    for i in range(12):
        window.on_mouse_drag(x, y + i, 0, 2, mouse.LEFT, 0)
        assert window.state.dragging == (2 * (i + 1) >= CLICK_THRESHOLD_PX)
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
    px, py = (round(c) for c in p.to_screen(*window.state.curve.knots[3]))
    window.on_mouse_press(px, py, mouse.LEFT, 0)
    assert window.state.dragging is False  # the press went to the panel, not the mesh
    assert window.state.curve.preset == "smooth"  # a press alone changes nothing
    low = int(p.to_screen(0.6, -0.8)[1])
    window.on_mouse_drag(px, low, 0, low - py, mouse.LEFT, 0)
    window.on_mouse_release(px, low, mouse.LEFT, 0)
    assert window.state.curve.knots[3][1] < 0.0
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


def _press_drag_release(window, start, end, modifiers=0):
    (x0, y0), (x1, y1) = start, end
    window.on_mouse_press(x0, y0, mouse.LEFT, modifiers)
    window.on_mouse_drag(x1, y1, x1 - x0, y1 - y0, mouse.LEFT, modifiers)
    window.on_mouse_release(x1, y1, mouse.LEFT, modifiers)


def test_panel_handles_aligned_alt_corner_and_double_click_reset(window, monkeypatch):
    to_edit(window)
    p = window.panel
    curve = window.state.curve
    i = 2
    handle = tuple(round(c) for c in p.to_screen(*curve.handles_out[i]))
    target = (handle[0] + 6, handle[1] + 20)
    _press_drag_release(window, handle, target)
    moved = window.state.curve
    assert moved.handles_out[i] != curve.handles_out[i] and moved.aligned[i]
    (kx, ky), (ax, ay), (bx, by) = moved.knots[i], moved.handles_in[i], moved.handles_out[i]
    assert abs((ax - kx) * (by - ky) - (ay - ky) * (bx - kx)) < 1e-9  # in handle followed
    # Alt+drag on the in handle: corner, the out handle stays
    handle_in = tuple(round(c) for c in p.to_screen(*moved.handles_in[i]))
    window.on_key_press(key.LALT, key.MOD_ALT)
    _press_drag_release(window, handle_in, (handle_in[0], handle_in[1] - 25), key.MOD_ALT)
    window.on_key_release(key.LALT, 0)
    broken = window.state.curve
    assert not broken.aligned[i] and broken.handles_out[i] == moved.handles_out[i]
    assert broken.handles_in[i] != moved.handles_in[i]
    window.on_draw()
    assert gl_error() == 0
    # double click on the knot: aligned automatic handles again
    knot = tuple(round(c) for c in p.to_screen(*broken.knots[i]))
    window.on_mouse_press(*knot, mouse.LEFT, 0)
    window.on_mouse_release(*knot, mouse.LEFT, 0)
    window.on_mouse_press(*knot, mouse.LEFT, 0)
    window.on_mouse_release(*knot, mouse.LEFT, 0)
    reset = window.state.curve
    assert reset.aligned[i] and reset.knots == broken.knots
    assert reset == broken.with_auto_handles(i)
    assert window.state.dragging is False


def test_rim_loop_hover_runs_around_the_box(window):
    to_edit(window, h=3, n=2)
    session = window.state.session
    mesh, cam = session.mesh, window.scene.camera
    found = None
    for eid in session.finder.rim_of_edge:  # hover the screen point of each rim edge's middle
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
        mid = tuple((a[k] + b[k]) / 2 for k in range(3))
        sx, sy = cam.project_to_screen(mid, WIDTH, HEIGHT)
        window.on_mouse_motion(sx, sy, 0, 0)
        target = window.scene.target
        if target is not None and target.edge in session.finder.rim_of_edge:
            found = target
            break
    assert found is not None
    assert found.closed and len(found.edges) == 8 and len(found.seeds) == 8
    window.on_draw()
    assert window.scene.lines.segment_count("hover") == 8
    assert len(window.scene.points.points("hover")) == 8


def test_surface_preview_draws_with_p_and_leaves_the_frame_identical_without(window):
    to_edit(window, h=8, n=4)
    wheel(window, 5, key.LSHIFT)  # radius up: more faces in the influence
    find_hover(window)
    window._hud_revision = window.state.revision  # keep the HUD text out of the comparison
    base = frame(window)
    assert window.scene.preview.triangle_count("influence_preview") == 0
    window.on_key_press(key.P, 0)
    assert window.state.preview_visible
    with_preview = frame(window)
    assert gl_error() == 0
    assert window.scene.preview.triangle_count("influence_preview") > 0
    changed = sum(1 for i in range(0, len(base), 4) if base[i:i + 3] != with_preview[i:i + 3])
    assert changed > 500  # the influenced faces are tinted
    # orange where the seeds are (the strongest tint): some pixel became redder than it was
    assert any(with_preview[i] > base[i] + 40 and with_preview[i + 2] < base[i + 2]
               for i in range(0, len(base), 4))
    window.on_key_press(key.P, 0)
    assert not window.state.preview_visible
    window._hud_revision = window.state.revision
    without = frame(window)
    hud_rows = HEIGHT - 12 * 18  # the HUD status line changes ("Vorschau an/aus"): compare below it
    stride = WIDTH * 4
    assert without[:hud_rows * stride] == base[:hud_rows * stride]


def test_hold_r_e_over_the_hover_through_the_window(window):
    """Slice 2b E16: hover → R down → mouse motion → R up = one Scale entry; E with RMB cancels
    exactly; focus loss cancels an armed hold; the hover is frozen while armed."""
    to_edit(window, h=6, n=3)
    x, y = find_hover(window)
    target = window.scene.target
    assert window.state.hover_target is target
    start = {v: window.scene.mesh.vertex_position(v) for v in window.scene.mesh.all_vertex_ids()}
    window.on_key_press(key.R, 0)
    assert window.state.armed
    window.on_mouse_motion(x + 200, y + 200, 200, 200)  # far away: the hover must stay frozen
    assert window.scene.target is target and window.state.dragging
    for i in range(5):
        window.on_mouse_motion(x + 200 + i, y + 200, 6, 0)
        window.on_draw()
    window.on_key_release(key.R, 0)
    assert not window.state.armed and len(window.state.session.history) == 1
    assert window.state.session.last.kind == "scale"
    assert any(window.scene.mesh.vertex_position(v) != start[v] for v in target.seeds)
    assert gl_error() == 0
    after = {v: window.scene.mesh.vertex_position(v) for v in start}
    window.on_mouse_motion(x, y, 0, 0)
    window.on_key_press(key.E, 0)
    for _ in range(4):
        window.on_mouse_motion(x, y, 8, 0)
    window.on_mouse_press(x, y, mouse.RIGHT, 0)  # RMB cancels the running rotate
    assert not window.state.armed and not window.state.dragging
    window.on_key_release(key.E, 0)
    assert {v: window.scene.mesh.vertex_position(v) for v in start} == after
    assert len(window.state.session.history) == 1
    window.on_key_press(key.W, 0)
    window.on_mouse_motion(x, y, 0, 5)
    window.on_deactivate()  # focus lost while W is held: cancelled, nothing moved
    assert not window.state.armed
    assert {v: window.scene.mesh.vertex_position(v) for v in start} == after
    window.on_draw()
    assert gl_error() == 0
