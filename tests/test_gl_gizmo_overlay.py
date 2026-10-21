"""The transform gizmo in the real GL path (2026-10-21): `viewport.gl_gizmo_overlay.draw_gizmo` draws the
`Application.gizmo_items()` on top of the mesh without a GL error, in the axis colours.

Needs a real GL context (Xvfb or a real display): `xvfb-run -a python3 -m pytest tests/test_gl_gizmo_overlay.py`.
Skips cleanly when no context is available (same pattern as `tests/test_gl_line_overlay.py`)."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.viewport import gizmo  # noqa: E402
from viewport.gl_gizmo_overlay import draw_gizmo  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402

SIZE = 160
BACKGROUND = (0.05, 0.05, 0.08)
TOL = 9


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _render(gl_window, app, *, gizmo_on: bool) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    app.viewport.sync()
    gl.glClearColor(*BACKGROUND, 1.0)
    gl_window.clear()
    app.viewport.render()
    items = app.gizmo_items() if gizmo_on else []
    draw_gizmo(items, app.viewport.overlay_camera_uniforms())
    gl.glFinish()
    buf = (gl.GLubyte * (gl_window.width * gl_window.height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, gl_window.width, gl_window.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _count(pixels: bytes, color) -> int:
    target = [round(c * 255) for c in color[:3]]
    return sum(
        1 for i in range(0, len(pixels), 3)
        if all(abs(pixels[i + k] - target[k]) <= TOL for k in range(3))
    )


@pytest.mark.parametrize("tool_key", [None, "e", "r"])
def test_the_gizmo_is_drawn_in_the_axis_colours_on_top_of_the_mesh(gl_window, tool_key):
    app = Application()
    app.init_scene("cube", store_type=GLRenderStore, point_overlay_type=GLPointOverlay,
                   line_overlay_type=GLLineOverlay)
    app.frame_scene()
    app.set_viewport_size(gl_window.width, gl_window.height)
    app.gizmo_enabled = True
    app.key_press(Input("key", "1", frozenset()))
    app.selection.set({next(iter(app.scene.mesh.all_vertex_ids()))})
    app.viewport.on_selection_changed()
    if tool_key is not None:
        app.key_press(Input("key", tool_key, frozenset()))
        app.key_release(Input("key", tool_key, frozenset()))

    without = _render(gl_window, app, gizmo_on=False)
    drawn = _render(gl_window, app, gizmo_on=True)
    assert _count(without, gizmo.COLOR_X) == 0
    assert _count(drawn, gizmo.COLOR_X) > 0
    assert _count(drawn, gizmo.COLOR_Z) > 0 or _count(drawn, gizmo.COLOR_Y) > 0
