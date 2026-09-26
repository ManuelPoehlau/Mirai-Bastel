"""GLPointOverlay (WP-06 B2b): round vertex points through the real
`Application` -> `Viewport` -> GL path.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_point_overlay.py`. Skips
cleanly when no context is available (same pattern as
`tests/test_gl_render_store.py`).
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from viewport.gl_point_overlay import (  # noqa: E402
    HOVER_COLOR,
    SELECTED_COLOR,
    GLPointOverlay,
)
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.overlay import HOVER_LAYER, SELECTED_LAYER  # noqa: E402

SIZE = 128
BACKGROUND = (0.05, 0.05, 0.08)
# Per-channel tolerance: when `tests/test_pyglet_input.py` has switched pyglet
# to headless (EGL) earlier in the run, the framebuffer is RGB565-like
# (5-bit red/blue steps of ~8).
TOL = 9


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _app(gl_window) -> Application:
    app = Application()
    app.init_scene("cube", store_type=GLRenderStore, point_overlay_type=GLPointOverlay)
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


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(
        app.scene.mesh.vertex_position(vid), app.viewport_width, app.viewport_height
    )


def _by_eye_distance(app):
    """Vertex ids sorted from nearest to farthest from the camera eye."""
    eye = app.camera.eye()
    mesh = app.scene.mesh
    return sorted(
        mesh.all_vertex_ids(),
        key=lambda vid: math.dist(mesh.vertex_position(vid), eye),
    )


def _is_selected_yellow(rgb) -> bool:
    r, g, b = rgb
    er, eg, eb = (round(c * 255) for c in SELECTED_COLOR[:3])
    return abs(r - er) <= TOL and abs(g - eg) <= TOL and abs(b - eb) <= TOL


def _changed_pixels(a: bytes, b: bytes) -> list[tuple[int, int]]:
    out = []
    for i in range(0, len(a), 3):
        if a[i:i + 3] != b[i:i + 3]:
            p = i // 3
            out.append((p % SIZE, p // SIZE))
    return out


def test_selected_vertex_is_a_round_yellow_point_and_mesh_is_not_tinted(gl_window):
    app = _app(gl_window)
    before = _render(gl_window, app)
    vlist_before = app.viewport.render_mesh.store.vertex_list()

    # Nearest vertex: its adjacent faces are visible, so a face tint would show.
    vid = _by_eye_distance(app)[0]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    after = _render(gl_window, app)

    # Base-mesh VertexList untouched by the selection change.
    assert app.viewport.render_mesh.store.vertex_list() is vlist_before

    sx, sy = _screen(app, vid)
    assert _is_selected_yellow(_pixel(after, int(sx), int(sy)))

    # Every changed pixel lies inside the 8 px point: the faces are not tinted.
    changed = _changed_pixels(before, after)
    assert changed
    assert all(math.hypot(x + 0.5 - sx, y + 0.5 - sy) <= 4.0 + 1.0 for x, y in changed)

    # Round, not square: fewer covered pixels than the 8x8 square, and the
    # square's corners stay untouched.
    assert len(changed) < 64
    for cx, cy in ((-3.5, -3.5), (3.5, -3.5), (-3.5, 3.5), (3.5, 3.5)):
        x, y = int(math.floor(sx + cx)), int(math.floor(sy + cy))
        assert _pixel(after, x, y) == _pixel(before, x, y)


def test_hover_point_is_translucent_pale_yellow_and_larger(gl_window):
    app = _app(gl_window)
    before = _render(gl_window, app)

    vid = _by_eye_distance(app)[0]
    app.selection.hovered = vid
    app.viewport.on_selection_changed()
    hovered = _render(gl_window, app)

    sx, sy = _screen(app, vid)
    under = _pixel(before, int(sx), int(sy))
    r, g, b = _pixel(hovered, int(sx), int(sy))
    alpha = HOVER_COLOR[3]
    expected = [
        c * 255 * alpha + u * (1.0 - alpha) for c, u in zip(HOVER_COLOR[:3], under)
    ]
    assert all(abs(got - exp) <= TOL for got, exp in zip((r, g, b), expected))

    hover_area = len(_changed_pixels(before, hovered))

    app.selection.hovered = None
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    selected_area = len(_changed_pixels(before, _render(gl_window, app)))
    assert hover_area > selected_area


def test_points_stay_visible_through_the_mesh(gl_window):
    app = _app(gl_window)
    hidden = _by_eye_distance(app)[-1]
    app.selection.set({hidden})
    app.viewport.on_selection_changed()
    pixels = _render(gl_window, app)
    sx, sy = _screen(app, hidden)
    assert _is_selected_yellow(_pixel(pixels, int(sx), int(sy)))


def test_layer_vertex_lists_rebuild_only_on_change(gl_window):
    app = _app(gl_window)
    overlay = app.viewport.point_overlay
    _render(gl_window, app)
    rebuilds = overlay.rebuilds

    for _ in range(3):
        app.camera.orbit(0.1, 0.0)
        app.viewport.on_camera_changed()
        _render(gl_window, app)
    assert overlay.rebuilds == rebuilds

    vid = app.scene.mesh.all_vertex_ids()[1]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    _render(gl_window, app)
    assert overlay.rebuilds == rebuilds + 1  # only the "selected" layer
    assert overlay.vertex_list(SELECTED_LAYER) is not None
    assert overlay.vertex_list(HOVER_LAYER) is None
