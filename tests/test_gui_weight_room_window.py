"""AD-041 slice 2: the Weight Room in the real pyglet window (xvfb) with the real `install_handlers`, the imgui layer and the
GL heatmap - the Bone panel's button opens the room, its panel draws and reaches `Application` (operation, close), a stroke
with the window's own mouse handlers paints, and the heatmap is drawn and updated by colour ranges only.

Needs pyglet, imgui-bundle and a display: `xvfb-run -a python -m pytest tests/test_gui_weight_room_window.py -q` (own
process, like `test_gui_bone_panel_window.py`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

pytest.importorskip("imgui_bundle")
pyglet = pytest.importorskip("pyglet")

try:
    import main as production  # importiert pyglet.window
except Exception as exc:  # kein Display
    pytest.skip(f"kein GL/Display: {exc}", allow_module_level=True)

from core import Rig  # noqa: E402
from pyglet.window import mouse  # noqa: E402

from tests.test_gui_imgui_window import _center, _click, _frame, run  # noqa: E402


@pytest.fixture()
def env():
    try:
        window, app, layer = run.build(argv=["cube"])
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    layer.bone_open = True
    from mirai.interaction.input import Input

    app.key_press(Input("key", "3"))  # face mode: the room opens in 1/2/3
    rig, bone = Rig().with_new_bone("Kiefer", (3.0, -3.0, 0.0), (3.0, -3.0, 0.5))  # off screen: no bone-line click
    app.scene.rig = rig
    app.select_bone(bone)
    for _ in range(3):
        run.render_frame(window)
    yield window, app, layer
    layer.close()
    window.close()


def _front_point(window, app):
    """A window point on the cube's face nearest to the camera, near its right corner (clear of the panels; the brush reaches that vertex)."""
    mesh = app.scene.mesh
    eye = app.camera.eye()
    best = None
    for f in mesh.all_face_ids():
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
        c = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        d = sum((c[i] - eye[i]) ** 2 for i in range(3))
        if best is None or d < best[0]:
            best = (d, c, pts)
    _, c, pts = best
    right = max(pts, key=lambda p: sum(app.camera.project_to_screen(p, window.width, window.height)))
    point = tuple(c[i] + 0.93 * (right[i] - c[i]) for i in range(3))
    x, y = app.camera.project_to_screen(point, window.width, window.height)
    return x, y  # (screen_to_ray and pyglet: origin bottom left)


def test_the_bone_panel_opens_the_room_its_panel_works_and_a_stroke_paints(env):
    window, app, layer = env
    _frame(window, 2)
    assert ("bone_weight_room", 0) in layer.item_rects
    _click(window, _center(layer.item_rects[("bone_weight_room", 0)]))
    assert app.weight_room_open, app.status_message
    _frame(window, 3)
    assert ("weight_op", "smooth") in layer.item_rects and ("weight_clean", 0) in layer.item_rects
    _click(window, _center(layer.item_rects[("weight_op", "smooth")]))
    assert app.weight_brush.operation == "smooth"
    _click(window, _center(layer.item_rects[("weight_op", "add")]))
    app.set_weight_brush(radius_step=13, flow=1.0)
    overlay = app._soft_shading_overlay
    _frame(window, 2)
    assert overlay.heat_full_uploads >= 1
    full, ranges = overlay.heat_full_uploads, overlay.heat_range_uploads
    history = len(app.history)
    px, py = _front_point(window, app)
    window.dispatch_event("on_mouse_motion", px, py, 0, 0)
    _frame(window, 1)
    window.dispatch_event("on_mouse_press", px, py, mouse.LEFT, 0)
    for i in range(1, 6):
        window.dispatch_event("on_mouse_drag", px - 1 * i, py, -1, 0, mouse.LEFT, 0)
        app.update_viewport(1 / 60)  # (the window's clock tick: the stroke's dabs and the heatmap's target)
        _frame(window, 1)
    window.dispatch_event("on_mouse_release", px - 5, py, mouse.LEFT, 0)
    _frame(window, 2)
    assert len(app.history) == history + 1, app.status_message
    assert app.weight_heat.shares.max() > 0.0
    assert overlay.heat_range_uploads > ranges and overlay.heat_full_uploads == full + 1  # (+1: the layer appeared)
