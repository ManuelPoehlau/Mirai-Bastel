"""GLSoftShadingOverlay (2026-10-22): the face shading through the real `Application` -> `Viewport`
-> GL path.

Needs a real GL context (Xvfb or a real display) - run via
`xvfb-run -a python3 -m pytest tests/test_gl_soft_shading.py`. Skips cleanly when no context is
available (same pattern as `tests/test_gl_soft_bands.py`).
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.soft_selection import GLSoftBandOverlay, GLSoftShadingOverlay  # noqa: E402
from tests.test_gl_soft_bands import BACKGROUND, SIZE, _near, _pixel, _render  # noqa: E402,F401
from viewport.gl_point_overlay import SELECTED_COLOR  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

from tests.test_gl_soft_bands import gl_window  # noqa: E402,F401  (fixture)

ALT_SHIFT_O = Input("key", "o", frozenset({"alt", "shift"}))
ALT_O = Input("key", "o", frozenset({"alt"}))


def _app(gl_window) -> Application:
    from tests.soft_selection_fixtures import HEAD_OBJ

    app = Application()
    app.init_scene(
        "obj",
        obj_path=HEAD_OBJ,
        store_type=GLRenderStore,
        face_overlay_type=GLTriangleOverlay,
        soft_overlay_type=GLSoftBandOverlay,
        soft_shading_overlay_type=GLSoftShadingOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(gl_window.width, gl_window.height)
    return app


def test_shading_draws_in_faces_mode_and_hiding_removes_it(gl_window):
    app = _app(gl_window)
    plain = _render(gl_window, app)
    app.key_press(Input("key", "o"))
    for _ in range(4):
        app.pointer_scroll(Input("wheel", "UP", frozenset({"shift"})))
    eye = app.camera.eye()
    mesh = app.scene.mesh
    vid = min(mesh.all_vertex_ids(), key=lambda v: sum((a - b) ** 2 for a, b in zip(mesh.vertex_position(v), eye)))
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    app._soft_preview_refresh()
    assert app.key_press(ALT_SHIFT_O)
    assert app.soft_shading and app.soft_bands.count == 0
    shaded = _render(gl_window, app)
    assert shaded != plain

    assert app.key_press(ALT_O)  # hide: Soft stays on, nothing is drawn but the selection point
    assert app.soft_settings.enabled and not app.soft_shading
    hidden = _render(gl_window, app)
    assert hidden != shaded


def test_selected_face_fill_stays_above_the_shading(gl_window):
    from mirai.interaction import commands as cmd

    app = Application()
    app.init_scene(
        "cube",
        store_type=GLRenderStore,
        face_overlay_type=GLTriangleOverlay,
        soft_shading_overlay_type=GLSoftShadingOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(gl_window.width, gl_window.height)
    app.dispatch_command(cmd.SOFT_TOGGLE)
    app.dispatch_command(cmd.SOFT_VIEW_MODE_CYCLE)
    app.key_press(Input("key", "3"))
    mesh = app.scene.mesh
    eye = app.camera.eye()

    def centroid(f):
        ps = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
        return tuple(sum(c) / len(ps) for c in zip(*ps))

    face = min(mesh.all_face_ids(), key=lambda f: sum((a - b) ** 2 for a, b in zip(centroid(f), eye)))
    app.selection.set({face})
    app.viewport.on_selection_changed()
    app._soft_preview_refresh()
    weights = app.soft_shading
    assert weights
    # Baseline: the same shading with no selection (pushed straight into the sink).
    app.selection.clear()
    app.viewport.on_selection_changed()
    app._soft_shading_overlay.set_weights(weights)
    shaded_only = _render(gl_window, app)
    sx, sy = app.camera.project_to_screen(centroid(face), app.viewport_width, app.viewport_height)
    app.selection.set({face})
    app.viewport.on_selection_changed()
    app._soft_preview_refresh()
    assert app.soft_shading == weights
    pixels = _render(gl_window, app)
    before, rgb = _pixel(shaded_only, int(sx), int(sy)), _pixel(pixels, int(sx), int(sy))
    # The selected face's fill (a translucent tint since 2026-10-22) is drawn after the shading: the pixel
    # moves towards the selection yellow compared with the shading alone.
    yellowness = lambda c: (c[0] + c[1]) / 2.0 - c[2]  # noqa: E731
    assert yellowness(rgb) - yellowness(before) >= 20, (before, rgb)
