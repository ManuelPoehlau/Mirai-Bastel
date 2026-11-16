"""The eye pass in the real GL path (AD-033 §5): the GLSL against its NumPy twins (`viewport.eye_optics`), the
per-triangle cornea / sclera split and the GPU ray classes against the CPU trace, the sclera's brightness against a
Worklight object of the same colour, preview off = the Worklight's own draw, every level / reflection / refraction
compiles and draws, GL state left as found. Eye LookDev phase 3: the look's terms (parity, neutral at 0, "fast" as
before, each term where it belongs, the lid in the rest frame, calm at modelling distance).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_eye_pass.py`); skips without."""

from __future__ import annotations

import ctypes
import dataclasses
import math

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.eye_object import (DEFAULT_EYE, DEFAULT_LOOK, SCLERA_COLOUR, cornea_triangles, eye_material,  # noqa: E402
                              shell_mesh)
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import eye_optics as eo  # noqa: E402
from viewport import eye_shaders as es  # noqa: E402
from viewport.eye_pass import EyeDraw, eye_uniforms, look_uniforms, rest_rotation  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.material import SurfaceFinish  # noqa: E402
from viewport.viewport import Viewport  # noqa: E402

SIZE = 240
SCALE = 1.2
FINISH = SurfaceFinish(specular=eye_material().specular, glossiness=eye_material().glossiness)
G = eo.EyeGeometry.from_values(DEFAULT_EYE)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    win.switch_to()
    yield win
    win.close()


def _model(scale=SCALE):
    return [scale, 0, 0, 0, 0, scale, 0, 0, 0, 0, scale, 0, 0, 0, 0, 1.0]


def _scene(spec=DEFAULT_EYE, yaw=0.0, distance=6.0, pitch=0.0, model=None, rest=None):
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=distance)
    camera.set_view(math.radians(yaw), math.radians(pitch))
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=1.0)
    draw = EyeDraw(spec, None, SCLERA_COLOUR, FINISH, cornea_triangles(), rest_matrix=rest, variation=3)
    viewport.set_object_entry("eye", shell_mesh(spec), SCLERA_COLOUR, model_matrix=model or _model(), finish=FINISH,
                              eye=draw)
    return viewport, camera


def _render(gl_window, viewport) -> np.ndarray:
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
    return np.frombuffer(bytes(buf), dtype=np.uint8).reshape(SIZE, SIZE, 3)[::-1].astype(int)


def _camera_rays(camera):
    """Eye-local rays through the pixel centres (row 0 = top), the eye at the origin with uniform scale SCALE."""
    view = np.array(camera.build_view_matrix()).reshape(4, 4).T
    proj = np.array(camera.build_projection_matrix(1.0)).reshape(4, 4).T
    inv = np.linalg.inv(proj @ view)
    px = (np.arange(SIZE) + 0.5) / SIZE * 2.0 - 1.0
    x, y = np.meshgrid(px, -px)
    near = np.stack([x, y, -np.ones_like(x), np.ones_like(x)], -1) @ inv.T
    far = np.stack([x, y, np.ones_like(x), np.ones_like(x)], -1) @ inv.T
    near, far = near[..., :3] / near[..., 3:], far[..., :3] / far[..., 3:]
    eye = np.asarray(camera.eye(), dtype=np.float64) / SCALE
    return eye, eo.normalize(far - near)


def _cpu_kinds(camera, variant):
    eye, d = _camera_rays(camera)
    tr = eo.trace(eye, d, variant, G)
    hit_s, ts = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.zeros(3), 1.0)
    ps = eye + ts[..., None] * d
    hit_a, ta = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.array([0.0, 0.0, G.anterior_centre_z]),
                                G.cornea_radius)
    sclera = hit_s & (ps[..., 2] < G.limbus_z) & (~hit_a | (ts < ta) | (tr.kind == eo.MISS))
    return np.where(sclera, -1, tr.kind)


def _gl_kinds(img):
    kinds = np.full(img.shape[:2], -2)
    for kind, colour in ((eo.IRIS, (255, 0, 0)), (eo.PUPIL, (0, 255, 0)), (eo.LIMBUS, (0, 0, 255)),
                         (-1, (255, 255, 0))):
        kinds[np.all(img == colour, axis=-1)] = kind
    return kinds


@pytest.mark.parametrize("variant, yaw", [("V2", 0.0), ("V2", 40.0), ("V3", 0.0), ("V3", 40.0)])
def test_gpu_ray_classes_and_cornea_split_equal_the_cpu_trace(gl_window, variant, yaw):
    viewport, camera = _scene(yaw=yaw)
    viewport.set_eye_display(refraction=variant)
    viewport.eye_pass.debug_kind = True
    try:
        gl = _gl_kinds(_render(gl_window, viewport))
    finally:
        viewport.eye_pass.debug_kind = False
    cpu = _cpu_kinds(camera, variant)
    both = (gl >= -1) & (cpu != eo.MISS)
    assert both.sum() > 2000
    # Per-pixel ray class (and the per-triangle split cornea / sclera) agree except at the tessellated rim.
    assert np.mean(gl[both] == cpu[both]) > 0.995, variant
    assert np.sum(gl == eo.PUPIL) > 100 and np.sum(gl == eo.IRIS) > 500


def _sclera_mask(camera, margin_mm=1.5):
    eye, d = _camera_rays(camera)
    hit, t = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.zeros(3), 1.0)
    p = eye + t[..., None] * d
    return hit & (eo.sclera_u(p, G) > margin_mm * eo.MM)


def test_sclera_reads_like_a_worklight_object_of_its_colour(gl_window):
    """AD-033 §5.4: the eye's diffuse light is the Worklight's. Away from the limbus the sclera matches the same shell
    drawn by the Worklight with the same colour and finish (preview off) within a few levels (analytic vs mesh
    normals)."""
    viewport, camera = _scene(yaw=30.0)
    eye_img = _render(gl_window, viewport)
    viewport.set_eye_display(preview=False)
    worklight = _render(gl_window, viewport)
    mask = _sclera_mask(camera)
    diff = np.abs(eye_img - worklight).max(-1)[mask]
    assert mask.sum() > 3000
    assert diff.mean() <= 2.0 and np.percentile(diff, 99) <= 8, (diff.mean(), np.percentile(diff, 99))


def test_tier_full_without_a_look_draws_the_same_pixels(gl_window):
    """Eye LookDev phase 3: the tier only matters for an eye with a look; without one "full" draws as "fast"."""
    viewport, _ = _scene()
    fast = _render(gl_window, viewport)
    viewport.set_eye_display(tier="full")
    assert np.array_equal(fast, _render(gl_window, viewport))


def test_preview_off_is_the_worklight_draw(gl_window):
    viewport, _ = _scene()
    viewport.set_eye_display(preview=False)
    off = _render(gl_window, viewport)
    plain = Viewport(Mesh(), store_type=GLRenderStore)
    plain.bind_camera(viewport.render_mesh.camera)
    plain.on_camera_changed(aspect=1.0)
    plain.set_object_entry("eye", shell_mesh(DEFAULT_EYE), SCLERA_COLOUR, model_matrix=_model(), finish=FINISH)
    assert np.array_equal(off, _render(gl_window, plain))


def test_a_second_entry_on_the_same_shell_draws_the_same_eye_shifted(gl_window):
    """AD-033 §14: a morph view twin is a second viewport entry on the eye's own mesh with a shifted matrix. Both draw
    through the eye pass: the frame with the eye and its twin is the eye alone plus the twin alone."""
    spec, shift = DEFAULT_EYE, 3.0
    shell = shell_mesh(spec)
    draw = EyeDraw(spec, None, SCLERA_COLOUR, FINISH, cornea_triangles())
    moved = _model()
    moved[12] = shift

    def frame(entries):
        viewport = Viewport(Mesh(), store_type=GLRenderStore)
        camera = OrbitCamera(target=(shift / 2.0, 0.0, 0.0), distance=9.0)
        camera.set_view(math.radians(10.0), 0.0)
        viewport.bind_camera(camera)
        viewport.on_camera_changed(aspect=1.0)
        for key, matrix in entries:
            viewport.set_object_entry(key, shell, SCLERA_COLOUR, model_matrix=matrix, finish=FINISH, eye=draw)
        return _render(gl_window, viewport)

    both = frame([("eye", _model()), (("morph_view", "eye"), moved)])
    own, twin = frame([("eye", _model())]), frame([(("morph_view", "eye"), moved)])
    assert own.any() and twin.any() and not (own.any(axis=-1) & twin.any(axis=-1)).any()  # two eyes, apart
    assert np.array_equal(both, own + twin)


@pytest.mark.parametrize("level", [0, 1, 2, 3])
@pytest.mark.parametrize("reflection", ["key", "studio"])
@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_every_variant_draws_and_leaves_the_gl_state_clean(gl_window, level, reflection, variant):
    from pyglet import gl

    spec = dataclasses.replace(DEFAULT_EYE, limbus_level=level, overlap_mm=0.3, asymmetry=True,
                               fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=True)
    viewport, camera = _scene(spec, yaw=25.0)
    viewport.set_eye_display(reflection=reflection, refraction=variant)
    img = _render(gl_window, viewport)
    assert np.sum(img.max(-1) > 0) > 3000  # the eye is there
    assert not gl.glIsEnabled(gl.GL_BLEND) and not gl.glIsEnabled(gl.GL_CULL_FACE)
    assert not gl.glIsEnabled(gl.GL_DEPTH_TEST)
    unit = gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(unit))
    assert unit.value == gl.GL_TEXTURE0
    assert gl.glGetError() == gl.GL_NO_ERROR


def test_levels_change_the_limbus_and_the_reflection_adds_light(gl_window):
    images = {}
    for level in (0, 1, 3):
        viewport, camera = _scene(dataclasses.replace(DEFAULT_EYE, limbus_level=level), yaw=25.0)
        images[level] = _render(gl_window, viewport)
    assert np.any(images[0] != images[1]) and np.any(images[1] != images[3])
    viewport, camera = _scene(yaw=0.0)
    studio = _render(gl_window, viewport)
    viewport.set_eye_display(reflection="key")
    key_only = _render(gl_window, viewport)
    eye, d = _camera_rays(camera)
    cornea = eo.trace(eye, d, "V2", G).kind != eo.MISS
    assert studio[cornea].sum() > key_only[cornea].sum()


# -- GPU parity of every GLSL function against its NumPy twin ----------------------------------------------------------


class _Parity:
    WIDTH = 256

    def __init__(self, fit_values: dict | None) -> None:
        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        self.gl = gl
        self.program = ShaderProgram(*(Shader(src, kind) for src, kind in es.parity_sources(fit_values is not None)))
        self.fit_values = fit_values or {}
        def gen(fn) -> int:
            ident = gl.GLuint()
            fn(1, ctypes.byref(ident))
            return ident.value

        self.buffer, self.tex = gen(gl.glGenBuffers), gen(gl.glGenTextures)
        self.fbo, self.rbo, self.vao = gen(gl.glGenFramebuffers), gen(gl.glGenRenderbuffers), gen(gl.glGenVertexArrays)
        gl.glBindVertexArray(self.vao)
        vbo = gl.GLuint()
        gl.glGenBuffers(1, ctypes.byref(vbo))
        self.vbo = vbo.value
        tri = (gl.GLfloat * 6)(-1.0, -1.0, 3.0, -1.0, -1.0, 3.0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tri), tri, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glBindVertexArray(0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

    def run(self, func: str, inputs: np.ndarray) -> np.ndarray:
        gl = self.gl
        data = np.ascontiguousarray(inputs, dtype=np.float32).reshape(-1, 12)
        count = len(data)
        rows = -(-count // self.WIDTH)
        gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, self.buffer)
        gl.glBufferData(gl.GL_TEXTURE_BUFFER, data.nbytes, data.ctypes.data, gl.GL_STREAM_DRAW)
        gl.glActiveTexture(gl.GL_TEXTURE0 + 3)
        gl.glBindTexture(gl.GL_TEXTURE_BUFFER, self.tex)
        gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, self.buffer)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.rbo)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA32F, self.WIDTH, rows)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, self.rbo)
        gl.glViewport(0, 0, self.WIDTH, rows)
        self.program.use()
        draw = EyeDraw(dataclasses.replace(DEFAULT_EYE, overlap_mm=0.2, asymmetry=True, band_mm=1.2, strength=0.8,
                                           normal_mm=0.6, falloff=3.0, look=PARITY_LOOK, **self.fit_values),
                       None, SCLERA_COLOUR, FINISH, cornea_triangles(), variation=PARITY_VARIATION)
        values = eye_uniforms(draw)
        values.update(look_uniforms(draw))
        values.update(LIGHT)
        values.update({"u_inputs": 3, "u_width": self.WIDTH, "u_count": count, "u_func": es.PARITY_FUNCS[func]})
        for name, value in values.items():
            if name in self.program.uniforms:
                self.program[name] = value
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        out = np.zeros((rows, self.WIDTH, 4), dtype=np.float32)
        gl.glReadPixels(0, 0, self.WIDTH, rows, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data)
        gl.glBindVertexArray(0)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glBindTexture(gl.GL_TEXTURE_BUFFER, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self.program.stop()
        return out.reshape(-1, 4)[:count].astype(np.float64)

    def release(self) -> None:
        gl = self.gl
        self.program.delete()
        for fn, ident in ((gl.glDeleteBuffers, self.buffer), (gl.glDeleteBuffers, self.vbo),
                          (gl.glDeleteTextures, self.tex), (gl.glDeleteFramebuffers, self.fbo),
                          (gl.glDeleteRenderbuffers, self.rbo), (gl.glDeleteVertexArrays, self.vao)):
            fn(1, ctypes.byref(gl.GLuint(ident)))


PARITY_LOOK = dataclasses.replace(DEFAULT_LOOK, wet_sclera=0.5, irregularity_deg=0.7, irregularity_mm=1.2, seed=5,
                                  highlight_softness=0.6, lid_shadow=0.4, lid_shadow_mm=2.5, lid_band=0.8,
                                  lid_upper=0.33, lid_lower=-0.45)
PARITY_VARIATION = 17
LIGHT = {"u_key_dir": tuple(eo.normalize([0.4, 0.5, 0.75])), "u_key_color": (0.9, 0.88, 0.85), "u_key_wrap": 0.2,
         "u_fill_dir": tuple(eo.normalize([-0.6, 0.1, 0.5])), "u_fill_color": (0.3, 0.32, 0.35), "u_fill_wrap": 0.5,
         "u_ambient": 0.12}
N = 2048


def _pack(*cols) -> np.ndarray:
    data = np.zeros((len(cols[0]), 12))
    k = 0
    for col in cols:
        col = np.asarray(col, dtype=np.float64).reshape(len(data), -1)
        data[:, k:k + col.shape[1]] = col
        k += col.shape[1]
    return data.astype(np.float32)


def _f32(x):
    return np.asarray(x, dtype=np.float32).astype(np.float64)


def _eye_rays(rng, n):
    az, off, dist = rng.uniform(0, 2 * np.pi, n), np.radians(rng.uniform(0, 80, n)), rng.uniform(2.0, 4.0, n)
    eye = np.stack([dist * np.sin(off) * np.cos(az), dist * np.sin(off) * np.sin(az), dist * np.cos(off)], -1)
    r = G.limbus_radius * np.sqrt(rng.uniform(0, 1, n))
    phi = rng.uniform(0, 2 * np.pi, n)
    target = np.stack([r * np.cos(phi), r * np.sin(phi), G.anterior_z(r)], -1)
    return eye, eo.normalize(target - eye)


def _stable(eye, d, variant):
    base = eo.trace(eye, d, variant, G).kind
    ok = np.ones(len(d), dtype=bool)
    for axis in range(3):
        for sign in (-1.0, 1.0):
            dd = d.copy()
            dd[:, axis] += sign * 2e-5
            ok &= eo.trace(eye, eo.normalize(dd), variant, G).kind == base
    return ok


@pytest.fixture(scope="module")
def parity(gl_window):
    passes = {fit: _Parity(dict(fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=True) if fit else None)
              for fit in (False, True)}
    yield passes
    for p in passes.values():
        p.release()


@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_trace_glsl_matches_numpy(parity, variant):
    rng = np.random.default_rng(3)
    eye, d = _eye_rays(rng, N)
    x = _pack(eye, np.zeros(N), d, np.zeros(N), np.full(N, 2.0 if variant == "V2" else 3.0))
    a = _f32(x)
    e, dd = a[:, 0:3], eo.normalize(a[:, 4:7])
    tr = eo.trace(e, dd, variant, G)
    ok = _stable(e, dd, variant) & (tr.kind != eo.MISS)
    hit = parity[False].run("trace_hit", x)
    entry = parity[False].run("trace_entry", x)
    assert ok.sum() > 0.9 * N
    assert np.array_equal(np.round(hit[ok, 3]), tr.kind[ok])
    assert np.abs(hit[ok, :3] - tr.hit[ok]).max() < 2e-4
    assert np.abs(entry[ok, :3] - tr.entry[ok]).max() < 2e-4
    assert np.abs(entry[ok, 3] - tr.transmit_inner[ok]).max() < 2e-4


def test_iris_uv_glsl_matches_numpy_planar_and_fitted(parity):
    rng = np.random.default_rng(5)
    r = G.iris_radius * np.sqrt(rng.uniform(0, 1.3, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    x = _pack(np.stack([r * np.cos(phi), r * np.sin(phi)], -1))
    a = _f32(x)
    spec = dataclasses.replace(DEFAULT_EYE, fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=True)
    assert np.abs(parity[False].run("iris_st", x)[:, :2] - eo.iris_uv(a[:, :2], G)).max() < 2e-6
    knots = eo.fit_knots(spec, G)
    assert np.abs(parity[True].run("iris_st", x)[:, :2] - eo.iris_uv(a[:, :2], G, knots)).max() < 2e-6


def test_limbus_functions_glsl_match_numpy(parity):
    rng = np.random.default_rng(11)
    spec = dataclasses.replace(DEFAULT_EYE, overlap_mm=0.2, asymmetry=True, band_mm=1.2, strength=0.8,
                               normal_mm=0.6, falloff=3.0)
    band, u0 = spec.band_mm * eo.MM, eo.limbus_u0(G)
    amount, base = eo.ASYM_MM * eo.MM, spec.overlap_mm * eo.MM
    theta = np.radians(rng.uniform(20, 45, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    p = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)
    x = _pack(p)
    a = _f32(x)
    got = parity[False].run("coords", x)
    assert np.abs(got[:, 0] - eo.sclera_u(a[:, :3], G)).max() < 5e-6
    assert np.abs(got[:, 1] - eo.cornea_u(a[:, :3], G)).max() < 5e-6
    assert np.abs(got[:, 2] - eo.asym_shift(a[:, :3], amount, base)).max() < 5e-6
    u = rng.uniform(-0.06, 0.15, N)
    shift = rng.choice([0.0, base, base + amount], N)
    x = _pack(u, u - 0.01, shift, rng.uniform(-0.06, 0.15, N))
    a = _f32(x)
    got = parity[False].run("weights", x)
    assert np.abs(got[:, 0] - eo.colour_weight(a[:, 0], band, u0)).max() < 2e-5
    assert np.abs(got[:, 1] - eo.iris_cover(a[:, 1], a[:, 2], amount + base, u0)).max() < 2e-5
    assert np.abs(got[:, 2] - eo.transmission(a[:, 3], band, spec.falloff, u0)).max() < 2e-5
    nc = eo.normalize(p - np.array([0, 0, G.anterior_centre_z]))
    w = rng.uniform(-0.08, 0.08, N)
    x = _pack(nc, np.zeros(N), p, np.zeros(N), w)
    a = _f32(x)
    got = parity[False].run("normal_blend", x)
    ref = eo.normal_blend(eo.normalize(a[:, :3]), eo.normalize(a[:, 4:7]), a[:, 8], spec.normal_mm * eo.MM)
    assert np.abs(got[:, :3] - ref).max() < 5e-6


def test_sclera_through_studio_and_worklight_light_glsl_match_numpy(parity):
    rng = np.random.default_rng(13)
    theta = np.radians(rng.uniform(20, 45, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    p = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)
    az, off, dist = rng.uniform(0, 2 * np.pi, N), np.radians(rng.uniform(0, 70, N)), rng.uniform(2, 4, N)
    eye = np.stack([dist * np.sin(off) * np.cos(az), dist * np.sin(off) * np.sin(az), dist * np.cos(off)], -1)
    d = eo.normalize(p - eye)
    x = _pack(p, np.zeros(N), d, np.zeros(N), p)
    a = _f32(x)
    hit, point = eo.sclera_through(a[:, :3], eo.normalize(a[:, 4:7]), eo.normalize(a[:, 8:11]), G)
    got = parity[False].run("sclera_through", x)
    stable = np.ones(N, dtype=bool)
    for k in range(3):
        for sign in (-1.0, 1.0):
            dd = a[:, 4:7].copy()
            dd[:, k] += sign * 2e-5
            stable &= eo.sclera_through(a[:, :3], eo.normalize(dd), eo.normalize(a[:, 8:11]), G)[0] == hit
    assert stable.sum() > 0.9 * N
    assert np.array_equal(got[stable, 3] > 0.5, hit[stable])
    both = stable & hit
    assert np.abs(got[both, :3] - point[both]).max() < 2e-4
    dirs = eo.normalize(rng.normal(size=(N, 3)))
    rough = rng.uniform(0.02, 0.6, N)
    x = _pack(dirs, rough)
    a = _f32(x)
    got = parity[False].run("td_env", x)
    ref = np.stack([eo.td_env(a[i, :3], a[i, 3]) for i in range(N)])
    assert np.abs(got[:, :3] - ref).max() < 2e-3 * max(1.0, ref.max())
    x = _pack(dirs)
    a = _f32(x)
    got = parity[False].run("worklight_light", x)
    assert np.abs(got[:, :3] - eo.worklight_light(eo.normalize(a[:, :3]), LIGHT)).max() < 2e-6


def test_colour_source_image_takes_the_iris_rings_colour(gl_window, tmp_path):
    """P1c's switch in production: "image" = the mean of the iris image's outer ring (here a red ring)."""
    from pyglet import image

    size = 128
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    rho = np.hypot(x, y)
    rgb = np.full((size, size, 3), 0.4)
    rgb[(rho > 0.70) & (rho < 0.95)] = (0.9, 0.05, 0.05)
    path = tmp_path / "iris.png"
    image.ImageData(size, size, "RGB", (rgb * 255).astype(np.uint8).tobytes()).save(str(path))
    spec = dataclasses.replace(DEFAULT_EYE, limbus_level=1, fit_pupil=0.2, fit_limbus=0.88, hold_outer_color=True)
    viewport, _ = _scene(spec)
    draw = EyeDraw(spec, str(path), SCLERA_COLOUR, FINISH, cornea_triangles())
    assert viewport.eye_pass.limbal_colour(draw) == tuple(spec.limbal_colour)  # "shader": the eye's own
    image_draw = EyeDraw(dataclasses.replace(spec, colour_source="image"), str(path), SCLERA_COLOUR, FINISH,
                         cornea_triangles())
    red = viewport.eye_pass.limbal_colour(image_draw)
    assert red[0] > 0.8 and red[1] < 0.15
    missing = EyeDraw(image_draw.spec, str(tmp_path / "none.png"), SCLERA_COLOUR, FINISH, cornea_triangles())
    assert viewport.eye_pass.limbal_colour(missing) == tuple(spec.limbal_colour)


# -- Eye LookDev phase 3: the look (`core.EyeLook`; Manu I-5 / I-8 / I-10, 2026-11-16) --------------------------------


def test_look_functions_glsl_match_numpy(parity):
    """GPU parity of every new function against its `eye_optics` twin (the frozen lab has none: these twins are the
    reference)."""
    rng = np.random.default_rng(29)
    v = eo.look_values(PARITY_LOOK, PARITY_VARIATION)
    # film_uv over the cornea, the limbus and the sclera (the apex included)
    theta = np.radians(rng.uniform(0, 80, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    theta[:8] = 0.0
    p = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)
    x = _pack(p)
    a = _f32(x)
    got = parity[False].run("film_uv", x)
    assert np.abs(got[:, :2] - eo.film_uv(a[:, :3], v["noise_scale"], v["noise_offset"])).max() < 5e-6
    # film_normal
    n = eo.normalize(p + rng.normal(scale=0.1, size=p.shape))
    g = rng.uniform(-3.0, 3.0, (N, 2))
    x = _pack(n, np.zeros(N), p, np.zeros(N), g)
    a = _f32(x)
    got = parity[False].run("film_normal", x)
    ref = eo.film_normal(eo.normalize(a[:, :3]), a[:, 4:7], a[:, 8:10], v["tilt"])
    assert np.abs(got[:, :3] - ref).max() < 5e-6
    # film_roughness and lid_shadow_weight
    base, nb = rng.uniform(0.03, 0.2, N), rng.uniform(-1, 1, N)
    p_rest = np.stack([rng.uniform(-0.6, 0.6, N), rng.uniform(-0.9, 0.9, N), rng.uniform(0.3, 1.0, N)], -1)
    x = _pack(base, nb, np.zeros((N, 2)), p_rest)
    a = _f32(x)
    got = parity[False].run("film_roughness_shadow", x)
    assert np.abs(got[:, 0] - eo.film_roughness(a[:, 0], a[:, 1], v["rough_s"])).max() < 2e-7
    assert np.abs(got[:, 1] - eo.lid_shadow_weight(a[:, 4:7], v["lid"])).max() < 2e-5
    # lid_occlusion: front points of the eyeball, every direction (backward ones included)
    theta = np.radians(rng.uniform(0, 60, N))
    p = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)
    r = eo.normalize(rng.normal(size=(N, 3)))
    rough = rng.uniform(0.03, 0.2, N)
    x = _pack(p, np.zeros(N), r, np.zeros(N), rough)
    a = _f32(x)
    defined = np.abs(a[:, 5]) + np.abs(a[:, 6]) > 1e-3
    got = parity[False].run("lid_occlusion", x)
    ref = eo.lid_occlusion(a[:, :3], eo.normalize(a[:, 4:7]), a[:, 8], v["lid"], G)
    assert np.abs(got[defined, 0] - ref[defined]).max() < 1e-4
    assert 0.1 < ref.mean() < 0.9  # both sides of the band are sampled
    # area_key: directions around the key, the degenerate frame (key along up) included
    c = eo.normalize(rng.normal(size=(N, 3)))
    up_ref = eo.normalize(rng.normal(size=(N, 3)))
    up_ref[:16] = c[:16]
    r = eo.normalize(c + rng.normal(scale=0.12, size=(N, 3)))
    rough = rng.uniform(0.03, 0.15, N)
    x = _pack(r, rough, c, np.zeros(N), up_ref)
    a = _f32(x)
    got = parity[False].run("area_key", x)
    ref = eo.area_key(eo.normalize(a[:, :3]), eo.normalize(a[:, 4:7]), eo.normalize(a[:, 8:11]), a[:, 3],
                      v["soft_half"], v["soft_radiance"])
    assert ref.max() > 10.0 and np.abs(got[:, 0] - ref).max() < 2e-3 * ref.max()


def test_film_noise_is_deterministic_tileable_and_normalized():
    data = eo.film_noise()
    assert data.shape == (eo.NOISE_SIZE, eo.NOISE_SIZE, 3) and data.dtype == np.uint8
    assert np.array_equal(data, eo.film_noise())
    g = eo.film_decode(data / 255.0)
    assert math.sqrt(float(np.mean(g[..., 0] ** 2 + g[..., 1] ** 2))) == pytest.approx(1.0, abs=0.02)
    assert abs(g[..., 0].mean()) < 0.02 and abs(g[..., 1].mean()) < 0.02 and np.abs(g[..., 2]).max() <= 1.0
    # tileable: the step across the seam is no larger than the steps inside
    steps = np.abs(np.diff(g[..., 0], axis=1)).max()
    assert np.abs(g[:, 0, 0] - g[:, -1, 0]).max() <= steps + 1e-9
    assert eo.noise_offset(3, 0) != eo.noise_offset(4, 0) != eo.noise_offset(3, 1)
    assert all(0.0 <= c < 1.0 for c in eo.noise_offset(2 ** 31 - 1, 2 ** 31 - 1))


L3_EYE = dataclasses.replace(DEFAULT_EYE, limbus_level=3, overlap_mm=0.41, asymmetry=True)


def _with(spec=L3_EYE, **look):
    return dataclasses.replace(spec, look=dataclasses.replace(DEFAULT_LOOK, **look))


def _full(gl_window, spec, reflection="studio", force=False, **scene):
    viewport, camera = _scene(spec, **scene)
    viewport.set_eye_display(tier="full", reflection=reflection)
    viewport.eye_pass.force_look = force
    try:
        return _render(gl_window, viewport), camera
    finally:
        viewport.eye_pass.force_look = False


def _regions(camera, margin=2):
    """(cornea, sclera) pixel masks from the CPU trace, `margin` pixels away from every class boundary."""
    kinds = _cpu_kinds(camera, "V2")
    cornea, sclera = kinds > 0, kinds == -1

    def erode(mask):
        out = mask.copy()
        for axis in (0, 1):
            for shift in range(1, margin + 1):
                out &= np.roll(mask, shift, axis) & np.roll(mask, -shift, axis)
        return out

    return erode(cornea), erode(sclera)


def test_fast_tier_ignores_the_look(gl_window):
    look = _with(wet_sclera=0.7, irregularity_deg=0.5, highlight_softness=0.5, lid_shadow=0.35, lid_band=0.8)
    plain, _ = _scene(L3_EYE, yaw=20.0)
    viewport, _ = _scene(look, yaw=20.0)  # the tier is "fast" by default
    assert np.array_equal(_render(gl_window, plain), _render(gl_window, viewport))


@pytest.mark.parametrize("reflection", ["studio", "key"])
@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_every_look_term_at_zero_is_neutral_in_the_look_program(gl_window, reflection, variant):
    """§H row 3: all amounts at 0 -> the same pixels. Normally such an eye is not drawn with the LOOK program at all
    (`uses_look`); forced into it, every term must still be exactly neutral."""
    spec = dataclasses.replace(L3_EYE, fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=True)
    viewport, _ = _scene(spec, yaw=25.0)
    viewport.set_eye_display(tier="full", reflection=reflection, refraction=variant)
    plain = _render(gl_window, viewport)
    viewport, _ = _scene(dataclasses.replace(spec, look=DEFAULT_LOOK), yaw=25.0)
    viewport.set_eye_display(tier="full", reflection=reflection, refraction=variant)
    viewport.eye_pass.force_look = True
    assert np.array_equal(plain, _render(gl_window, viewport))


def test_wet_sclera_changes_only_the_sclera(gl_window):
    plain, camera = _full(gl_window, L3_EYE, yaw=20.0)
    wet, _ = _full(gl_window, _with(wet_sclera=1.0), yaw=20.0)
    cornea, sclera = _regions(camera)
    assert np.array_equal(wet[cornea], plain[cornea])
    diff = np.abs(wet - plain).max(-1)[sclera]
    assert (diff > 2).mean() > 0.3  # the studio's reflection continues over the sclera


def test_irregularity_changes_only_the_corneas_reflection(gl_window):
    plain, camera = _full(gl_window, L3_EYE, yaw=0.0, distance=4.0)
    rough, _ = _full(gl_window, _with(irregularity_deg=1.0), yaw=0.0, distance=4.0)
    cornea, sclera = _regions(camera)
    assert np.array_equal(rough[sclera], plain[sclera])  # a dry sclera has no film to disturb
    assert (np.abs(rough - plain).max(-1)[cornea] > 3).sum() > 50


def test_irregularity_does_not_sparkle_at_modelling_distance(gl_window):
    """§H row 3 "no shimmer in an orbit, at modelling distance no noise, no sparkle": the noise is mip-mapped, so with
    the eye small on screen the irregularity adds no frame-to-frame flicker while the camera orbits in small steps (it
    only shifts the mean roughness). Measured in the container: +0.01-0.03 grey levels per frame (2026-11-16)."""
    def flicker(look, distance, steps=8, step=0.25):
        frames = [_full(gl_window, look, distance=distance, yaw=10.0 + k * step, pitch=5.0) for k in range(steps)]
        eye = _cpu_kinds(frames[-1][1], "V2") != eo.MISS
        return np.mean([np.abs(frames[k + 1][0] - frames[k][0]).max(-1)[eye].mean() for k in range(steps - 1)])

    for distance in (25.0, 40.0):  # the eye about 20-30 pixels across
        plain = flicker(_with(wet_sclera=1.0), distance)
        for size in (1.5, 0.6):
            rough = flicker(_with(wet_sclera=1.0, irregularity_deg=1.0, irregularity_mm=size), distance)
            assert rough <= plain + 0.1, (distance, size, plain, rough)


def _sclera_points(camera, rotation=np.eye(3)):
    """Eye-local points (the drawn frame) on the sclera per pixel, and the pixels that see the sclera away from the
    limbus. `rotation` is the eye's drawn rotation (world = SCALE * rotation @ local)."""
    eye, d = _camera_rays(camera)
    hit, t = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.zeros(3), 1.0)
    world = eye + t[..., None] * d  # in units of SCALE
    local = world @ rotation  # rotation.T @ world per pixel
    return local, hit & (eo.sclera_u(local, G) > 2.0 * eo.MM)


def test_lid_shadow_darkens_only_near_and_above_the_upper_lid(gl_window):
    look = _with(DEFAULT_EYE, lid_shadow=0.6)
    plain, camera = _full(gl_window, DEFAULT_EYE, yaw=15.0, pitch=10.0)
    shaded, _ = _full(gl_window, look, yaw=15.0, pitch=10.0)
    points, sclera = _sclera_points(camera)
    weight = eo.lid_shadow_weight(points, (DEFAULT_LOOK.lid_upper, DEFAULT_LOOK.lid_lower,
                                           DEFAULT_LOOK.lid_shadow_mm * eo.MM))
    below = sclera & (weight == 0.0)
    above = sclera & (weight > 0.9)
    assert below.sum() > 1000 and above.sum() > 500
    assert np.array_equal(shaded[below], plain[below])
    assert np.all(shaded[above] <= plain[above]) and (plain[above] - shaded[above]).mean() > 10


def test_lid_band_only_darkens_the_reflection_and_from_above(gl_window):
    plain, camera = _full(gl_window, L3_EYE, yaw=0.0, distance=4.0)
    band, _ = _full(gl_window, _with(lid_band=1.0), yaw=0.0, distance=4.0)
    assert np.all(band <= plain)
    darker = np.argwhere((plain - band).max(-1) > 3)
    assert len(darker) > 50
    assert darker[:, 0].mean() < SIZE / 2  # the upper lid's band: in the upper half of the cornea


def test_lid_stays_with_the_head_while_the_eye_turns(gl_window):
    """I-10 / assessment §C roadmap #3: the lid is defined in the eye's rest frame, so an eye turned by the gaze keeps
    its shadow where the head's lid is. Sclera pixels far from the limbus look the same whichever way an L0 eye turns;
    with the rest frame the shaded pixels agree too - drawn without it (rest = turned), the shadow would move."""
    angle = math.radians(-20.0)  # about +X: the eye looks up
    rot = np.array([[1, 0, 0], [0, math.cos(angle), -math.sin(angle)], [0, math.sin(angle), math.cos(angle)]])
    turned = np.eye(4)
    turned[:3, :3] = SCALE * rot
    turned_model = list(turned.T.ravel())
    look = _with(DEFAULT_EYE, lid_shadow=0.8, lid_shadow_mm=4.0)
    kw = dict(yaw=10.0, pitch=5.0)
    own, camera = _full(gl_window, look, **kw)
    with_rest, _ = _full(gl_window, look, model=turned_model, rest=tuple(_model()), **kw)
    without_rest, _ = _full(gl_window, look, model=turned_model, rest=None, **kw)
    plain_own, _ = _full(gl_window, DEFAULT_EYE, **kw)
    plain_turned, _ = _full(gl_window, DEFAULT_EYE, model=turned_model, **kw)
    _, sclera_own = _sclera_points(camera)
    _, sclera_turned = _sclera_points(camera, rot)
    # where the unshaded eyes agree (a few pixels on the shells' different triangle seams do not)
    both = sclera_own & sclera_turned & (np.abs(plain_turned - plain_own).max(-1) <= 1)
    assert both.sum() > 2000
    assert np.abs(with_rest[both] - own[both]).max() <= 2
    assert np.abs(without_rest[both] - own[both]).max() > 20
    m = np.asarray(rest_rotation(EyeDraw(look, None, SCLERA_COLOUR, FINISH, 0, rest_matrix=tuple(_model())),
                                 turned_model)).reshape(3, 3).T
    assert np.allclose(m, rot, atol=1e-12)


def test_soft_highlight_spreads_the_keys_peak(gl_window):
    """I-8: in the key-only reflection the point highlight is a near-white dot; softened it is broader and its peak
    lower, at the same place."""
    point, camera = _full(gl_window, L3_EYE, reflection="key", distance=4.0)
    soft, _ = _full(gl_window, _with(highlight_softness=1.0), reflection="key", distance=4.0)
    cornea, _ = _regions(camera, margin=1)
    lum_point, lum_soft = point.mean(-1), soft.mean(-1)
    peak = np.unravel_index(np.argmax(np.where(cornea, lum_point, -1)), lum_point.shape)
    assert lum_point[peak] >= 245 and lum_soft[cornea].max() < lum_point[peak] - 20
    gain_soft = (lum_soft - lum_point)[cornea]
    assert (gain_soft > 10).sum() > 5 * ((lum_point[cornea] > 240).sum())  # broader than the dot
    centre = np.argwhere(np.where(cornea, lum_soft, -1) >= lum_soft[cornea].max() - 5).mean(0)
    assert np.hypot(*(centre - np.asarray(peak))) < 0.08 * SIZE  # still at the key


@pytest.mark.parametrize("level", [0, 3])
@pytest.mark.parametrize("reflection", ["key", "studio"])
@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_look_programs_draw_and_leave_the_gl_state_clean(gl_window, level, reflection, variant):
    from pyglet import gl

    spec = dataclasses.replace(_with(wet_sclera=0.7, irregularity_deg=0.5, highlight_softness=0.5, lid_shadow=0.3,
                                     lid_band=0.8), limbus_level=level, fit_pupil=0.22, fit_limbus=0.88)
    viewport, _ = _scene(spec, yaw=25.0)
    viewport.set_eye_display(tier="full", reflection=reflection, refraction=variant)
    img = _render(gl_window, viewport)
    assert np.sum(img.max(-1) > 0) > 3000
    assert not gl.glIsEnabled(gl.GL_BLEND) and not gl.glIsEnabled(gl.GL_CULL_FACE)
    unit = gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(unit))
    assert unit.value == gl.GL_TEXTURE0
    noise = viewport.eye_pass._noise
    assert noise is not None
    gl.glBindTexture(noise.target, noise.id)
    params = {}
    for name in ("GL_TEXTURE_WRAP_S", "GL_TEXTURE_WRAP_T", "GL_TEXTURE_MIN_FILTER"):
        value = gl.GLint()
        gl.glGetTexParameteriv(noise.target, getattr(gl, name), ctypes.byref(value))
        params[name] = value.value
    gl.glBindTexture(noise.target, 0)
    assert params == {"GL_TEXTURE_WRAP_S": gl.GL_REPEAT, "GL_TEXTURE_WRAP_T": gl.GL_REPEAT,
                      "GL_TEXTURE_MIN_FILTER": gl.GL_LINEAR_MIPMAP_LINEAR}
    assert gl.glGetError() == gl.GL_NO_ERROR
