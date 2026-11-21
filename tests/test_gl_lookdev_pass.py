"""The LookDev pass in the real GL path (AD-038): the store's two accesses (§4.2 / §4.3), the pass and its GL state,
the grey card (E7), the depth contract (E8), a selected painted head (E13), the GL state (E14).

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_pass.py -q`."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from gui.imgui_layer import snapshot_gl_state  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from tests.test_gl_texture import GREEN, RED, _live, _plane  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.material import Material  # noqa: E402
from viewport.render_mesh import TRIANGLE_UVS, RenderMesh  # noqa: E402

SIZE = 160


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _bound(unit: int, target) -> int:
    from pyglet import gl

    binding = {gl.GL_TEXTURE_BUFFER: gl.GL_TEXTURE_BINDING_BUFFER, gl.GL_TEXTURE_2D: gl.GL_TEXTURE_BINDING_2D}[target]
    value = gl.GLint()
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    gl.glGetIntegerv(binding, value)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    return value.value


def _requested(gl_window, mesh, texture=None) -> RenderMesh:
    gl_window.switch_to()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    rm.bind_camera(OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0))
    rm.mark_camera_dirty(aspect=1.0)
    rm.bind_material(Material((0.5, 0.5, 0.5), texture=texture))
    rm.mark_material_dirty()
    rm.set_uvs_requested(True)
    rm.sync()
    return rm


# -- §4.2 / §4.3: the store's two accesses --------------------------------------------------------------------------

def test_bind_triangle_uvs_uploads_and_binds_only_the_uvs(gl_window):
    from pyglet import gl

    rm = _requested(gl_window, _plane(uvs=True))
    store = rm.store
    before = snapshot_gl_state()
    assert store.bind_triangle_uvs(3)
    name = _bound(3, gl.GL_TEXTURE_BUFFER)
    assert name and store._face_gl[TRIANGLE_UVS][1] == name
    assert set(store._face_gl) == {TRIANGLE_UVS}  # nothing else of the face data went up
    assert snapshot_gl_state() == before  # unit 0 active again
    # the buffer holds the store's UVs (read back through a 1D buffer view)
    buffer_id = store._face_gl[TRIANGLE_UVS][0]
    data = (gl.GLfloat * len(store._face_cpu[TRIANGLE_UVS]))()
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer_id)
    gl.glGetBufferSubData(gl.GL_TEXTURE_BUFFER, 0, len(data) * 4, data)
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, 0)
    assert list(data) == list(store._face_cpu[TRIANGLE_UVS])
    GLRenderStore.unbind_triangle_uvs(3)
    assert _bound(3, gl.GL_TEXTURE_BUFFER) == 0 and gl.glGetError() == gl.GL_NO_ERROR
    # a mesh without UVs has none to bind
    plain = _requested(gl_window, _plane(uvs=False))
    assert not plain.store.bind_triangle_uvs(3) and _bound(3, gl.GL_TEXTURE_BUFFER) == 0
    rm.store.release()
    plain.store.release()


def test_the_worklight_draw_after_a_uv_bind_is_unchanged(gl_window):
    """The Worklight draw of a requested mesh stays the untextured one, and a LookDev bind in between changes nothing."""
    from tests.test_gl_texture import _draw

    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    plain = _requested(gl_window, _plane(uvs=False))
    plain.set_uvs_requested(False)
    reference = _draw(gl_window, plain, camera)
    rm = _requested(gl_window, _plane(uvs=True))
    assert _draw(gl_window, rm, camera) == reference
    rm.store.bind_triangle_uvs(3)
    GLRenderStore.unbind_triangle_uvs(3)
    assert _draw(gl_window, rm, camera) == reference
    rm.store.release()
    plain.store.release()


def test_texture_binding_of_a_path_and_a_live_texture(gl_window, tmp_path):
    from pyglet import gl

    from tests.test_obj_uvs import write_png

    gl_window.switch_to()
    assert GLRenderStore.texture_binding(None) is None
    assert GLRenderStore.texture_binding(str(tmp_path / "missing.png")) is None
    path = tmp_path / "red.png"
    write_png(path, 4, 4, RED)
    target, name = GLRenderStore.texture_binding(str(path))
    texture = GLRenderStore.texture(str(path))
    assert (target, name) == (texture.target, texture.id)  # the shared cache: one upload
    live = _live(GREEN)
    assert live.gl_name is None
    target, name = GLRenderStore.texture_binding(live)
    assert target == gl.GL_TEXTURE_2D and name == live.gl_name and live.uploads == 1
    GLRenderStore.texture_binding(live)
    assert live.uploads == 1  # nothing pending: no second upload
    live.rgba[0:2, 0:2, :3] = RED
    live.mark(0, 0, 2, 2)
    live.finish()
    GLRenderStore.texture_binding(live)
    assert live.uploads == 2
    assert _bound(4, gl.GL_TEXTURE_2D) == 0 and gl.glGetError() == gl.GL_NO_ERROR  # the caller binds the unit
    live.release()


# -- §3: Viewport.shading, the LookDev pass, the background ---------------------------------------------------------

from core import Mesh  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport.lookdev_pass import LookDraw  # noqa: E402
from viewport.viewport import Viewport  # noqa: E402

BG_BOTTOM, BG_TOP = (0.10, 0.20, 0.30), (0.50, 0.40, 0.30)
#: A plain studio: no environment, one key from the camera (+Z), Lambert - the grey card's light.
FLAT = lo.Studio((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def _ld_state(**kw):
    values = dict(preset="test", studio=FLAT, key=lo.StudioLight(True, 1.0, 0.0, 0.0, 6500.0, 0.0),
                  fill=lo.StudioLight(False), rim=lo.StudioLight(False), env_intensity=0.0,
                  background=(BG_BOTTOM, BG_TOP), background_gradient=True)
    values.update(kw)
    return lo.LookdevState(**values)


def _plane_viewport(gl_window, uvs=True, texture=None):
    gl_window.switch_to()
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=1.0)
    viewport.set_object_entry("plane", _plane(uvs), (0.5, 0.5, 0.5), texture=texture)
    return viewport


def _frame(gl_window, viewport, clear=(0.0, 0.0, 0.0)) -> np.ndarray:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, SIZE, SIZE)
    gl.glClearColor(*clear, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    viewport.sync()
    viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return np.frombuffer(bytes(buf), dtype=np.uint8).reshape(SIZE, SIZE, 3).astype(int)  # row 0 = bottom


def _release(viewport) -> None:
    for entry in list(viewport.object_entries):
        viewport.remove_object_entry(entry)
    if viewport._lookdev_pass is not None:
        viewport._lookdev_pass.release()


def test_worklight_shading_is_todays_draw_and_creates_nothing(gl_window):
    plain = _plane_viewport(gl_window)
    reference = _frame(gl_window, plain)
    looked = _plane_viewport(gl_window)
    looked.set_object_entry("plane", looked.object_entries["plane"].mesh, (0.5, 0.5, 0.5),
                            look=LookDraw((0.5, 0.5, 0.5)))
    assert np.array_equal(_frame(gl_window, looked), reference)  # a LookDraw alone changes nothing in the Worklight
    assert looked._lookdev_pass is None and plain._lookdev_pass is None
    _release(plain)
    _release(looked)


def test_lookdev_draws_the_background_as_picked_and_the_mesh_through_the_pass(gl_window):
    viewport = _plane_viewport(gl_window)
    viewport.set_object_entry("plane", viewport.object_entries["plane"].mesh, (0.5, 0.5, 0.5),
                              look=LookDraw((0.5, 0.5, 0.5), roughness=1.0, specular=0.0))
    viewport.set_shading("lookdev", _ld_state())
    from pyglet import gl

    gl.glUseProgram(0)  # a Worklight draw before leaves its program bound; the passes stop theirs (as EyePass)
    before = snapshot_gl_state()
    pixels = _frame(gl_window, viewport, clear=(1.0, 0.0, 1.0))
    assert viewport.lookdev_pass.draws == 1
    # the background, as picked: no exposure, tone curve or encode (bottom row ~ bottom, top row ~ top)
    for row, colour in ((0, BG_BOTTOM), (SIZE - 1, BG_TOP)):
        expected = np.array(BG_BOTTOM) + (np.array(BG_TOP) - np.array(BG_BOTTOM)) * (row + 0.5) / SIZE
        assert np.abs(pixels[row, 0] - expected * 255).max() <= 1.5, (row, pixels[row, 0])
    # the plane faces the key at normal incidence: Lambert 1 x decode(0.5) -> Reinhard on luminance -> encode
    centre = pixels[SIZE // 2, SIZE // 2]
    lin = float(lo.srgb_decode(0.5))
    expected = float(lo.lookdev_output(np.array([lin, lin, lin]))[0]) * 255
    assert np.abs(centre - expected).max() <= 2, (centre, expected)
    assert snapshot_gl_state() == before
    viewport.set_shading("worklight")
    assert viewport.lookdev_state is None
    _release(viewport)


def test_an_entry_without_a_look_keeps_the_worklight_draw_in_the_room(gl_window):
    worklight = _plane_viewport(gl_window)
    reference = _frame(gl_window, worklight)
    viewport = _plane_viewport(gl_window)
    viewport.set_shading("lookdev", _ld_state(background_gradient=False, background=((0.0, 0.0, 0.0),) * 2))
    pixels = _frame(gl_window, viewport)
    assert viewport.lookdev_pass.draws == 0
    assert np.array_equal(pixels, reference)
    _release(worklight)
    _release(viewport)


def test_the_albedo_map_reaches_the_lookdev_pass(gl_window, tmp_path):
    from tests.test_obj_uvs import write_png

    path = tmp_path / "red.png"
    write_png(path, 4, 4, RED)
    viewport = _plane_viewport(gl_window)  # no Worklight texture: the UVs come from the LookDev request
    viewport.set_object_entry("plane", viewport.object_entries["plane"].mesh, (0.5, 0.5, 0.5),
                              look=LookDraw((0.5, 0.5, 0.5), roughness=1.0, specular=0.0, albedo=str(path)))
    assert viewport.object_entries["plane"].uvs_requested
    viewport.set_shading("lookdev", _ld_state())
    centre = _frame(gl_window, viewport)[SIZE // 2, SIZE // 2]
    assert centre[0] > centre[1] + 60 and centre[0] > centre[2] + 60, centre
    viewport.set_object_entry("plane", viewport.object_entries["plane"].mesh, (0.5, 0.5, 0.5), look=None)
    assert not viewport.object_entries["plane"].uvs_requested
    _release(viewport)


# -- E7: the grey card - skin and sclera in one linear pipeline ------------------------------------------------------

def test_grey_card_skin_matches_a_sclera_of_the_same_albedo_and_roughness(gl_window):
    """AD-038 §5.5 (E7): a Neutral grey card (albedo 0.5) on the skin pass and a sclera of the same albedo, roughness
    and F0, lit by the same key at normal incidence (no environment), match within 2/255."""
    import dataclasses
    import math

    from mirai.eye_object import DEFAULT_EYE, DEFAULT_LOOK, cornea_triangles, shell_mesh
    from viewport import eye_optics as eo
    from viewport.eye_pass import EyeDraw
    from viewport.material import DEFAULT_FINISH

    roughness = 0.5
    state = _ld_state(background_gradient=False, background=((0.0, 0.0, 0.0),) * 2,
                      key=lo.StudioLight(True, 1.5, 0.0, 0.0, 6500.0, 0.0))
    card = _plane_viewport(gl_window)
    card.set_object_entry("plane", card.object_entries["plane"].mesh, (0.5, 0.5, 0.5),
                          look=LookDraw((0.5, 0.5, 0.5), roughness=roughness, specular=eo.CORNEA_F0 / 0.08))
    card.set_shading("lookdev", state)
    skin = _frame(gl_window, card)[SIZE // 2, SIZE // 2]
    # the eye turned so it looks down +X: the camera on +Z sees its sclera face-on at the centre
    spec = dataclasses.replace(DEFAULT_EYE, limbus_level=0,
                               look=dataclasses.replace(DEFAULT_LOOK, sclera_roughness=roughness))
    c, s = math.cos(math.radians(90.0)), math.sin(math.radians(90.0))
    model = [0.8 * c, 0.0, -0.8 * s, 0.0, 0.0, 0.8, 0.0, 0.0, 0.8 * s, 0.0, 0.8 * c, 0.0, 0.0, 0.0, 0.0, 1.0]
    eye_vp = Viewport(Mesh(), store_type=GLRenderStore)
    eye_vp.bind_camera(OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0))
    eye_vp.on_camera_changed(aspect=1.0)
    grey = (0.5, 0.5, 0.5)
    eye_vp.set_object_entry("eye", shell_mesh(spec), grey, model_matrix=model, finish=DEFAULT_FINISH,
                            eye=EyeDraw(spec, None, grey, DEFAULT_FINISH, cornea_triangles()))
    eye_vp.set_shading("lookdev", state)
    sclera = _frame(gl_window, eye_vp)[SIZE // 2, SIZE // 2]
    assert any(k[7] and not k[5] for k in eye_vp.eye_pass.programs)  # the LOOKDEV variant, no look terms
    assert np.abs(skin - sclera).max() <= 2, (skin, sclera)
    lin = float(lo.srgb_decode(0.5))
    assert skin.min() > 0.5 * 255 * lin  # lit, not black
    _release(card)
    _release(eye_vp)
    eye_vp.eye_pass.release()


# -- E8: the depth contract - the wire over the LookDev pass is the wire over the Worklight --------------------------

def test_the_wire_lies_on_the_lookdev_pass_as_on_the_worklight(gl_window):
    from viewport.gl_line_overlay import GLLineOverlay

    def masks(shading):
        gl_window.switch_to()
        viewport = Viewport(Mesh(), store_type=GLRenderStore, line_overlay_type=GLLineOverlay)
        camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.4, pitch=0.3)
        viewport.bind_camera(camera)
        viewport.on_camera_changed(aspect=1.0)
        viewport.set_edit_mesh(_plane(True))
        viewport.set_edit_look(LookDraw((0.5, 0.5, 0.5)))
        if shading == "lookdev":
            viewport.set_shading("lookdev", _ld_state(background_gradient=False,
                                                      background=((0.0, 0.0, 0.0),) * 2))
        viewport.set_display(show_faces=True, show_edges=False, flat=False)
        plain = _frame(gl_window, viewport)
        viewport.set_display(show_faces=True, show_edges=True, flat=False)
        wired = _frame(gl_window, viewport)
        if viewport._lookdev_pass is not None:
            assert viewport.lookdev_pass.draws > 0
            viewport.lookdev_pass.release()
        viewport.render_mesh.store.release()
        return np.any(plain != wired, axis=-1)

    worklight, lookdev = masks("worklight"), masks("lookdev")
    assert worklight.sum() > 200  # the wire is drawn
    assert np.array_equal(worklight, lookdev)  # the same line pixels: same transform, same depth, same offset


# -- E13: a selected painted head keeps its albedo in the room --------------------------------------------------------

def test_a_selected_painted_object_keeps_its_paint_in_lookdev(gl_window):
    import main as production

    from mirai.application import Application
    from mirai.interaction import commands
    from mirai.paint.brush import RADIUS_STEPS_PERCENT
    from tests.test_paint_room import _stroke

    gl_window.switch_to()
    app = Application()
    app.init_scene("cube", **production.GL_TYPES)
    app.set_viewport_size(SIZE, SIZE)
    mesh = app.scene.mesh
    for i, fid in enumerate(mesh.all_face_ids()):
        mesh.set_face_uvs(fid, [(i / 6 + du / 6, dv) for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1))])
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_paint_resolution(1024)
    assert app.open_paint_room(), app.status_message
    app.set_paint_brush(colour=(0.9, 0.05, 0.05), radius_step=len(RADIUS_STEPS_PERCENT) - 1, opacity=1.0, flow=1.0)
    app.set_viewport_size(800, 600)  # `_stroke` aims in an 800x600 viewport
    for _ in range(3):
        _stroke(app, steps=10, dx=4.0)
    app.close_paint_room()
    app.set_viewport_size(SIZE, SIZE)
    app.dispatch_command(commands.SET_OBJECT_MODE)
    assert app.select_objects([app.scene.edit_object_id])
    app.update_viewport(0.0)
    worklight = _frame(gl_window, app.viewport)
    centre = worklight[SIZE // 2, SIZE // 2]
    assert not (centre[0] > centre[1] + 80)  # the Worklight shows the selection tint, not the paint
    assert app.open_lookdev()
    for _ in range(3):
        app.update_viewport(0.0)
    assert app.viewport.shading == "lookdev"
    look = app.viewport._edit_look
    assert look is not None and look.albedo is app.paint_display.texture(app.scene.edit_object)
    pixels = _frame(gl_window, app.viewport)
    red = (pixels[..., 0] > pixels[..., 1] + 60) & (pixels[..., 0] > pixels[..., 2] + 60)
    assert red.sum() > 100, red.sum()  # the composite drawn by the LookDev pass
    app.close_lookdev()
    app.viewport.lookdev_pass.release()
    app.shutdown()


# -- E14: both passes and the background leave the GL state as found -------------------------------------------------

def test_both_passes_and_the_background_leave_the_gl_state_as_found(gl_window, tmp_path):
    from pyglet import gl

    from mirai.eye_object import DEFAULT_EYE, cornea_triangles, shell_mesh
    from tests.test_obj_uvs import write_png
    from viewport.eye_pass import EyeDraw
    from viewport.material import DEFAULT_FINISH

    write_png(tmp_path / "t.png", 4, 4, GREEN)
    viewport = _plane_viewport(gl_window)
    viewport.set_object_entry("plane", viewport.object_entries["plane"].mesh, (0.5, 0.5, 0.5),
                              look=LookDraw((0.5, 0.5, 0.5), albedo=str(tmp_path / "t.png")))
    grey = (0.6, 0.6, 0.6)
    eye_model = [0.4, 0, 0, 0, 0, 0.4, 0, 0, 0, 0, 0.4, 0, 0.5, 0.3, 0.6, 1.0]
    viewport.set_object_entry("eye", shell_mesh(DEFAULT_EYE), grey, model_matrix=eye_model, finish=DEFAULT_FINISH,
                              eye=EyeDraw(DEFAULT_EYE, None, grey, DEFAULT_FINISH, cornea_triangles()))
    viewport.set_eye_display(tier="full")
    viewport.set_shading("lookdev", _ld_state(studio=lo.EYE_STUDIO, env_intensity=0.5))
    _frame(gl_window, viewport)
    gl.glUseProgram(0)
    before = snapshot_gl_state()
    _frame(gl_window, viewport)
    assert snapshot_gl_state() == before and gl.glGetError() == gl.GL_NO_ERROR
    for unit, target in ((3, gl.GL_TEXTURE_BUFFER), (4, gl.GL_TEXTURE_2D)):
        assert _bound(unit, target) == 0, unit
    assert viewport.lookdev_pass.draws >= 2 and any(k[7] for k in viewport.eye_pass.programs)
    _release(viewport)
    viewport.eye_pass.release()


# -- E19 (LD-2, AD-038 §18): "Bild speichern" - the LookDev view without overlays ------------------------------------

def test_the_capture_is_the_lookdev_view_without_overlays_and_the_frame_after_it_is_unchanged(gl_window):
    """One extra render of the meshes into the back buffer, read back: it equals the frame drawn with the wire off; the
    normal frame that follows (wire on) equals a frame without a capture; nothing is bound or left changed."""
    from pyglet import gl

    from viewport.gl_line_overlay import GLLineOverlay

    gl_window.switch_to()
    viewport = Viewport(Mesh(), store_type=GLRenderStore, line_overlay_type=GLLineOverlay)
    viewport.bind_camera(OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.4, pitch=0.3))
    viewport.on_camera_changed(aspect=1.0)
    viewport.set_edit_mesh(_plane(True))
    viewport.set_edit_look(LookDraw((0.5, 0.5, 0.5)))
    viewport.set_shading("lookdev", _ld_state())
    viewport.set_display(show_faces=True, show_edges=False, flat=False)
    without = _frame(gl_window, viewport)
    viewport.set_display(show_faces=True, show_edges=True, flat=False)
    wired = _frame(gl_window, viewport)
    assert np.any(without != wired)  # the wire shows in the normal frame

    got = []
    viewport.request_capture(got.append)
    assert viewport.capture_pending
    gl.glUseProgram(0)
    before = snapshot_gl_state()
    after = _frame(gl_window, viewport, clear=(1.0, 0.0, 1.0))  # a different clear: the capture's own clear must not leak
    assert not viewport.capture_pending and len(got) == 1
    rgba = got[0]
    assert rgba.shape == (SIZE, SIZE, 4) and rgba.dtype == np.uint8 and (rgba[..., 3] == 255).all()
    assert np.array_equal(rgba[::-1, :, :3].astype(int), without)  # top row first; no wire
    assert np.array_equal(after, wired)  # the frame after the capture is the normal one
    gl.glUseProgram(0)
    assert snapshot_gl_state() == before
    viewport.lookdev_pass.release()
    viewport.render_mesh.store.release()


def test_save_lookdev_image_writes_the_png(gl_window, tmp_path):
    """`Application.save_lookdev_image` in the real draw path: refused outside the room, a PNG of the window's size
    written by the next frame, its pixels the captured ones."""
    from mirai import iris_import
    from mirai.application import Application

    gl_window.switch_to()
    app = Application()
    app.init_scene("cube", store_type=GLRenderStore)
    app.set_viewport_size(SIZE, SIZE)
    app.frame_scene()
    assert app.save_lookdev_image(tmp_path / "x.png") is False and "only inside" in app.status_message
    app.open_lookdev()
    for _ in range(app.LOOKDEV_PREPARE_FRAMES + 1):
        app.update_viewport(0.0)
        _frame(gl_window, app.viewport)
    assert app.viewport.shading == "lookdev"
    path = tmp_path / "shots" / "head.png"
    assert app.save_lookdev_image(path) and not path.exists()  # written in the next frame
    _frame(gl_window, app.viewport)
    assert path.exists() and app.lookdev.last_image == path and "saved" in app.status_message
    rgba = iris_import.decode_png(path.read_bytes())
    assert rgba.shape == (SIZE, SIZE, 4) and (rgba[..., 3] == 255).all()
    centre, corner = rgba[SIZE // 2, SIZE // 2, :3], rgba[0, 0, :3]
    assert np.any(centre != corner)  # the cube in front of the studio background
    app.close_lookdev()
