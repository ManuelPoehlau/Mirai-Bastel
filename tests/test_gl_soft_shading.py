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


def test_the_weight_rooms_heatmap_draws_grey_at_zero_and_colours_a_share(gl_window):
    """AD-041 §5 (slice 2): the room's heatmap through the real GL path - every face drawn (grey where the bone has no
    share), opaque enough to read; a weight written shows in colour, uploaded as a colour range (no full upload)."""
    import numpy as np

    from core import Rig
    from mirai.interaction import commands as cmd
    from mirai.soft_selection.shading import WEIGHT_ALPHA, WEIGHT_ZERO_RGB
    from mirai.skin_weights import set_bone_weight
    from mirai.skinning import skin_layer
    from core import PointLayerInfo
    from core.mesh import LayerKind

    app = Application()
    app.init_scene("cube", store_type=GLRenderStore, soft_shading_overlay_type=GLSoftShadingOverlay)
    app.frame_scene()
    app.set_viewport_size(gl_window.width, gl_window.height)
    app.dispatch_command(cmd.SET_FACE_MODE)
    rig, bone = Rig().with_new_bone("Kiefer", (0.0, 0.0, 0.0), (0.0, 0.0, 0.3))
    app.scene.rig = rig
    app.select_bone(bone)
    plain = _render(gl_window, app)
    assert app.open_weight_room(), app.status_message
    overlay = app._soft_shading_overlay
    grey = _render(gl_window, app)
    centre = _pixel(grey, SIZE // 2, SIZE // 2)
    expected = [round((c * WEIGHT_ALPHA + 0.0) * 255) for c in WEIGHT_ZERO_RGB]
    assert grey != plain
    assert all(abs(a - b) <= 40 for a, b in zip(centre, expected)), centre  # mostly the grey over the lit cube
    full = overlay.heat_full_uploads
    mesh = app.scene.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    _render(gl_window, app)  # (the new layer: one whole recompute)
    full = overlay.heat_full_uploads
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, v, set_bone_weight((), bone, 1.0, lambda b: None))
    coloured = _render(gl_window, app)
    assert overlay.heat_full_uploads == full and overlay.heat_range_uploads >= 1
    r, g, b = _pixel(coloured, SIZE // 2, SIZE // 2)
    assert r > g and r > b and r > 120  # share 1: red
    assert skin_layer(mesh) == lid and np.all(app.weight_heat.shares == 1.0)
    assert app.close_weight_room()
    assert _render(gl_window, app) == plain  # the heatmap is gone (its buffers freed in the draw)
