"""LookDev P3 S7 - the material's maps in the real GL path (AD-039 §10 / §20): a flat normal map and white grey maps
change no pixel, a tilted constant normal map lights the plane as its twin (`lookdev_optics.ld_normal_mapped`) and the
DirectX flag flips it, the roughness map multiplies the roughness, the translucency map scales the backscatter, a face
without UVs reads no map, the GL state as found (units 3, 9-11), a context with too few texture units turns the maps
off; plus the GPU parity of `ld_cotangent_frame` / `ld_normal_tangent` against their twins.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_maps.py -q`."""

from __future__ import annotations

import ctypes
import dataclasses

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.iris_import import encode_png  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import lookdev_features  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport import lookdev_shaders as ls  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.lookdev_pass import LookDraw  # noqa: E402
from viewport.viewport import Viewport  # noqa: E402

SIZE = 128
HALF = 2.0
FLAT = lo.Studio((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
MAPS_ONLY = lo.LookdevEffects(shadow=False, eye_shadow=False, dual_lobe=False, thickness=False, cube=False, maps=True)
NO_MAPS = dataclasses.replace(MAPS_ONLY, maps=False)
MATTE = LookDraw((0.5, 0.5, 0.5), roughness=1.0, specular=0.0)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _plane(n: int = 4, uv_faces=None) -> Mesh:
    """A square in XZ at y = 0 facing +Y, n x n quads; UVs u = (x + HALF) / 2 HALF, v = (z + HALF) / 2 HALF on the faces
    `uv_faces` picks by index (all by default)."""
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex((-HALF + 2 * HALF * i / n, 0.0, -HALF + 2 * HALF * j / n))
           for i in range(n + 1) for j in range(n + 1)}
    for i in range(n):
        for j in range(n):
            face = [ids[i, j], ids[i, j + 1], ids[i + 1, j + 1], ids[i + 1, j]]
            p = [np.asarray(mesh.vertex_position(v)) for v in face]
            if np.cross(p[1] - p[0], p[2] - p[0])[1] < 0:
                face.reverse()
            mesh.add_face(face)
    for index, fid in enumerate(mesh.all_face_ids()):
        if uv_faces is None or uv_faces(index):
            corners = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
            mesh.set_face_uvs(fid, [((x + HALF) / (2 * HALF), (z + HALF) / (2 * HALF)) for x, _y, z in corners])
    return mesh


def _png(tmp_path, name: str, rgb) -> str:
    image = np.zeros((8, 8, 4), np.uint8)
    image[..., :3] = rgb
    image[..., 3] = 255
    path = tmp_path / f"{name}.png"
    path.write_bytes(encode_png(image))
    return str(path)


def _state(key_az=0.0, key_el=45.0, effects=MAPS_ONLY, **kw):
    values = dict(preset="test", studio=FLAT, key=lo.StudioLight(True, 1.0, key_az, key_el, 6500.0, 0.0),
                  fill=lo.StudioLight(False), rim=lo.StudioLight(False), env_intensity=0.0,
                  background=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), background_gradient=False, effects=effects)
    values.update(kw)
    return lo.LookdevState(**values)


def _viewport(gl_window, mesh: Mesh, look: LookDraw, camera=None) -> Viewport:
    gl_window.switch_to()
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    viewport.bind_camera(camera or OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.0, yaw=0.0, pitch=1.45))
    viewport.on_camera_changed(aspect=1.0)
    viewport.set_object_entry("plane", mesh, (0.5, 0.5, 0.5), look=look)
    return viewport


def _frame(gl_window, viewport) -> np.ndarray:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, SIZE, SIZE)
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    viewport.sync()
    viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return np.frombuffer(bytes(buf), dtype=np.uint8).reshape(SIZE, SIZE, 3).astype(int)


def _draw(gl_window, viewport, look: LookDraw, state) -> np.ndarray:
    viewport.set_object_entry("plane", viewport.object_entries["plane"].mesh, (0.5, 0.5, 0.5), look=look)
    viewport.set_shading("lookdev", state)
    return _frame(gl_window, viewport)


def _release(viewport) -> None:
    for entry in list(viewport.object_entries):
        viewport.remove_object_entry(entry)
    if viewport._lookdev_pass is not None:
        viewport._lookdev_pass.release()


def _centre(image: np.ndarray) -> np.ndarray:
    c = SIZE // 2
    return np.median(image[c - 6:c + 6, c - 6:c + 6].reshape(-1, 3), axis=0)


def _matte_value(state, normal) -> float:
    """The twin of the matte plane's pixel: Lambert from the key alone (no environment, fill, rim, wrap or specular)."""
    frame = lo.frame_uniforms(state)
    n = np.asarray(normal, float) / np.linalg.norm(normal)
    colour = lo.srgb_decode((0.5, 0.5, 0.5)) * np.asarray(frame["u_ld_light_color"][0]) * max(
        float(np.dot(n, frame["u_ld_light_dir"][0])), 0.0)
    return lo.lookdev_output(colour, frame["u_ld_exposure"], state.tone_curve) * 255.0


# -- a flat map changes nothing ---------------------------------------------------------------------------------------

def test_a_flat_normal_map_and_white_grey_maps_change_no_pixel(gl_window, tmp_path):
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.5, yaw=0.4, pitch=0.7)
    glossy = LookDraw((0.6, 0.5, 0.4), roughness=0.4, specular=1.0, backscatter=0.5)
    viewport = _viewport(gl_window, _plane(), glossy, camera)
    state = _state(key_az=200.0, key_el=35.0)
    plain = _draw(gl_window, viewport, glossy, state)
    assert (False, True, False, False, False) in viewport.lookdev_pass.programs
    assert viewport.lookdev_pass.features is None  # the maps on, but no map drawn: nothing probed (AD-039 §2.2)
    mapped = dataclasses.replace(glossy, normal_map=_png(tmp_path, "flat", (128, 128, 255)),
                                 roughness_map=_png(tmp_path, "white", (255, 255, 255)),
                                 translucency_map=_png(tmp_path, "white2", (255, 255, 255)))
    with_maps = _draw(gl_window, viewport, mapped, state)
    assert (False, True, False, False, False, True, True, True) in viewport.lookdev_pass.programs
    assert plain.max() > 40 and np.abs(with_maps - plain).max() <= 1
    # the effect off: the maps are not drawn, the frame is the one without them
    assert np.array_equal(_draw(gl_window, viewport, mapped, _state(key_az=200.0, key_el=35.0, effects=NO_MAPS)),
                          plain)
    _release(viewport)


# -- the normal map tilts the shading normal --------------------------------------------------------------------------

def test_a_tilted_normal_map_lights_the_plane_as_its_twin_and_directx_flips_green(gl_window, tmp_path):
    viewport = _viewport(gl_window, _plane(), MATTE)
    state = _state(key_az=0.0, key_el=45.0)  # the key toward +Z, 45° up
    plain = _centre(_draw(gl_window, viewport, MATTE, state))
    assert abs(plain[0] - _matte_value(state, (0.0, 1.0, 0.0))[0]) <= 2
    texel = np.array([128.0, 200.0, 230.0]) / 255.0  # green up: toward +v = +Z
    path = _png(tmp_path, "tilt", (128, 200, 230))
    tangent = lo.normal_map_tangent(texel)
    up = np.array([0.0, 1.0, 0.0])
    tu, tv = np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])  # the plane's dp/du, dp/dv
    toward = tu * tangent[0] + tv * tangent[1] + up * tangent[2]
    lit = _centre(_draw(gl_window, viewport, dataclasses.replace(MATTE, normal_map=path), state))
    assert abs(lit[0] - _matte_value(state, toward)[0]) <= 2 and lit[0] > plain[0] + 8
    down = lo.normal_map_tangent(texel, green_down=True)
    away = tu * down[0] + tv * down[1] + up * down[2]
    dx = _centre(_draw(gl_window, viewport, dataclasses.replace(MATTE, normal_map=path, normal_green_down=True), state))
    assert abs(dx[0] - _matte_value(state, away)[0]) <= 2 and dx[0] < plain[0] - 8
    half = _centre(_draw(gl_window, viewport, dataclasses.replace(MATTE, normal_map=path, normal_strength=0.5), state))
    half_n = tu * tangent[0] * 0.5 + tv * tangent[1] * 0.5 + up * tangent[2]
    assert abs(half[0] - _matte_value(state, half_n)[0]) <= 2 and plain[0] < half[0] < lit[0]
    zero = _centre(_draw(gl_window, viewport, dataclasses.replace(MATTE, normal_map=path, normal_strength=0.0), state))
    assert np.abs(zero - plain).max() <= 1
    _release(viewport)


# -- the grey maps ----------------------------------------------------------------------------------------------------

def test_the_roughness_map_multiplies_the_materials_roughness(gl_window, tmp_path):
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.5, yaw=0.0, pitch=0.6)
    glossy = LookDraw((0.4, 0.4, 0.4), roughness=0.6, specular=1.0)
    viewport = _viewport(gl_window, _plane(), glossy, camera)
    state = _state(key_az=180.0, key_el=35.0)  # in the camera's mirror direction: a highlight on the plane
    half_map = _draw(gl_window, viewport, dataclasses.replace(glossy, roughness_map=_png(tmp_path, "g", (128,) * 3)),
                     state)
    same = _draw(gl_window, viewport, dataclasses.replace(glossy, roughness=0.6 * 128.0 / 255.0), state)
    assert np.abs(half_map - same).max() <= 1
    rough = _draw(gl_window, viewport, glossy, state)
    assert np.abs(half_map - rough).max() > 20  # a sharper highlight than the material alone
    _release(viewport)


def test_the_translucency_map_scales_the_backscatter(gl_window, tmp_path):
    backlit = LookDraw((0.7, 0.6, 0.5), roughness=1.0, specular=0.0, backscatter=1.0)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.5, yaw=0.0, pitch=0.5)
    viewport = _viewport(gl_window, _plane(), backlit, camera)
    state = _state(key_az=0.0, key_el=-40.0)  # the key from below: the plane's top faces away from it (M1's proxy)
    lit = _draw(gl_window, viewport, backlit, state)
    assert lit.max() > 10
    black = _draw(gl_window, viewport, dataclasses.replace(backlit, translucency_map=_png(tmp_path, "k", (0,) * 3)),
                  state)
    none = _draw(gl_window, viewport, dataclasses.replace(backlit, backscatter=0.0), state)
    assert np.abs(black - none).max() <= 1
    grey = _draw(gl_window, viewport, dataclasses.replace(backlit, translucency_map=_png(tmp_path, "g", (128,) * 3)),
                 state)
    scaled = _draw(gl_window, viewport, dataclasses.replace(backlit, backscatter=128.0 / 255.0), state)
    assert np.abs(grey - scaled).max() <= 1
    _release(viewport)


# -- faces without UVs ------------------------------------------------------------------------------------------------

def test_a_face_without_uvs_reads_no_map(gl_window, tmp_path):
    path = _png(tmp_path, "tilt", (128, 200, 230))
    mesh = _plane(n=4, uv_faces=lambda index: index < 8)  # half the faces
    viewport = _viewport(gl_window, mesh, MATTE)
    state = _state()
    plain = _draw(gl_window, viewport, MATTE, state)
    mapped = _draw(gl_window, viewport, dataclasses.replace(MATTE, normal_map=path), state)
    changed = np.abs(mapped - plain).max(axis=-1) > 5
    same = np.abs(mapped - plain).max(axis=-1) <= 1
    lit = plain.max(axis=-1) > 0
    assert changed[lit].mean() > 0.3 and same[lit].mean() > 0.3  # one half tilted, the other as before
    _release(viewport)
    viewport = _viewport(gl_window, _plane(uv_faces=lambda index: False), MATTE)  # no UVs at all: no map, no UV request
    plain = _draw(gl_window, viewport, MATTE, state)
    assert np.array_equal(_draw(gl_window, viewport, dataclasses.replace(MATTE, normal_map=path), state), plain)
    assert all(len(key) == 5 for key in viewport.lookdev_pass.programs)
    _release(viewport)


# -- the GL state and the feature check --------------------------------------------------------------------------------

def test_a_map_frame_leaves_units_3_and_9_to_11_unbound(gl_window, tmp_path):
    from pyglet import gl

    look = dataclasses.replace(MATTE, roughness_map=_png(tmp_path, "r", (200,) * 3),
                               normal_map=_png(tmp_path, "n", (128, 128, 255)),
                               translucency_map=_png(tmp_path, "t", (100,) * 3))
    viewport = _viewport(gl_window, _plane(), look)
    _draw(gl_window, viewport, look, _state())
    active = gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
    assert active.value == gl.GL_TEXTURE0
    for unit in (ls.UV_UNIT, *ls.MAP_UNITS.values()):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        bound, buffer = gl.GLint(), gl.GLint()
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D, ctypes.byref(bound))
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_BUFFER, ctypes.byref(buffer))
        assert (bound.value, buffer.value) == (0, 0), unit
    gl.glActiveTexture(gl.GL_TEXTURE0)
    _release(viewport)


def test_too_few_texture_units_turn_the_maps_off_with_a_status_line(gl_window, tmp_path, monkeypatch):
    look = dataclasses.replace(MATTE, normal_map=_png(tmp_path, "n", (128, 200, 230)))
    reference = _viewport(gl_window, _plane(), look)
    want = _draw(gl_window, reference, look, _state(effects=NO_MAPS))
    _release(reference)
    monkeypatch.setitem(lookdev_features.CHECKS, "texture_units", lambda: False)
    viewport = _viewport(gl_window, _plane(), look)
    assert np.array_equal(_draw(gl_window, viewport, look, _state()), want)
    assert not viewport.lookdev_effects().maps
    assert viewport.take_lookdev_notices() == ["LookDev: Maps aus – zu wenige Textureinheiten"]
    _release(viewport)


def test_the_texture_unit_check_passes_here(gl_window):
    gl_window.switch_to()
    assert lookdev_features.CHECKS["texture_units"]()


# -- GPU parity of the normal map's frame ---------------------------------------------------------------------------

PARITY_BODY = """
uniform samplerBuffer u_inputs;
uniform int u_width;
uniform int u_count;
layout(location = 0) out vec4 out_value;
void main() {
    int i = int(gl_FragCoord.y) * u_width + int(gl_FragCoord.x);
    if (i >= u_count) { out_value = vec4(0.0); return; }
    vec4 a = texelFetch(u_inputs, 4 * i);      // n, strength
    vec4 b = texelFetch(u_inputs, 4 * i + 1);  // dp1, green
    vec4 c = texelFetch(u_inputs, 4 * i + 2);  // dp2
    vec4 d = texelFetch(u_inputs, 4 * i + 3);  // duv1, duv2
    mat3 frame = ld_cotangent_frame(a.xyz, b.xyz, c.xyz, d.xy, d.zw);
    vec3 m = frame * ld_normal_tangent(vec3(0.85, 0.3, 0.9), a.w, b.w);
    out_value = vec4(dot(m, m) > 1e-12 ? normalize(m) : a.xyz, 1.0);
}
"""


def test_gpu_parity_of_the_normal_maps_frame(gl_window):
    from pyglet import gl
    from pyglet.graphics.shader import Shader, ShaderProgram

    from viewport.gl_render_store import _register_sampler_buffer_uniform

    gl_window.switch_to()
    _register_sampler_buffer_uniform()
    program = ShaderProgram(Shader(ls.FULLSCREEN_VERTEX_SRC, "vertex"),  # gl_VertexID: no vertex buffer
                            Shader("#version 330 core\n" + ls.LD_NORMAL_MAP_SRC + PARITY_BODY, "fragment"))
    rng = np.random.default_rng(7)
    count, width = 1024, 32
    n = rng.normal(size=(count, 3))
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    dp1, dp2 = rng.normal(size=(count, 3)) * 0.01, rng.normal(size=(count, 3)) * 0.01
    duv = rng.normal(size=(count, 4)) * 0.02
    duv[:16] = 0.0  # degenerate UV: the normal stays
    strength = rng.uniform(0.0, 2.0, count)
    green = np.where(rng.uniform(size=count) < 0.5, 1.0, -1.0)
    inputs = np.zeros((count, 4, 4), np.float32)
    inputs[:, 0, :3], inputs[:, 0, 3] = n, strength
    inputs[:, 1, :3], inputs[:, 1, 3] = dp1, green
    inputs[:, 2, :3] = dp2
    inputs[:, 3] = duv
    ids = [gl.GLuint() for _ in range(4)]  # buffer, texture, fbo, colour target
    gl.glGenBuffers(1, ctypes.byref(ids[0]))
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, ids[0])
    data = inputs.tobytes()
    gl.glBufferData(gl.GL_TEXTURE_BUFFER, len(data), data, gl.GL_STATIC_DRAW)
    gl.glGenTextures(1, ctypes.byref(ids[1]))
    gl.glActiveTexture(gl.GL_TEXTURE0 + 1)
    gl.glBindTexture(gl.GL_TEXTURE_BUFFER, ids[1])
    gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, ids[0])
    gl.glGenTextures(1, ctypes.byref(ids[3]))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_2D, ids[3])
    rows = count // width
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, width, rows, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    gl.glGenFramebuffers(1, ctypes.byref(ids[2]))
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, ids[2])
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, ids[3], 0)
    vao = gl.GLuint()
    gl.glGenVertexArrays(1, ctypes.byref(vao))
    gl.glBindVertexArray(vao)
    gl.glViewport(0, 0, width, rows)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glDisable(gl.GL_BLEND)
    program.use()
    program["u_inputs"] = 1
    program["u_width"] = width
    program["u_count"] = count
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    out = np.empty((rows, width, 4), np.float32)
    gl.glReadPixels(0, 0, width, rows, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data_as(ctypes.c_void_p))
    program.stop()
    gl.glBindVertexArray(0)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glActiveTexture(gl.GL_TEXTURE0 + 1)
    gl.glBindTexture(gl.GL_TEXTURE_BUFFER, 0)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glDeleteVertexArrays(1, ctypes.byref(vao))
    gl.glDeleteFramebuffers(1, ctypes.byref(ids[2]))
    gl.glDeleteTextures(1, ctypes.byref(ids[1]))
    gl.glDeleteTextures(1, ctypes.byref(ids[3]))
    gl.glDeleteBuffers(1, ctypes.byref(ids[0]))
    program.delete()
    assert gl.glGetError() == gl.GL_NO_ERROR
    gpu = out.reshape(count, 4)[:, :3]
    texel = np.broadcast_to([0.85, 0.3, 0.9], (count, 3))
    twin = np.stack([lo.ld_normal_mapped(n[i], dp1[i], dp2[i], duv[i, :2], duv[i, 2:], texel[i], strength[i],
                                         green[i] < 0) for i in range(count)])
    assert np.abs(gpu - twin).max() < 2e-4
    assert np.allclose(gpu[:16], n[:16], atol=1e-6)
