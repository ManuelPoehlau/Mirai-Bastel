"""The LookDev room in the real window (AD-038 §7, §9): the SPACE row's call opens the room, the programs compile
behind the status line before the first LookDev frame, the panel draws, frames leave the GL state as found, closing
restores the Worklight. A separate file: `tests/test_gui_imgui_window.py` stays unchanged (AD-038 §11).

Only with pyglet, imgui-bundle and a display, in its own process:
`xvfb-run -a python -m pytest tests/test_gui_lookdev_window.py -q`."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

pytest.importorskip("imgui_bundle")
pyglet = pytest.importorskip("pyglet")

try:
    from tests.test_gui_imgui_window import _center, run  # noqa: E402
except Exception as exc:  # no display
    pytest.skip(f"kein GL/Display: {exc}", allow_module_level=True)

from gui import lookdev_model as lm  # noqa: E402
from gui.imgui_layer import snapshot_gl_state  # noqa: E402


def _tick(app, window, n):
    for _ in range(n):
        app.update_viewport(0.0)
        run.render_frame(window)


def test_lookdev_room_in_the_window():
    try:
        window, app, layer = run.build(argv=["cube"])
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    try:
        eye = app.add_eye()
        app.select_objects([])
        _tick(app, window, 2)
        rects = len(layer.panel_rects)
        assert lm.toggle(app) and app.lookdev_open
        assert app.status_message == "LookDev: Shader werden vorbereitet …"
        assert app.viewport.shading == "worklight"
        _tick(app, window, 1)  # the frame that shows the status line
        assert app.viewport.shading == "worklight" and app.lookdev.preparing
        _tick(app, window, 1)  # compiled, then the first LookDev frame
        assert app.viewport.shading == "lookdev" and "Shader in" in app.status_message, app.status_message
        passes = app.viewport.lookdev_pass
        compiled = (len(passes.programs), len(app.viewport.eye_pass.programs))
        assert compiled[0] >= 1 and any(k[7] for k in app.viewport.eye_pass.programs)
        _tick(app, window, 2)
        assert (len(passes.programs), len(app.viewport.eye_pass.programs)) == compiled  # nothing compiled in a frame
        assert passes.draws > 0 and len(layer.panel_rects) == rects + 1
        px, py = _center(layer.panel_rects[-1])
        assert layer._over_panel(px, window.height - py)
        before = snapshot_gl_state()
        _tick(app, window, 1)
        assert snapshot_gl_state() == before
        assert app.set_lookdev_studio_preset("Soft Studio") and app.set_lookdev_material("Creature Skin")
        _tick(app, window, 2)
        before = snapshot_gl_state()
        _tick(app, window, 1)
        assert snapshot_gl_state() == before
        assert lm.toggle(app) and not app.lookdev_open and app.viewport.shading == "worklight"
        _tick(app, window, 2)
        assert len(layer.panel_rects) == rects
        del eye
    finally:
        layer.close()
        window.close()
