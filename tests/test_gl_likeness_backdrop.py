"""The likeness camera's backdrop in the real GL path (AD-042 §7, §10.3): G1 round trip, G2 pinhole in pixels, G3 GL
hygiene, G4 nothing left behind, G5 the capture default, G6 the LookDev slot, G7 the passepartout slot.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_likeness_backdrop.py -q`."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from gui.imgui_layer import snapshot_gl_state  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402
from mirai.iris_import import encode_png  # noqa: E402
from mirai.viewport import lens as L  # noqa: E402
from viewport.backdrop import Backdrop, gate_corners  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402

SIZE = 640
CLEAR = (0.25, 0.1, 0.4)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _app(gl_window, w: int, h: int, wire: bool = False) -> Application:
    gl_window.switch_to()
    app = Application()
    app.init_scene("cube", store_type=GLRenderStore, line_overlay_type=GLLineOverlay if wire else None)
    app.set_viewport_size(w, h)
    app.frame_scene()
    return app


def _frame(gl_window, app, capture=None, backdrop: bool = False) -> np.ndarray:
    """One frame into a (w, h) viewport; returns the read-back RGBA (top row first); `capture` gets the capture."""
    from pyglet import gl

    from viewport.lookdev_pass import read_back_buffer

    gl_window.switch_to()
    gl.glViewport(0, 0, app.viewport_width, app.viewport_height)
    gl.glClearColor(*CLEAR, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    if capture is not None:
        app.viewport.request_capture(capture, backdrop=backdrop)
    app.update_viewport(0.0)
    app.viewport.render()
    gl.glFinish()
    assert gl.glGetError() == gl.GL_NO_ERROR
    return read_back_buffer()


def _gate_px(app) -> tuple[int, int, int, int]:
    """(x0, y0, w, h) of the gate in pixels, y from the top."""
    half_w, half_h = app.viewport.backdrop.gate
    W, H = app.viewport_width, app.viewport_height
    gw, gh = round(half_w * W), round(half_h * H)
    return (W - gw) // 2, (H - gh) // 2, gw, gh


def _crop(rgba, rect) -> np.ndarray:
    x, y, w, h = rect
    return rgba[y:y + h, x:x + w].copy()


def _camera(app, overscan: float = 1.25) -> None:
    assert app.new_likeness_camera()
    assert app.set_likeness_lens(0, sensor="custom", sensor_w_mm=36.0, sensor_h_mm=27.0, fit="auto")
    app.set_likeness_view(overscan=overscan)
    assert app.look_through(0), app.status_message


def _load(app, rgba, tmp_path) -> None:
    path = tmp_path / "photo.png"
    path.write_bytes(encode_png(rgba))
    assert app.load_likeness_photo(0, path)
    for _ in range(4):
        app.update_viewport(0.0)
    assert app.likeness.cameras[0].photo is not None, app.status_message


# -- G1: render -> capture -> photo -> capture --------------------------------------------------------------------

@pytest.mark.parametrize("size, rect", [((640, 480), (64, 48, 512, 384)), ((480, 640), (48, 176, 384, 288))])
def test_round_trip_through_the_photo(gl_window, tmp_path, size, rect):
    app = _app(gl_window, *size)
    _camera(app)
    assert _gate_px(app) == rect
    shots = []
    _frame(gl_window, app, capture=shots.append)
    photo = _crop(shots[0], rect)
    photo[..., 3] = 255
    assert len(np.unique(photo.reshape(-1, 4), axis=0)) > 2  # the cube on the clear colour
    _load(app, photo, tmp_path)
    assert app.likeness.cameras[0].photo.size == (rect[2], rect[3])
    app.viewport.show_faces = False
    again = []
    _frame(gl_window, app, capture=again.append, backdrop=True)
    diff = np.abs(_crop(again[0], rect)[..., :3].astype(int) - photo[..., :3].astype(int)).mean()
    assert diff < 1.0, diff  # PROVISIONAL < 1/255 mean; texel centres land on pixel centres


# -- G2: the pinhole in pixels ---------------------------------------------------------------------------------------

def test_the_gate_shows_what_the_lens_records(gl_window):
    app = _app(gl_window, 640, 480)
    cam = app.camera
    cam.set_view(0.0, 0.0)  # Front: the cube's front face (edge 2) faces the camera
    cam.target, cam.distance = (0.0, 0.0, 0.0), 9.0
    _camera(app, overscan=1.25)
    assert app.set_likeness_lens(0, focal_mm=85.0)
    rgba = _frame(gl_window, app)
    clear = np.round(np.array(CLEAR) * 255).astype(int)
    _x, y0, _w, gate_h = _gate_px(app)
    column = rgba[y0 + 2:y0 + gate_h - 2, 320, :3].astype(int)  # inside the gate (outside it the passepartout darkens)
    covered = np.any(np.abs(column - clear) > 2, axis=1).sum()
    record = app.likeness.cameras[0]
    _W, H = L.effective_sensor(36.0, 27.0, "auto", 4 / 3)
    expected = gate_h * 2.0 * record.lens.focal_mm / ((9.0 - 1.0) * H)
    assert abs(covered - expected) <= 1.0, (covered, expected)


# -- G3: GL hygiene --------------------------------------------------------------------------------------------------

def _texture_state() -> tuple:
    from pyglet import gl

    def geti(name):
        value = gl.GLint()
        gl.glGetIntegerv(name, value)
        return value.value

    active = geti(gl.GL_ACTIVE_TEXTURE)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    state = (geti(gl.GL_TEXTURE_BINDING_2D), geti(gl.GL_SAMPLER_BINDING), geti(gl.GL_UNPACK_ALIGNMENT),
             geti(gl.GL_BLEND_SRC_ALPHA), geti(gl.GL_BLEND_DST_ALPHA))
    gl.glActiveTexture(active)
    return state + (active,)


def test_the_pass_restores_the_gl_state_it_sets(gl_window):
    import ctypes

    from pyglet import gl

    from viewport.backdrop_pass import BackdropPass

    gl_window.switch_to()
    image = np.full((30, 40, 4), 200, np.uint8)
    gate = (0.8, 0.7)
    backdrop = Backdrop(gate=gate, image=image, image_serial=1, corners=gate_corners(gate), opacity=0.5)
    passes = BackdropPass()
    tex = gl.GLuint()
    gl.glGenTextures(1, ctypes.byref(tex))
    sampler = gl.GLuint()
    gl.glGenSamplers(1, ctypes.byref(sampler))
    for mode in (gl.GL_FILL, gl.GL_LINE):  # wireframe display mode too
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex.value)
        gl.glBindSampler(0, sampler.value)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glPolygonMode(gl.GL_FRONT_AND_BACK, mode)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
        before, textures = snapshot_gl_state(), _texture_state()
        assert passes.draw_image(backdrop)
        assert snapshot_gl_state() == before and _texture_state() == textures
        passes.draw_gate(backdrop)
        assert snapshot_gl_state() == before and _texture_state() == textures
        assert gl.glGetError() == gl.GL_NO_ERROR
    assert passes.uploads == 1  # the same serial never re-uploads
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindSampler(0, 0)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    gl.glDeleteTextures(1, ctypes.byref(tex))
    gl.glDeleteSamplers(1, ctypes.byref(sampler))
    passes.release()


def test_the_app_frame_leaves_the_same_gl_state_with_and_without_the_backdrop(gl_window, tmp_path):
    """The whole frame (meshes, LookDev, overlays) ends in the same GL state as without a camera view."""
    app = _app(gl_window, 640, 480)
    for lookdev in (False, True):
        if lookdev:
            app.open_lookdev()
            for _ in range(app.LOOKDEV_PREPARE_FRAMES + 1):
                _frame(gl_window, app)
            assert app.viewport.shading == "lookdev"
        _frame(gl_window, app)
        free = snapshot_gl_state(), _texture_state()
        if not app.likeness.cameras:
            _camera(app)
            _load(app, np.full((48, 64, 4), 90, np.uint8), tmp_path)
        else:
            assert app.look_through(0)
        _frame(gl_window, app)
        assert (snapshot_gl_state(), _texture_state()) == free
        app.leave_camera_view()


# -- G4 / G5: nothing left behind, the capture default --------------------------------------------------------------

def test_a_frame_after_leaving_equals_a_frame_that_never_had_a_backdrop(gl_window, tmp_path):
    app = _app(gl_window, 640, 480)
    never = _frame(gl_window, app)
    _camera(app)
    _load(app, np.full((48, 64, 4), 255, np.uint8), tmp_path)
    shown = _frame(gl_window, app)
    assert not np.array_equal(shown, never)
    assert app.viewport.backdrop_pass.has_texture
    app.leave_camera_view()
    assert not app.viewport.backdrop_pass.has_texture  # freed on leaving
    assert np.array_equal(_frame(gl_window, app), never)


def test_the_default_capture_never_shows_the_photo(gl_window, tmp_path):
    app = _app(gl_window, 640, 480)
    _camera(app)
    without = []
    _frame(gl_window, app, capture=without.append)
    _load(app, np.full((48, 64, 4), 255, np.uint8), tmp_path)
    shot = []
    _frame(gl_window, app, capture=shot.append)
    assert np.array_equal(shot[0], without[0])


# -- G6: the LookDev slot --------------------------------------------------------------------------------------------

def test_the_photo_lies_on_the_studio_background(gl_window, tmp_path):
    app = _app(gl_window, 640, 480)
    _camera(app)
    app.open_lookdev()
    for _ in range(app.LOOKDEV_PREPARE_FRAMES + 1):
        _frame(gl_window, app)
    assert app.viewport.shading == "lookdev"
    plain = _frame(gl_window, app)
    colour = np.array([30, 200, 120, 255], np.uint8)
    _load(app, np.tile(colour, (48, 64, 1)), tmp_path)
    full = _frame(gl_window, app)
    x0, y0, _w, _h = _gate_px(app)
    corner = (y0 + 3, x0 + 3)  # inside the gate, outside the model
    centre = (240, 320)  # inside the model
    assert np.abs(full[corner][:3].astype(int) - colour[:3]).max() <= 1
    assert np.array_equal(full[centre], plain[centre])
    assert app.set_likeness_view(photo_opacity=0.5)
    half = _frame(gl_window, app)
    mix = 0.5 * colour[:3] + 0.5 * plain[corner][:3].astype(float)
    assert np.abs(half[corner][:3].astype(float) - mix).max() <= 1.0
    app.close_lookdev()


# -- G7: the passepartout slot ---------------------------------------------------------------------------------------

def test_outside_the_gate_the_model_darkens_and_the_wire_does_not(gl_window):
    app = _app(gl_window, 640, 480, wire=True)
    app.camera.set_view(0.0, 0.0)
    app.camera.target, app.camera.distance = (0.0, 0.0, 0.0), 3.7  # the front face reaches out of the gate
    plain = _frame(gl_window, app)
    app.dispatch_command(cmd.TOGGLE_WIREFRAME_OVERLAY)
    wired = _frame(gl_window, app)
    app.set_likeness_view(overscan=1.5)  # before „Neu aus Ansicht“: the camera view shows the same picture
    assert app.new_likeness_camera() and app.look_through(0)
    with_gate = _frame(gl_window, app)
    x0, y0, w, h = _gate_px(app)
    outside = np.ones(with_gate.shape[:2], bool)
    outside[y0 - 2:y0 + h + 2, x0 - 2:x0 + w + 2] = False
    wire = np.any(wired[..., :3] != plain[..., :3], axis=-1) & outside
    face = ~wire & outside & np.any(np.abs(plain[..., :3].astype(int) - np.round(np.array(CLEAR) * 255)) > 3,
                                    axis=-1)
    assert wire.sum() > 50 and face.sum() > 1000
    darkened = np.abs(with_gate[face][:, :3].astype(int) - wired[face][:, :3].astype(int) // 2).max(axis=-1)
    assert (darkened <= 1).all(), darkened.max()
    assert np.array_equal(with_gate[wire], wired[wire])
