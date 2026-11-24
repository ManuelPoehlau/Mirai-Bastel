"""LookDev P3 S5 - the studio's environment cube in the real GL path (AD-039 §8 / §21): level 0 is the analytic studio
(`lookdev_optics.ld_studio`), the three texels at a cube corner are equal at every level (the corner fix), the rough
levels match the NumPy GGX prefilter (`lookdev_optics.prefilter_ggx`), `ld_env_cube` reads the level of the roughness
in the studio's frame (`textureLod` read-back), the cube is prefiltered only on a studio content change, the
rendered-then-copied cube samples over many frames (the reference PC's defect, §11.1 run 4 / 5), the effect off draws
the frame before S5 with nothing on unit 8, the GL state as found (the seamless flag), and a context without the cube
target turns the effect off with a status line.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_cube.py -q`."""

from __future__ import annotations

import ctypes
import dataclasses
import math

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.lookdev_presets import preset  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import eye_shaders as es  # noqa: E402
from viewport import lookdev_features  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport import lookdev_shaders as ls  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.lookdev_cube import EnvCube  # noqa: E402
from viewport.lookdev_pass import LookDraw  # noqa: E402
from viewport.viewport import Viewport  # noqa: E402

SIZE = 128
#: A studio with a bright, sharp softbox, a dome and a floor (the parity test's studio).
STUDIO = lo.Studio((0.25, 0.22, 0.2), (0.12, 0.12, 0.13), (0.03, 0.03, 0.035),
                   (lo.Softbox(40.0, 25.0, 25.0, 18.0, (6.0, 5.8, 5.5)),
                    lo.Softbox(-120.0, 10.0, 5.0, 30.0, (3.0, 3.0, 3.2)),
                    lo.Softbox(180.0, 60.0, 30.0, 10.0, (1.0, 1.0, 1.0))))
CUBE_ONLY = lo.LookdevEffects(shadow=False, eye_shadow=False, dual_lobe=False, thickness=False, cube=True, maps=False)
NO_CUBE = dataclasses.replace(CUBE_ONLY, cube=False)
GLOSSY = LookDraw((0.5, 0.45, 0.4), roughness=0.45, specular=1.0)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture(scope="module")
def cube(gl_window):
    gl_window.switch_to()
    built = EnvCube()
    assert built.update(STUDIO) and built.ready and built.prefilters == 1
    from pyglet import gl

    assert gl.glGetError() == gl.GL_NO_ERROR
    yield built
    built.release()


def _sphere(n: int = 24) -> Mesh:
    mesh = Mesh()
    rows = [[mesh.add_vertex((math.sin(math.pi * i / n) * math.cos(2 * math.pi * j / n), math.cos(math.pi * i / n),
                              math.sin(math.pi * i / n) * math.sin(2 * math.pi * j / n))) for j in range(n)]
            for i in range(1, n)]
    top, bottom = mesh.add_vertex((0.0, 1.0, 0.0)), mesh.add_vertex((0.0, -1.0, 0.0))
    for j in range(n):
        k = (j + 1) % n
        mesh.add_face([top, rows[0][k], rows[0][j]])
        mesh.add_face([bottom, rows[-1][j], rows[-1][k]])
        for i in range(len(rows) - 1):
            mesh.add_face([rows[i][j], rows[i][k], rows[i + 1][k], rows[i + 1][j]])
    return mesh


def _state(studio=STUDIO, effects=CUBE_ONLY, **kw):
    values = dict(preset="test", studio=studio, key=lo.StudioLight(True, 1.0, 40.0, 30.0, 6500.0, 0.1),
                  fill=lo.StudioLight(False), rim=lo.StudioLight(False), env_intensity=1.0, rotation=20.0,
                  background=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), background_gradient=False, effects=effects)
    values.update(kw)
    return lo.LookdevState(**values)


def _viewport(gl_window, look: LookDraw = GLOSSY) -> Viewport:
    gl_window.switch_to()
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    viewport.bind_camera(OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.3, pitch=0.3))
    viewport.on_camera_changed(aspect=1.0)
    viewport.set_object_entry("sphere", _sphere(), (0.5, 0.5, 0.5), look=look)
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


def _release(viewport) -> None:
    for entry in list(viewport.object_entries):
        viewport.remove_object_entry(entry)
    if viewport._lookdev_pass is not None:
        viewport._lookdev_pass.release()


def _relative(a, b, floor: float = 0.02) -> float:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return float(np.max(np.abs(a - b) / np.maximum(np.abs(b), floor)))


# -- the cube's content -----------------------------------------------------------------------------------------------

def test_level_0_is_the_analytic_studio(cube):
    """AD-039 §8: level 0 against `ld_studio(d, 0)` at every texel's direction (the corner fix's included), within one
    RGBA16F step (2^-10 relative: a driver may round the store toward zero, Mesa does) plus 2e-4 for the shader's float
    evaluation - the AD's "1e-3" is that format limit (§21.2 S5-2; llvmpipe 1.14e-3, LD-0 (c) on the reference PC
    6e-4)."""
    level0 = cube.read_back(0)
    assert level0.shape == (6, ls.CUBE_SIZE, ls.CUBE_SIZE, 4)
    for face in range(6):
        want = lo.ld_studio(lo.cube_texel_directions(face, ls.CUBE_SIZE), 0.0, STUDIO)
        assert _relative(level0[face, ..., :3], want) <= 2.0 ** -10 + 2e-4, face
    assert level0[..., :3].max() > 3.0  # the softboxes are in it (a float cube: above 1)


def _corner_spread(faces: np.ndarray) -> float:
    side = faces.shape[1]
    worst = 0.0
    for corner in np.array(np.meshgrid([-1.0, 1.0], [-1.0, 1.0], [-1.0, 1.0])).T.reshape(-1, 3):
        texels = []
        for face in range(6):
            for ty, tx in ((0, 0), (0, side - 1), (side - 1, 0), (side - 1, side - 1)):
                s, t = (1.0 if tx else -1.0), (1.0 if ty else -1.0)
                if np.allclose(lo.cube_face_direction(face, s, t), corner):
                    texels.append(faces[face, ty, tx, :3])
        assert len(texels) == 3
        values = np.array(texels)
        worst = max(worst, float(np.max(values.max(0) - values.min(0))))
    return worst


def test_the_corner_texels_are_equal_at_every_level(cube):
    """AD-039 C7: the three texels that meet at a cube corner hold the same value at every level (spread 0)."""
    for level in range(ls.CUBE_LEVELS):
        assert _corner_spread(cube.read_back(level)) == 0.0, level


def test_the_rough_levels_match_the_numpy_prefilter(cube):
    """AD-039 §8: levels 1-6 against `prefilter_ggx` (the same 64 Hammersley samples) at a few texels each, ≤ 2 %."""
    rng = np.random.default_rng(5)
    for level in range(1, ls.CUBE_LEVELS):
        side = ls.CUBE_SIZE >> level
        faces = cube.read_back(level)
        for face in range(6):
            dirs = lo.cube_texel_directions(face, side)
            picks = rng.integers(0, side, size=(4, 2))
            got = np.array([faces[face, ty, tx, :3] for ty, tx in picks])
            want = lo.prefilter_ggx(np.array([dirs[ty, tx] for ty, tx in picks]), lo.cube_level_roughness(level),
                                    STUDIO)
            assert _relative(got, want) <= 0.02, (level, face, got, want)


ENV_BODY = """
uniform vec3 u_dirs[16];
uniform float u_rough[16];
layout(location = 0) out vec4 out_value;
void main() {
    int i = int(gl_FragCoord.x);
    out_value = vec4(ld_env_cube(u_dirs[i], u_rough[i]), 1.0);
}
"""


def _ld_env_cube(cube, dirs, rough, values) -> np.ndarray:
    """`LD_CUBE_SRC`'s `ld_env_cube` on the GPU for up to 16 world directions into an RGBA32F row."""
    from pyglet import gl
    from pyglet.graphics.shader import Shader, ShaderProgram

    from viewport.lookdev_pass import set_uniforms

    fragment = "#version 330 core\n" + ls.LD_BRDF_SRC + ls.LD_COMMON_SRC + ls.LD_CUBE_SRC + ENV_BODY
    program = ShaderProgram(Shader(es.FULLSCREEN_VERTEX_SRC, "vertex"), Shader(fragment, "fragment"))
    count = len(dirs)
    fbo, rbo, vao, vbo = gl.GLuint(), gl.GLuint(), gl.GLuint(), gl.GLuint()
    gl.glGenFramebuffers(1, ctypes.byref(fbo))
    gl.glGenRenderbuffers(1, ctypes.byref(rbo))
    gl.glGenVertexArrays(1, ctypes.byref(vao))
    gl.glGenBuffers(1, ctypes.byref(vbo))
    gl.glBindVertexArray(vao.value)
    tri = (gl.GLfloat * 6)(-1.0, -1.0, 3.0, -1.0, -1.0, 3.0)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo.value)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tri), tri, gl.GL_STATIC_DRAW)
    gl.glEnableVertexAttribArray(0)
    gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
    gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, rbo.value)
    gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA32F, 16, 1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
    gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, rbo.value)
    gl.glViewport(0, 0, 16, 1)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glDisable(gl.GL_BLEND)
    program.use()
    pad = 16 - count
    set_uniforms(program, dict(values, u_dirs=[tuple(map(float, d)) for d in dirs] + [(0.0, 0.0, 1.0)] * pad,
                               u_rough=[float(r) for r in rough] + [0.0] * pad, **cube.uniforms()))
    cube.bind()
    gl.glEnable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    gl.glDisable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
    cube.unbind()
    out = (gl.GLfloat * (16 * 4))()
    gl.glReadPixels(0, 0, 16, 1, gl.GL_RGBA, gl.GL_FLOAT, out)
    program.stop()
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glBindVertexArray(0)
    for name, fn, ident in (("fbo", gl.glDeleteFramebuffers, fbo), ("rbo", gl.glDeleteRenderbuffers, rbo),
                            ("vao", gl.glDeleteVertexArrays, vao), ("vbo", gl.glDeleteBuffers, vbo)):
        fn(1, ctypes.byref(ident))
    program.delete()
    assert gl.glGetError() == gl.GL_NO_ERROR
    return np.frombuffer(bytes(out), np.float32).reshape(16, 4)[:count, :3].astype(np.float64)


def test_ld_env_cube_reads_the_level_of_the_roughness_in_the_studio_frame(cube):
    """AD-039 §8 (the LD-0 (c) `textureLod` read-back): at a texel's centre direction and the roughness of its level,
    `ld_env_cube` returns that texel times the environment intensity - with the studio turned (`u_ld_env_rot`), the
    world direction is the studio direction turned back. Also `cube_lod`: roughness L / 6 -> level L."""
    state = _state(rotation=33.0, env_intensity=0.7)
    values = lo.frame_uniforms(state)
    frame = lo.studio_frame(state)
    rng = np.random.default_rng(11)
    dirs, rough, want = [], [], []
    for level in range(ls.CUBE_LEVELS):
        side = ls.CUBE_SIZE >> level
        faces = cube.read_back(level)
        face = int(rng.integers(0, 6))
        tx, ty = (int(v) for v in rng.integers(1, side - 1, size=2)) if side > 2 else (0, 1)
        dirs.append(frame @ lo.cube_texel_directions(face, side, corner_fix=False)[ty, tx])
        rough.append(lo.cube_level_roughness(level))
        assert lo.cube_lod(rough[-1]) == pytest.approx(level)
        want.append(0.7 * faces[face, ty, tx, :3])
    got = _ld_env_cube(cube, dirs, rough, values)
    assert _relative(got, np.array(want)) <= 2e-3, (got, want)


# -- the cube in the room's frame -------------------------------------------------------------------------------------

def test_the_cube_is_prefiltered_only_on_a_studio_content_change(gl_window):
    """AD-039 §8: rotation, intensity, exposure, a light and the camera move nothing (+0); another studio content
    (a preset) +1; back to the first +1 (one cube, no cache); the capture's second mesh draw costs no prefilter."""
    viewport = _viewport(gl_window)
    state = _state()
    viewport.set_shading("lookdev", state)
    first = _frame(gl_window, viewport)
    cube = viewport.lookdev_pass.cube
    assert cube is not None and cube.prefilters == 1 and cube.holds(STUDIO)
    assert (False, True, False, False, False, False, False, False, True) in viewport.lookdev_pass.programs
    for change in (dict(rotation=80.0), dict(env_intensity=0.4), dict(exposure=1.0),
                   dict(key=lo.StudioLight(True, 2.0, -40.0, 10.0, 4000.0, 0.3))):
        viewport.set_shading("lookdev", dataclasses.replace(state, **change))
        _frame(gl_window, viewport)
    viewport.render_mesh.camera.yaw = 1.2
    viewport.on_camera_changed(aspect=1.0)
    _frame(gl_window, viewport)
    assert cube.prefilters == 1
    portrait = preset("Portrait").studio
    viewport.set_shading("lookdev", dataclasses.replace(state, studio=portrait))
    _frame(gl_window, viewport)
    assert cube.prefilters == 2 and cube.holds(portrait)
    viewport.set_shading("lookdev", state)
    viewport.render_mesh.camera.yaw = 0.3
    viewport.on_camera_changed(aspect=1.0)
    assert np.array_equal(_frame(gl_window, viewport), first) and cube.prefilters == 3
    captured = []
    viewport.request_capture(captured.append)
    _frame(gl_window, viewport)
    assert len(captured) == 1 and cube.prefilters == 3
    _release(viewport)


def test_the_copied_cube_samples_over_many_frames(gl_window):
    """AD-039 §11.1 run 4 / 5 (the gate of the workaround): the cube is rendered, read back and uploaded, and the skin
    samples the copy - 30 frames in a row draw the same picture with no GL error, and the cube's reflection is in it."""
    viewport = _viewport(gl_window)
    viewport.set_shading("lookdev", _state())
    first = _frame(gl_window, viewport)
    for _ in range(29):
        assert np.array_equal(_frame(gl_window, viewport), first)
    viewport.set_shading("lookdev", _state(env_intensity=0.0))
    assert np.abs(first - _frame(gl_window, viewport)).max() > 20  # the reflection came from the cube
    _release(viewport)


def test_the_cube_off_draws_the_frame_before_s5_and_on_stays_close(gl_window):
    """AD-039 §8: with the cube off the program built by S7's call (`skin_sources` without the new argument) draws the
    same pixels and nothing is created on unit 8; with it on the reflection comes from the cube - the same studio, so
    the picture stays close (the split-sum differs from the analytic fit at medium roughness, §8)."""
    from pyglet.graphics.shader import Shader, ShaderProgram

    viewport = _viewport(gl_window)
    viewport.set_shading("lookdev", _state(effects=NO_CUBE))
    off = _frame(gl_window, viewport)
    passes = viewport.lookdev_pass
    assert passes.cube is None and set(passes.programs) == {(False, True, False, False, False)}
    locations = {"position": GLRenderStore.program().attributes["position"]["location"],
                 "normal": GLRenderStore.program().attributes["normal"]["location"]}
    passes.programs[(False, True, False, False, False)].delete()
    passes.programs[(False, True, False, False, False)] = ShaderProgram(
        *(Shader(src, kind) for src, kind in ls.skin_sources(locations, False, True)))
    assert np.array_equal(_frame(gl_window, viewport), off)
    viewport.set_shading("lookdev", _state())
    on = _frame(gl_window, viewport)
    lit = off.max(axis=-1) > 10
    diff = np.abs(on - off).max(axis=-1)
    assert lit.sum() > 2000 and diff[lit].mean() < 2.0 and np.percentile(diff[lit], 99) < 12, (
        diff[lit].mean(), np.percentile(diff[lit], 99))
    _release(viewport)


def test_with_the_dual_lobe_the_cube_is_read_twice(gl_window):
    """AD-039 §6 / §11.1 run 5: with the dual lobe and the cube on, the reflection mixes two lookups (roughness x 0.75
    and x 1.3); it changes the picture against the cube with one lobe and against the analytic studio's one lobe."""
    viewport = _viewport(gl_window, dataclasses.replace(GLOSSY, roughness=0.6))
    no_lights = dict(key=lo.StudioLight(False))
    viewport.set_shading("lookdev", _state(effects=CUBE_ONLY, **no_lights))
    single = _frame(gl_window, viewport)
    viewport.set_shading("lookdev", _state(effects=dataclasses.replace(CUBE_ONLY, dual_lobe=True), **no_lights))
    dual = _frame(gl_window, viewport)
    assert (False, True, False, True, False, False, False, False, True) in viewport.lookdev_pass.programs
    assert (np.abs(dual - single).max(axis=-1) > 2).sum() > 50
    _release(viewport)


def _seamless_and_unit_8() -> tuple[bool, int]:
    from pyglet import gl

    bound = gl.GLint()
    gl.glActiveTexture(gl.GL_TEXTURE0 + ls.CUBE_UNIT)
    gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_CUBE_MAP, ctypes.byref(bound))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    return bool(gl.glIsEnabled(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)), bound.value


def test_the_frame_leaves_the_seamless_flag_and_unit_8_as_found(gl_window):
    """AD-039 §2.4: seamless filtering on only around the skin draw (restored to what it was, off or on); unit 8 empty
    after the frame; unit 0 active; the default framebuffer bound."""
    from pyglet import gl

    viewport = _viewport(gl_window)
    viewport.set_shading("lookdev", _state())
    _frame(gl_window, viewport)
    assert _seamless_and_unit_8() == (False, 0)
    gl.glEnable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
    viewport.set_shading("lookdev", dataclasses.replace(_state(), studio=preset("Portrait").studio))  # a prefilter too
    _frame(gl_window, viewport)
    assert _seamless_and_unit_8() == (True, 0)
    gl.glDisable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
    active, fbo = gl.GLint(), gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
    gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(fbo))
    assert (active.value, fbo.value) == (gl.GL_TEXTURE0, 0)
    _release(viewport)


def test_prepare_lookdev_prefilters_the_wanted_studio_before_the_frame(gl_window):
    """AD-039 §8 / §2.1: the room's preparation builds the cube for the studio it set (`set_lookdev_effects(effects,
    studio)`), so the frame after draws without a prefilter; the frame before still shows the old content."""
    viewport = _viewport(gl_window)
    state = _state()
    viewport.set_lookdev_effects(state.effects, state.studio)
    assert viewport.lookdev_prepare_needed() and viewport.lookdev_cube_needed()
    viewport.prepare_lookdev()
    cube = viewport.lookdev_pass.cube
    assert cube.holds(STUDIO) and not viewport.lookdev_prepare_needed() and not viewport.lookdev_cube_needed()
    viewport.set_shading("lookdev", state)
    _frame(gl_window, viewport)
    assert cube.prefilters == 1
    portrait = preset("Portrait").studio
    viewport.set_lookdev_effects(state.effects, portrait)
    assert viewport.lookdev_cube_needed()
    _frame(gl_window, viewport)  # the frame before the preparation: the old content, no prefilter
    assert cube.prefilters == 1 and cube.holds(STUDIO)
    viewport.prepare_lookdev()
    assert cube.prefilters == 2 and cube.holds(portrait)
    viewport.set_lookdev_effects(NO_CUBE, portrait)
    assert not viewport.lookdev_cube_needed()  # the effect off: nothing to prefilter
    _release(viewport)


def test_without_a_cube_target_the_cube_is_off_with_a_status_line(gl_window, monkeypatch):
    """AD-039 §2.2: `cube_rgba16f` stubbed false - the frame equals the cube-off frame, no cube is made, the status
    line once."""
    reference = _viewport(gl_window)
    reference.set_shading("lookdev", _state(effects=NO_CUBE))
    want = _frame(gl_window, reference)
    _release(reference)
    monkeypatch.setitem(lookdev_features.CHECKS, "cube_rgba16f", lambda: False)
    viewport = _viewport(gl_window)
    viewport.set_shading("lookdev", _state())
    assert np.array_equal(_frame(gl_window, viewport), want)
    assert not viewport.lookdev_effects().cube and viewport.lookdev_pass.cube is None
    assert viewport.take_lookdev_notices() == ["LookDev: Umgebungs-Cube aus – Cube-Ziel nicht verfügbar"]
    assert viewport.take_lookdev_notices() == []
    _release(viewport)


def test_the_cube_check_passes_here(gl_window):
    gl_window.switch_to()
    assert lookdev_features._cube_rgba16f()


# -- the room: a preset switch prefilters behind the status line -----------------------------------------------------

@pytest.fixture
def cube_app(gl_window):
    from mirai.application import Application
    from tests.test_gl_posed_picking import _GL

    gl_window.switch_to()
    app = Application()
    app.init_scene("cube", **_GL)
    app.set_viewport_size(SIZE, SIZE)
    app.frame_scene()
    app._camera_changed()
    app.update_viewport(0.0)
    yield app
    if app.lookdev_open:
        app.close_lookdev()


def _app_frame(gl_window, app) -> None:
    from pyglet import gl

    gl_window.switch_to()
    app.update_viewport(0.0)
    gl.glViewport(0, 0, SIZE, SIZE)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    app.viewport.render()
    gl.glFinish()
    assert gl.glGetError() == gl.GL_NO_ERROR


def test_in_the_app_a_preset_switch_prefilters_behind_the_status_line(gl_window, cube_app):
    """AD-039 §11.1 run 5 / §2.1: the room's entry builds the cube with the programs; a preset switch (new studio
    content) shows „LookDev: Umgebung wird vorbereitet …“ for the frame before (the old cube drawn, nothing
    prefiltered in it), then prefilters once; a rotation or another light does not wait; the effect switch is saved
    view state like the others."""
    app = cube_app
    assert app.open_lookdev()
    for _ in range(4):
        _app_frame(gl_window, app)
    cube = app.viewport.lookdev_pass.cube
    assert app.viewport.shading == "lookdev" and cube is not None and cube.prefilters == 1
    assert cube.holds(app.lookdev.studio.studio)
    old = app.lookdev.studio.studio
    target = next(n for n in ("Dramatic", "Soft Studio") if preset(n).studio != old)
    assert app.set_lookdev_studio_preset(target)
    assert app.lookdev.preparing and app.status_message == "LookDev: Umgebung wird vorbereitet …"
    _app_frame(gl_window, app)  # the frame before: still the old studio and its cube
    assert app.viewport.lookdev_state.studio == old and cube.prefilters == 1
    _app_frame(gl_window, app)
    assert not app.lookdev.preparing and cube.prefilters == 2 and cube.holds(preset(target).studio)
    assert app.viewport.lookdev_state.studio == preset(target).studio
    assert "Umgebung in" in app.status_message and "vorbereitet" in app.status_message
    _app_frame(gl_window, app)
    assert cube.prefilters == 2
    assert app.set_lookdev_studio(rotation=45.0) and not app.lookdev.preparing
    assert app.set_lookdev_light("key", azimuth=10.0) and not app.lookdev.preparing
    _app_frame(gl_window, app)
    assert cube.prefilters == 2
    assert app.set_lookdev_effect("cube", False)  # its programs compile behind the status line (I-10)
    for _ in range(3):
        _app_frame(gl_window, app)
    assert not app.lookdev.preparing and not app.viewport.lookdev_state.effects.cube
    assert any(len(k) < 9 for k in app.viewport.lookdev_pass.programs) and cube.prefilters == 2
    assert app.set_lookdev_studio_preset("Portrait") and not app.lookdev.preparing  # the cube off: nothing to wait for
    _app_frame(gl_window, app)
    assert cube.prefilters == 2
