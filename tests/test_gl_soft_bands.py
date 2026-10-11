"""GLSoftBandOverlay (WP-SOFT-01 S2b, AD-020 §5): the band layers through the real
`Application` -> `Viewport` -> GL path.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_soft_bands.py`. Skips cleanly when no context is
available (same pattern as `tests/test_gl_point_overlay.py`).
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from mirai.soft_selection import BAND_LAYERS, GLSoftBandOverlay, SoftBands  # noqa: E402
from viewport.gl_point_overlay import SELECTED_COLOR  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402

SIZE = 128
BACKGROUND = (0.05, 0.05, 0.08)
TOL = 9  # per channel; see tests/test_gl_point_overlay.py


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _app(gl_window, head: bool = False) -> Application:
    app = Application()
    if head:
        from tests.soft_selection_fixtures import HEAD_OBJ

        app.init_scene(
            "obj", obj_path=HEAD_OBJ, store_type=GLRenderStore, soft_overlay_type=GLSoftBandOverlay
        )
    else:
        app.init_scene("cube", store_type=GLRenderStore, soft_overlay_type=GLSoftBandOverlay)
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
    gl.glReadPixels(0, 0, gl_window.width, gl_window.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * SIZE + x) * 3
    return pixels[i], pixels[i + 1], pixels[i + 2]


def _near(rgb, color) -> bool:
    """`rgb` is `color` blended over the background by its alpha (blending is on)."""
    alpha = color[3]
    expected = [e * alpha + b * (1.0 - alpha) for e, b in zip(color[:3], BACKGROUND)]
    return all(abs(c - round(e * 255)) <= TOL for c, e in zip(rgb, expected))


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(
        app.scene.mesh.vertex_position(vid), app.viewport_width, app.viewport_height
    )


def _by_eye_distance(app):
    eye = app.camera.eye()
    mesh = app.scene.mesh
    return sorted(mesh.all_vertex_ids(), key=lambda v: math.dist(mesh.vertex_position(v), eye))


def test_every_band_layer_draws_in_its_own_colour(gl_window):
    app = _app(gl_window)
    overlay = app._soft_overlay
    vids = _by_eye_distance(app)[:4]
    # One vertex per band (weights 0.9 / 0.6 / 0.4 / 0.1), pushed the way Application does.
    overlay.set_bands(SoftBands.from_weights(dict(zip(vids, (0.9, 0.6, 0.4, 0.1)))))
    pixels = _render(gl_window, app)

    seen = []
    for vid, layer in zip(vids, BAND_LAYERS):
        color = GLSoftBandOverlay.LAYER_STYLES[layer][0]
        sx, sy = _screen(app, vid)
        rgb = _pixel(pixels, int(sx), int(sy))
        assert _near(rgb, color), (layer, rgb, color)
        seen.append(rgb)
    assert len(set(seen)) == 4
    assert not any(_near(rgb, SELECTED_COLOR) for rgb in seen)


def test_empty_bands_draw_nothing(gl_window):
    app = _app(gl_window)
    before = _render(gl_window, app)
    vids = _by_eye_distance(app)[:2]
    app._soft_overlay.set_bands(SoftBands.from_weights({vids[0]: 0.9, vids[1]: 0.3}))
    shown = _render(gl_window, app)
    assert shown != before
    app._soft_overlay.set_bands(SoftBands.from_weights({}))
    assert _render(gl_window, app) == before


def test_application_soft_on_draws_bands_and_off_removes_them(gl_window):
    from mirai.interaction.input import Input

    app = _app(gl_window, head=True)
    vid = _by_eye_distance(app)[0]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    plain = _render(gl_window, app)

    app.key_press(Input("key", "o"))
    for _ in range(4):  # 15 % -> 50 %: a patch of neighbours
        app.pointer_scroll(Input("wheel", "UP", frozenset({"shift"})))
    with_bands = _render(gl_window, app)
    assert app.soft_bands.count > 0
    assert with_bands != plain

    app.key_press(Input("key", "o"))
    assert _render(gl_window, app) == plain
