"""Stage A entry point (`src/main.py`) — smoke test through the real
`Application` -> `Viewport` -> `GLRenderStore` path.

Not a test of `src/main.py`'s `main()` itself (that opens an event-loop
window and never returns) — instead builds `Application`, calls
`init_scene(store_type=GLRenderStore)` exactly as `src/main.py` does, and
confirms `Viewport.render()` (the facade fix, AD-018 §5 Stage-A-Handoff
§4.3) now produces a non-background framebuffer through the real
Production path, not just through `RenderMesh` directly (that path is
already covered by `tests/test_gl_render_store.py`).

Needs a real GL context (Xvfb or a real display), same as
`tests/test_gl_render_store.py` — skips cleanly when unavailable.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=128, height=128, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _read_pixels_rgb(window):
    from pyglet import gl

    width, height = window.width, window.height
    buf = (gl.GLubyte * (width * height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    return bytes(buf)


def test_application_viewport_render_draws_through_real_path(gl_window):
    app = Application()
    app.init_scene(store_type=GLRenderStore)
    app.viewport.on_camera_changed(aspect=gl_window.width / gl_window.height)
    app.viewport.sync()

    from pyglet import gl

    gl_window.switch_to()
    gl.glClearColor(0.05, 0.05, 0.08, 1.0)
    gl_window.clear()
    app.viewport.render()
    gl.glFinish()

    pixels = _read_pixels_rgb(gl_window)
    background = bytes([12, 12, 20]) * (len(pixels) // 3)
    assert pixels != background, "framebuffer is empty - no silhouette rendered"


def test_application_viewport_render_camera_invariant_through_orbit(gl_window):
    # V02 invariant (geometry_uploads stays 0 while orbiting), demonstrated
    # through the real Application/Viewport facade, not RenderMesh directly.
    app = Application()
    app.init_scene(store_type=GLRenderStore)
    app.viewport.on_camera_changed(aspect=gl_window.width / gl_window.height)
    app.viewport.sync()

    before = app.viewport.resource_ids()

    for _ in range(20):
        app.camera.orbit(0.05, 0.01)
        app.viewport.on_camera_changed(aspect=gl_window.width / gl_window.height)
        app.viewport.sync()
        app.viewport.render()

    after = app.viewport.resource_ids()
    assert after == before
    assert app.viewport.benchmark_counters.get("geometry_uploads", 0) == 0


if __name__ == "__main__":
    unittest.main()
