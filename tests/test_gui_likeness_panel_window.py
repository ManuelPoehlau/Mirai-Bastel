"""AD-042 §8.2: the panel „Kamera“ in the real pyglet window (xvfb) with the imgui layer - „Neu aus Ansicht“,
„Durchschauen“, a focal button and „Kamera fixieren“ reach `Application`; the frame draws the gate and a photo; the
panel holds no document state.

Needs pyglet, imgui-bundle and a display: `xvfb-run -a python -m pytest tests/test_gui_likeness_panel_window.py -q`
(own process, like `test_gui_imgui_window.py`)."""

from __future__ import annotations

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

pytest.importorskip("imgui_bundle")
pyglet = pytest.importorskip("pyglet")

try:
    import main as production  # importiert pyglet.window
except Exception as exc:  # kein Display
    pytest.skip(f"kein GL/Display: {exc}", allow_module_level=True)

from tests.test_gui_imgui_window import _center, _click, _frame, run  # noqa: E402


@pytest.fixture()
def env():
    try:
        window, app, layer = run.build(argv=["cube"])
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    layer.likeness_open = True
    for _ in range(3):
        run.render_frame(window)
    yield window, app, layer
    layer.close()
    window.close()


def test_the_panel_creates_looks_through_and_fixes_a_camera(env, tmp_path):
    from mirai.iris_import import encode_png

    window, app, layer = env
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("likeness_new", 0)]))
    assert app.likeness.cameras and app.likeness.cameras[0].name == "Kamera 1", app.status_message
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("likeness_look", 0)]))
    assert app.camera_view_open, app.status_message
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("likeness_focal", 85)]))
    assert app.likeness.cameras[0].lens.focal_mm == 85.0 and app.view_text.endswith("85 mm")
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("likeness_fix", 0)]))
    assert app.likeness.cameras[0].fixed
    _click(window, _center(layer.item_rects[("likeness_more", 0)]))
    path = tmp_path / "p.png"
    path.write_bytes(encode_png(np.full((60, 80, 4), 180, np.uint8)))
    assert app.load_likeness_photo(0, path)
    for _ in range(3):  # the window's tick (scheduled on the clock in `main`) - here by hand
        app.update_viewport(1 / 60)
    _frame(window, 3)  # frames with the photo, the gate and „Mehr“ open
    assert app.likeness.cameras[0].photo is not None and app.viewport.backdrop.image is not None
    assert app.viewport.backdrop_pass.uploads == 1
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("likeness_look", 0)]))  # „Verlassen“
    assert not app.camera_view_open and app.viewport.backdrop is None
