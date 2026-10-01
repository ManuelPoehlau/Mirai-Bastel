"""Knife session overlays in the real GL path (WP-06 B7; WP-KNIFE-01 S2): tool layers of
`GLPointOverlay` / `GLLineOverlay` fed by `Application` through
`Viewport.set_tool_overlay`.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_knife_overlay.py`. Skips
cleanly when no context is available (same pattern as
`tests/test_gl_point_overlay.py`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import SELECTED_COLOR, GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

SIZE = 256
BACKGROUND = (0.05, 0.05, 0.08)
TOL = 9  # see tests/test_gl_point_overlay.py (RGB565-like EGL framebuffer)
LMB = Input("mouse", "LEFT", frozenset())


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture
def app(gl_window) -> Application:
    app = Application()
    app.init_scene(
        "cube",
        store_type=GLRenderStore,
        point_overlay_type=GLPointOverlay,
        line_overlay_type=GLLineOverlay,
        face_overlay_type=GLTriangleOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(gl_window.width, gl_window.height)
    return app


def _render(gl_window, app) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    app.viewport.sync()
    gl.glClearColor(*BACKGROUND, 1.0)
    gl_window.clear()
    app.viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (gl_window.width * gl_window.height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(
        0, 0, gl_window.width, gl_window.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf
    )
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * SIZE + x) * 3
    return pixels[i], pixels[i + 1], pixels[i + 2]


def _is_selected_yellow(rgb) -> bool:
    return all(abs(c - round(e * 255)) <= TOL for c, e in zip(rgb, SELECTED_COLOR[:3]))


def _v(app, index):
    return sorted(app.scene.mesh.all_vertex_ids(), key=int)[index]


def _screen(app, point):
    return app.camera.project_to_screen(point, SIZE, SIZE)


def _lerp(a, b, t):
    return tuple(a[i] + t * (b[i] - a[i]) for i in range(3))


def _click(app, pos):
    app.pointer_motion(*pos)
    app.pointer_press(LMB, *pos)
    return app.pointer_release("LEFT", *pos)


def _near(pixels, pos, predicate) -> bool:
    x, y = int(pos[0]), int(pos[1])
    return any(
        predicate(_pixel(pixels, x + dx, y + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
    )


def test_start_point_line_preview_and_path_are_drawn_and_cleared_on_cancel(gl_window, app):
    mesh = app.scene.mesh
    idle = _render(gl_window, app)
    p4, p5, p6, p7 = (mesh.vertex_position(_v(app, i)) for i in (4, 5, 6, 7))

    app.key_press(Input("key", "c", frozenset()))
    assert app.knife_active
    assert _click(app, _screen(app, p7)) is True

    # Start vertex: selected-style point (drawn through the mesh like all points).
    app.pointer_motion(2, 2)
    started = _render(gl_window, app)
    assert _is_selected_yellow(_pixel(started, *map(int, _screen(app, p7))))

    # Hover edge 5-6: the line preview from the start crosses face 1.
    target = _lerp(p5, p6, 0.3)
    app.pointer_motion(*_screen(app, target))
    assert app.knife_render_data.line_preview is not None
    previewed = _render(gl_window, app)
    mid = _screen(app, _lerp(p7, target, 0.5))
    assert _near(previewed, mid, lambda rgb: rgb != _pixel(started, int(mid[0]), int(mid[1])))

    # Cut across face 4 → 5: the path segment is a selected-yellow line. WP-KNIFE-01 S2:
    # the mesh is cut at commit, so the placed edge point is drawn as a selected-yellow
    # point too (no split vertex to show yet).
    n_vertices = len(mesh.all_vertex_ids())
    assert _click(app, _screen(app, target)) is True
    assert len(mesh.all_vertex_ids()) == n_vertices
    app.pointer_motion(2, 2)
    cut = _render(gl_window, app)
    path_mid = _screen(app, _lerp(p7, target, 0.5))
    assert _near(cut, path_mid, _is_selected_yellow)
    assert _near(cut, _screen(app, target), _is_selected_yellow)

    # A second cut target on edge 4-5 from the new start keeps the old path.
    app.pointer_motion(*_screen(app, _lerp(p4, p5, 0.5)))
    assert _near(_render(gl_window, app), path_mid, _is_selected_yellow)

    # Esc: mesh untouched, every tool layer gone - the frame equals the idle one.
    app.key_press(Input("key", "ESCAPE", frozenset()))
    app.pointer_motion(2, 2)
    assert _render(gl_window, app) == idle
