"""AD-042 M2 (§18) in the real GL path: the photo in front (over the model, under the wire), the wipe, the photo fit
in pixels (mirror and half-turn round trips through the capture), GL hygiene of the new draws, the capture default.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_likeness_compare.py -q`."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from gui.imgui_layer import snapshot_gl_state  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402
from tests.test_gl_likeness_backdrop import (  # noqa: E402
    _app, _camera, _crop, _frame, _gate_px, _load, _texture_state, gl_window,  # noqa: F401 (fixture)
)
from viewport.backdrop import Backdrop, gate_corners  # noqa: E402

COLOUR = np.array([30, 200, 120, 255], np.uint8)


def _flat(h: int = 48, w: int = 64) -> np.ndarray:
    return np.tile(COLOUR, (h, w, 1))


def _inner(rect, margin: int = 3):
    x, y, w, h = rect
    return (x + margin, y + margin, w - 2 * margin, h - 2 * margin)


def test_the_front_photo_covers_the_model_and_the_wire_stays_on_top(gl_window, tmp_path):
    app = _app(gl_window, 640, 480, wire=True)
    app.dispatch_command(cmd.TOGGLE_WIREFRAME_OVERLAY)
    _camera(app)
    _load(app, _flat(), tmp_path)
    behind = _frame(gl_window, app)
    inner = _inner(_gate_px(app))
    centre = (240, 320)  # inside the model
    assert np.abs(behind[centre][:3].astype(int) - COLOUR[:3]).max() > 10  # behind: the model covers the photo
    assert app.set_likeness_view(compare="front")
    front = _frame(gl_window, app)
    region = _crop(front, inner)[..., :3].astype(int)
    photo_px = np.all(np.abs(region - COLOUR[:3]) <= 1, axis=-1)
    assert photo_px.mean() > 0.9  # the photo over the whole gate
    # the wire pixels of the behind frame are drawn the same in front: the front photo lies under the wire
    wire_behind = np.any(np.abs(_crop(behind, inner)[..., :3].astype(int) - COLOUR[:3]) > 1, axis=-1) & ~photo_px
    assert wire_behind.sum() > 50
    assert np.array_equal(_crop(front, inner)[wire_behind], _crop(behind, inner)[wire_behind])
    assert app.set_likeness_view(photo_opacity=0.5)
    half = _frame(gl_window, app)
    plain_centre = behind[centre][:3].astype(float)
    mix = 0.5 * COLOUR[:3] + 0.5 * plain_centre
    assert np.abs(half[centre][:3].astype(float) - mix).max() <= 1.0


def test_the_wipe_shows_the_photo_left_and_the_model_right(gl_window, tmp_path):
    app = _app(gl_window, 640, 480)
    _camera(app)
    model_only = _frame(gl_window, app)  # the camera view without a photo
    _load(app, _flat(), tmp_path)
    assert app.set_likeness_view(compare="wipe", wipe=0.5, photo_opacity=0.2)  # the wipe draws at full strength
    wiped = _frame(gl_window, app)
    x, y, w, h = _inner(_gate_px(app))
    line = 320  # the wipe line at the gate's middle
    left = wiped[y:y + h, x:line - 2, :3].astype(int)
    assert np.all(np.abs(left - COLOUR[:3]) <= 1)
    assert np.array_equal(wiped[y:y + h, line + 2:x + w], model_only[y:y + h, line + 2:x + w])
    column = wiped[y + 5:y + h - 5, line - 1:line + 2, :3].astype(int)
    assert np.any(np.all(np.abs(column - 209) <= 2, axis=-1))  # the 1 px wipe line (the gate line colour)


@pytest.mark.parametrize("kind", ["mirror", "half_turn"])
def test_the_fit_round_trips_through_the_photo(gl_window, tmp_path, kind):
    """G1 with a fit: the capture turned into a photo by the inverse operation, shown with the fit - the same picture."""
    app = _app(gl_window, 640, 480)
    _camera(app)
    rect = _gate_px(app)
    shots = []
    _frame(gl_window, app, capture=shots.append)
    photo = _crop(shots[0], rect)
    photo[..., 3] = 255
    stored = photo[:, ::-1] if kind == "mirror" else photo[::-1, ::-1]
    _load(app, np.ascontiguousarray(stored), tmp_path)
    fit = {"mirror": True} if kind == "mirror" else {"rotation_deg": 180.0}
    assert app.set_likeness_photo_fit(0, **fit)
    app.viewport.show_faces = False
    again = []
    _frame(gl_window, app, capture=again.append, backdrop=True)
    diff = np.abs(_crop(again[0], rect)[..., :3].astype(int) - photo[..., :3].astype(int)).mean()
    assert diff < 1.0, diff


def test_the_new_draws_restore_the_gl_state(gl_window):
    from pyglet import gl

    from viewport.backdrop_pass import BackdropPass

    gl_window.switch_to()
    gate = (0.8, 0.7)
    backdrop = Backdrop(gate=gate, image=np.full((30, 40, 4), 200, np.uint8), image_serial=1,
                        corners=gate_corners(gate), opacity=0.5, placement="front", wipe=0.1)
    passes = BackdropPass()
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
    before, textures = snapshot_gl_state(), _texture_state()
    assert passes.draw_image(backdrop)
    passes.draw_gate(backdrop)
    assert snapshot_gl_state() == before and _texture_state() == textures
    assert gl.glGetError() == gl.GL_NO_ERROR
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
    gl.glDisable(gl.GL_CULL_FACE)
    passes.release()


@pytest.mark.parametrize("compare", ["front", "wipe"])
def test_the_app_frame_state_and_the_capture_with_a_front_photo(gl_window, tmp_path, compare):
    app = _app(gl_window, 640, 480)
    _frame(gl_window, app)
    free = snapshot_gl_state(), _texture_state()
    _camera(app)
    without = []
    _frame(gl_window, app, capture=without.append)
    _load(app, _flat(), tmp_path)
    assert app.set_likeness_view(compare=compare)
    shot = []
    _frame(gl_window, app, capture=shot.append)
    assert np.array_equal(shot[0], without[0])  # „Bild speichern“ never shows the photo
    assert (snapshot_gl_state(), _texture_state()) == free
    assert app.set_likeness_flip(True)
    flipped = _frame(gl_window, app)
    inner = _inner(_gate_px(app))
    assert np.all(np.abs(_crop(flipped, inner)[..., :3].astype(int) - COLOUR[:3]) <= 1)  # only the photo
