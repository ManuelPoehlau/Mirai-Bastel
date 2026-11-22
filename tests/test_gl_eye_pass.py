"""The eye pass in the real GL path (AD-033 §5): the GLSL against its NumPy twins (`viewport.eye_optics`), the
per-triangle cornea / sclera split and the GPU ray classes against the CPU trace, the sclera's brightness against a
Worklight object of the same colour, preview off = the Worklight's own draw, every level / reflection / refraction
compiles and draws, GL state left as found. Eye LookDev phase 3: the look's terms (parity, neutral at 0, "fast" as
before, each term where it belongs, the lid in the rest frame, calm at modelling distance). Phase 4: the iris's terms
(parity, neutral at 0, "fast" and phase 3 as before, the crescent opposite the key, the rim shadow on the key's side,
relief and pupil edge only where they belong).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_eye_pass.py`); skips without."""

from __future__ import annotations

import ctypes
import os
import tempfile
import dataclasses
import math

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.eye_object import (DEFAULT_EYE, DEFAULT_IRIS, DEFAULT_LOOK, SCLERA_COLOUR, cornea_triangles,  # noqa: E402
                              eye_material, shell_mesh)
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import eye_optics as eo  # noqa: E402
from viewport import eye_shaders as es  # noqa: E402
from viewport.eye_pass import EyeDraw, eye_uniforms, iris_uniforms, look_uniforms, rest_rotation  # noqa: E402
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


def _scene(spec=DEFAULT_EYE, yaw=0.0, distance=6.0, pitch=0.0, model=None, rest=None, texture=None):
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=distance)
    camera.set_view(math.radians(yaw), math.radians(pitch))
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=1.0)
    draw = EyeDraw(spec, texture, SCLERA_COLOUR, FINISH, cornea_triangles(), rest_matrix=rest, variation=3)
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

        from viewport.gl_render_store import _register_sampler_buffer_uniform

        _register_sampler_buffer_uniform()  # `u_inputs`; else only registered once a Worklight program was built
        self.gl = gl
        self.program = ShaderProgram(*(Shader(src, kind) for src, kind in es.parity_sources(fit_values is not None)))
        self.fit_values = fit_values or {}
        self.crescent = None  # test hook: another `u_crescent`
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
        values.update(iris_uniforms(draw, _model(1.0), LIGHT["u_key_dir"], 512))
        if self.crescent is not None:
            values["u_crescent"] = self.crescent
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


PARITY_IRIS = dataclasses.replace(DEFAULT_IRIS, light=0.8, crescent=1.2, rim_shadow=0.7, rim_shadow_mm=0.5,
                                  relief=0.6, pupil_edge_mm=0.15, pupil_margin=0.5)
PARITY_LOOK = dataclasses.replace(DEFAULT_LOOK, wet_sclera=0.5, irregularity_deg=0.7, irregularity_mm=1.2, seed=5,
                                  highlight_softness=0.6, lid_shadow=0.4, lid_shadow_mm=2.5, lid_band=0.8,
                                  lid_upper=0.33, lid_lower=-0.45, iris=PARITY_IRIS)
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


# -- Eye LookDev phase 4: the iris (`core.EyeIris`; Manu 2026-11-16 "1 go (v11), 2 go") ------------------------------

SIDE_KEY = (40.0, 0.0)  # camera-relative azimuth / elevation in degrees: the key from the side, as after an `L`-drag


def _iris(spec=DEFAULT_EYE, **values):
    return dataclasses.replace(spec, look=dataclasses.replace(DEFAULT_LOOK, iris=dataclasses.replace(DEFAULT_IRIS,
                                                                                                     **values)))


def _iris_full(gl_window, spec, key=SIDE_KEY, force=False, **scene):
    from viewport.light_rig import LightRig

    viewport, camera = _scene(spec, **scene)
    viewport.set_eye_display(tier="full")
    viewport.set_light(LightRig(key_azimuth=key[0], key_elevation=key[1]))
    viewport.eye_pass.force_look = viewport.eye_pass.force_iris = force
    try:
        return _render(gl_window, viewport), camera, viewport.light_uniforms()
    finally:
        viewport.eye_pass.force_look = viewport.eye_pass.force_iris = False


def test_iris_functions_glsl_match_numpy(parity):
    """GPU parity of every phase 4 function against its `eye_optics` twin."""
    rng = np.random.default_rng(41)
    v = eo.iris_values(PARITY_IRIS, G)
    # the key's path and terms: iris points (inside the limbus and under the sclera), keys from the front hemisphere
    r = G.iris_radius * np.sqrt(rng.uniform(0, 1, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    hit = np.stack([r * np.cos(phi), r * np.sin(phi), G.iris_a + G.iris_b * r], -1)
    off, az = np.radians(rng.uniform(0, 70, N)), rng.uniform(0, 2 * np.pi, N)
    key = np.stack([np.sin(off) * np.cos(az), np.sin(off) * np.sin(az), np.cos(off)], -1)
    x = _pack(hit, np.zeros(N), key)
    a = _f32(x)
    hit32, key32 = a[:, :3], eo.normalize(a[:, 4:7])
    ok, _e, d, _cos, aperture, _phi = eo.iris_light_path(hit32, key32, G)
    got = parity[False].run("iris_light_path", x)
    assert np.array_equal(got[:, 3] >= 0.0, ok)
    # float32 secant steps: the direction to 1e-4 rad
    assert np.abs(got[ok, :3] - d[ok]).max() < 3e-4 and np.abs(got[ok, 3] - aperture[ok]).max() < 3e-4
    _d, trans, conc, shadow = eo.iris_key_terms(hit32, key32, v["rim_width"], G)
    got = parity[False].run("iris_key_terms", x)
    assert np.abs(got[:, 0] - trans).max() < 2e-5 and np.abs(got[:, 2] - shadow).max() < 2e-3
    assert np.abs(got[:, 1] - conc).max() < 5e-3  # a finite difference in float32: 1e-5 of the entry spacing
    assert conc.max() > 1.3 and conc.min() < 0.9 and 0.05 < shadow.mean() < 0.95  # both ends are sampled
    parity[False].crescent = 0.0  # without the crescent the neighbours are skipped: C = 1, the rest the same
    got = parity[False].run("iris_key_terms", x)
    parity[False].crescent = None
    assert np.all(got[:, 1] == 1.0) and np.abs(got[:, 0] - trans).max() < 2e-5
    _d, _t, flat, _s = eo.iris_key_terms(hit32, key32, v["rim_width"], G, concentration=False)
    assert np.all(flat == 1.0)
    # relief_normal and pupil_weights
    grad = rng.uniform(-2.0, 2.0, (N, 2))
    x = _pack(hit, np.zeros(N), grad)
    a = _f32(x)
    got = parity[False].run("relief_normal", x)
    assert np.abs(got[:, :3] - eo.relief_normal(a[:, :3], a[:, 4:6], G)).max() < 5e-6
    radius = rng.uniform(0.5, 2.0, N) * G.pupil_radius
    width = np.where(rng.uniform(0, 1, N) < 0.2, 0.0, rng.uniform(0.001, 0.03, N))
    x = _pack(radius, width)
    a = _f32(x)
    got = parity[False].run("pupil_weights", x)
    pupil, margin = eo.pupil_weights(a[:, 0], a[:, 1], v["margin_width"], G)
    assert np.abs(got[:, 0] - pupil).max() < 2e-4 and np.abs(got[:, 1] - margin).max() < 2e-4


def test_fast_tier_and_phase_3_ignore_the_iris(gl_window):
    """The standing rule: "fast" draws as before; a look without iris values draws with the program of phase 3, whose
    source has no iris code (and is character for character the one of phase 3 - checked against that commit while
    building)."""
    iris = _iris(L3_EYE, light=1.0, crescent=1.0, rim_shadow=0.8, relief=0.5, pupil_edge_mm=0.1, pupil_margin=0.5)
    plain, _ = _scene(L3_EYE, yaw=20.0)
    viewport, _ = _scene(iris, yaw=20.0)  # the tier is "fast" by default
    assert np.array_equal(_render(gl_window, plain), _render(gl_window, viewport))
    locations = {"position": 0, "normal": 1}
    for look in (False, True):
        source = es.shell_sources(locations, "V2", 3, "studio", True, look=look)[1][0]
        assert "#define IRIS\n" not in source and "iris_lit" not in source and "u_relief" not in source
    assert "iris_lit" not in es.shell_sources(locations, "V2", 3, "studio", True, look=False, iris=True)[1][0]


@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_every_iris_term_at_zero_is_neutral_in_the_iris_program(gl_window, variant):
    """§H row 4: all iris amounts at 0 -> the same pixels, forced into the IRIS program (with an image, its fit and
    the L3 paths behind the limbus)."""
    from pyglet import image

    size = 64
    rgb = np.random.default_rng(3).uniform(0.2, 0.8, (size, size, 4))
    rgb[..., 3] = 0.3  # an alpha that would tilt the normal if the relief were on
    path = os.path.join(tempfile.mkdtemp(), "iris.png")
    image.ImageData(size, size, "RGBA", (rgb * 255).astype(np.uint8).tobytes()).save(path)
    spec = dataclasses.replace(L3_EYE, fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=True)
    plain, _, _ = _iris_full(gl_window, spec, yaw=25.0, texture=path)
    forced, _, _ = _iris_full(gl_window, _iris(spec, relief_source="alpha"), force=True, yaw=25.0, texture=path)
    assert np.array_equal(plain, forced)
    viewport, _ = _scene(spec, yaw=25.0, texture=path)
    viewport.set_eye_display(tier="full", refraction=variant)
    reference = _render(gl_window, viewport)
    viewport, _ = _scene(_iris(spec), yaw=25.0, texture=path)
    viewport.set_eye_display(tier="full", refraction=variant)
    viewport.eye_pass.force_look = viewport.eye_pass.force_iris = True
    assert np.array_equal(reference, _render(gl_window, viewport))


def _key_side(camera, light) -> float:
    """+1 when the key lights the eye from the image's right, -1 from its left."""
    view = np.array(camera.build_view_matrix()).reshape(4, 4).T[:3, :3]
    return float(np.sign((view @ np.asarray(light["u_key_dir"]))[0]))


def _iris_pixels(camera):
    kinds = _cpu_kinds(camera, "V2")
    iris = kinds == eo.IRIS
    out = iris.copy()
    for axis in (0, 1):
        for shift in (1, 2):
            out &= np.roll(iris, shift, axis) & np.roll(iris, -shift, axis)
    return out


def test_iris_light_changes_only_the_iris_and_the_crescent_lies_opposite_the_key(gl_window):
    """Roadmap #4 / §H row 4 "the crescent moves opposite the highlight": with the key from the side, the key through
    the cornea (refracted and focused) brightens the iris's far side more than its near side, for a key from either
    side; the sclera is untouched (L0: no iris behind the limbus). The physics is checked against a forward ray trace in
    `test_eye_iris.py`."""
    kw = dict(distance=4.0)
    plain, camera, light = _iris_full(gl_window, DEFAULT_EYE, **kw)
    lit_only, _, _ = _iris_full(gl_window, _iris(light=1.0), **kw)
    cornea, sclera = _regions(camera)
    assert np.array_equal(lit_only[sclera], plain[sclera])
    assert (np.abs(lit_only - plain).max(-1)[cornea] > 2).sum() > 200
    iris = _iris_pixels(camera)
    cols = np.argwhere(iris)[:, 1]
    centre = 0.5 * (cols.min() + cols.max())
    for key in ((60.0, 0.0), (-60.0, 0.0)):
        base, camera, light = _iris_full(gl_window, DEFAULT_EYE, key=key, **kw)
        crescent, _, _ = _iris_full(gl_window, _iris(light=1.0, crescent=1.0), key=key, **kw)
        gain = (crescent - base).mean(-1)
        x = np.where(iris, np.arange(SIZE)[None, :] - centre, 0.0) * _key_side(camera, light)
        # the band between the centre and the far edge (outermost the key cannot reach: beyond the caustic)
        half = 0.5 * (cols.max() - cols.min())
        far, near = iris & (x < -0.15 * half) & (x > -0.75 * half), iris & (x > 0.15 * half) & (x < 0.75 * half)
        assert far.sum() > 300 and near.sum() > 300
        assert gain[far].mean() > gain[near].mean() + 5.0, (key, gain[far].mean(), gain[near].mean())
        assert (crescent - base).mean(-1)[far].mean() > 5.0  # brighter than the Worklight's key alone


def test_rim_shadow_darkens_the_iris_edge_on_the_keys_side(gl_window):
    kw = dict(distance=4.0)
    base, camera, light = _iris_full(gl_window, _iris(light=1.0), **kw)
    shaded, _, _ = _iris_full(gl_window, _iris(light=1.0, rim_shadow=1.0), **kw)
    assert np.all(shaded <= base)
    darker = np.argwhere((base - shaded).max(-1) > 3)
    assert len(darker) > 30
    eye_centre = np.argwhere(_cpu_kinds(camera, "V2") > 0)[:, 1].mean()
    assert np.sign(darker[:, 1].mean() - eye_centre) == _key_side(camera, light)


def test_relief_changes_only_the_iris_and_reads_the_derived_height(gl_window):
    """Roadmap #5: the relief tilts the iris's normal only (sclera and pupil unchanged); the procedural iris has no
    alpha, so its height is derived (also with the source "alpha"); the derived texture is built once."""
    kw = dict(distance=4.0, key=(30.0, 20.0))
    plain, camera, _ = _iris_full(gl_window, DEFAULT_EYE, **kw)
    relief, _, _ = _iris_full(gl_window, _iris(relief=1.0), **kw)
    alpha, _, _ = _iris_full(gl_window, _iris(relief=1.0, relief_source="alpha"), **kw)
    kinds = _cpu_kinds(camera, "V2")
    cornea, sclera = _regions(camera)
    assert np.array_equal(relief[sclera], plain[sclera])
    pupil = cornea & (kinds == eo.PUPIL)
    assert np.abs(relief[pupil] - plain[pupil]).max() <= 1
    iris = _iris_pixels(camera)
    assert (np.abs(relief - plain).max(-1)[iris] > 3).mean() > 0.3
    assert np.array_equal(relief, alpha)
    viewport, _ = _scene(_iris(relief=1.0), distance=4.0)
    viewport.set_eye_display(tier="full")
    _render(gl_window, viewport)
    _render(gl_window, viewport)
    assert len(viewport.eye_pass._relief) == 1
    texture = next(iter(viewport.eye_pass._relief.values()))
    assert texture is not None and texture.width == 512
    viewport.eye_pass.release()
    assert not viewport.eye_pass._relief


def test_relief_from_alpha_without_a_height_is_flat(gl_window, tmp_path):
    """An image without alpha read with the source "alpha" has no slope: the relief changes nothing."""
    from pyglet import image

    size = 64
    rgb = np.random.default_rng(5).uniform(0.2, 0.8, (size, size, 3))
    path = tmp_path / "iris_rgb.png"
    image.ImageData(size, size, "RGB", (rgb * 255).astype(np.uint8).tobytes()).save(str(path))
    plain, _, _ = _iris_full(gl_window, DEFAULT_EYE, distance=4.0, texture=str(path))
    flat, _, _ = _iris_full(gl_window, _iris(relief=1.0, relief_source="alpha"), distance=4.0, texture=str(path))
    assert np.abs(flat - plain).max() <= 1
    derived, _, _ = _iris_full(gl_window, _iris(relief=1.0), distance=4.0, texture=str(path))
    assert np.abs(derived - plain).max() > 3


def test_imported_height_in_alpha_draws_as_the_accepted_derived_height(gl_window, tmp_path):
    """Eye LookDev phase 5: the import bakes phase 4's derived height (`eye_optics.iris_height`, "2 go") into the
    copy's alpha, so "Höhe aus Alpha" on the copy draws what "Höhe aus Helligkeit" drew on the same colour - the
    accepted phase 4 appearance - within one 8-bit step of the relief's filtering."""
    from mirai import iris_import as ii

    flat = np.full((SIZE, SIZE, 4), 255, np.uint8)
    flat[..., :3] = np.clip(np.round(eo.procedural_iris(G, SIZE) * 255.0), 0, 255).astype(np.uint8)
    marks = ii.Landmarks(ii.Circle(SIZE / 2, SIZE / 2, G.pupil_radius / G.iris_radius * SIZE / 2),
                         ii.Circle(SIZE / 2, SIZE / 2, G.limbus_radius / G.iris_radius * SIZE / 2))
    result = ii.build_copy(flat, marks, "flat", DEFAULT_EYE, hold_outer_color=False)
    copy, rgb_only = tmp_path / "copy.png", tmp_path / "copy_rgb.png"
    copy.write_bytes(ii.encode_png(result.rgba))
    opaque = result.rgba.copy()
    opaque[..., 3] = 255
    rgb_only.write_bytes(ii.encode_png(opaque))
    fitted = dataclasses.replace(DEFAULT_EYE, fit_pupil=result.fit_pupil, fit_limbus=result.fit_limbus,
                                 hold_outer_color=result.hold_outer_color)
    kw = dict(distance=4.0, key=(30.0, 20.0))
    phase4, camera, _ = _iris_full(gl_window, _iris(fitted, relief=1.0), texture=str(rgb_only), **kw)
    alpha, _, _ = _iris_full(gl_window, _iris(fitted, relief=1.0, relief_source="alpha"), texture=str(copy), **kw)
    plain, _, _ = _iris_full(gl_window, fitted, texture=str(rgb_only), **kw)
    iris = _iris_pixels(camera)
    assert (np.abs(phase4 - plain).max(-1)[iris] > 3).mean() > 0.3  # the relief is there
    assert np.abs(alpha - phase4).max() <= 2 and np.abs(alpha - phase4).mean() < 0.1


def test_pupil_edge_and_margin_change_only_a_ring_at_the_pupil(gl_window):
    """Roadmap #7: the soft edge changes only pixels whose iris point lies within the edge (plus the pixel footprint)
    of the pupil radius; the margin darkens only outside the pupil, within its width."""
    kw = dict(distance=3.0)
    plain, camera, _ = _iris_full(gl_window, DEFAULT_EYE, **kw)
    eye, d = _camera_rays(camera)
    tr = eo.trace(eye, d, "V2", G)
    seen = (tr.kind == eo.IRIS) | (tr.kind == eo.PUPIL)
    r = np.where(seen, np.hypot(tr.hit[..., 0], tr.hit[..., 1]), np.inf)
    pixel = 2.0 * np.abs(np.gradient(r, axis=1)).clip(max=0.05)  # about two pixels' footprint
    edge = 0.2 * eo.MM
    soft, _, _ = _iris_full(gl_window, _iris(pupil_edge_mm=0.2), **kw)
    changed = np.abs(soft - plain).max(-1) > 1
    assert changed.sum() > 50
    assert np.all(np.abs(r[changed] - G.pupil_radius) < edge / 2 + pixel[changed] + 2e-3)
    margin, _, _ = _iris_full(gl_window, _iris(pupil_margin=1.0), **kw)
    darker = (plain - margin).max(-1) > 1
    assert darker.sum() > 50 and np.all(margin <= plain)
    width = eo.PUPIL_MARGIN_MM * eo.MM
    assert np.all((r[darker] > G.pupil_radius - 2e-3) & (r[darker] < G.pupil_radius + width + 2e-3))


@pytest.mark.parametrize("level", [0, 3])
@pytest.mark.parametrize("reflection", ["key", "studio"])
@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_iris_programs_draw_and_leave_the_gl_state_clean(gl_window, level, reflection, variant):
    from pyglet import gl

    spec = dataclasses.replace(_iris(light=1.0, crescent=1.0, rim_shadow=0.8, relief=0.5, pupil_edge_mm=0.1,
                                     pupil_margin=0.4), limbus_level=level, fit_pupil=0.22, fit_limbus=0.88)
    viewport, _ = _scene(spec, yaw=25.0)
    viewport.set_eye_display(tier="full", reflection=reflection, refraction=variant)
    img = _render(gl_window, viewport)
    assert np.sum(img.max(-1) > 0) > 3000
    assert not gl.glIsEnabled(gl.GL_BLEND) and not gl.glIsEnabled(gl.GL_CULL_FACE)
    unit = gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(unit))
    assert unit.value == gl.GL_TEXTURE0
    assert gl.glGetError() == gl.GL_NO_ERROR


def test_iris_table_value_glsl_matches_numpy(parity):
    rng = np.random.default_rng(43)
    v = eo.iris_values(PARITY_IRIS, G)
    r = G.iris_radius * np.sqrt(rng.uniform(0, 1, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    x = _pack(np.stack([r * np.cos(phi), r * np.sin(phi)], -1))
    a = _f32(x)
    key = eo.normalize(LIGHT["u_key_dir"])  # the parity pass's model is the identity
    for crescent in (PARITY_IRIS.crescent, 0.0):
        parity[False].crescent = crescent
        got = parity[False].run("iris_table_value", x)
        parity[False].crescent = None
        ref = eo.iris_table_value(a[:, :2], key, v["rim_width"], crescent, PARITY_IRIS.rim_shadow, G)
        assert np.abs(got[:, :3] - ref[:, :3]).max() < 3e-4
        assert np.abs(got[:, 3] - ref[:, 3]).max() < 1e-2  # the concentration's finite difference in float32


def test_iris_table_is_baked_once_per_key_and_leaves_the_gl_state(gl_window):
    """The key's path is traced once per eye into the table (not per pixel): baked again only when the key in the
    eye's frame or a key value changes; its texels are `eye_optics.iris_light_table`; the GL state stays as found."""
    from pyglet import gl

    from gui.imgui_layer import snapshot_gl_state

    spec = _iris(light=1.0, crescent=1.0, rim_shadow=0.8)
    viewport, camera = _scene(spec, distance=4.0)
    viewport.set_eye_display(tier="full")
    passes = viewport.eye_pass
    _render(gl_window, viewport)
    bakes = passes.table_bakes if passes is not None else 0
    passes = viewport.eye_pass
    _render(gl_window, viewport)
    _render(gl_window, viewport)
    assert passes.table_bakes == bakes >= 1  # an unchanged frame reuses the table
    camera.set_view(math.radians(20.0), 0.0)  # the key follows the camera: it turns in the eye's frame
    viewport.on_camera_changed(aspect=1.0)
    _render(gl_window, viewport)
    assert passes.table_bakes == bakes + 1
    (_key, texture, _fbo), = passes._tables.values()
    size = eo.IRIS_TABLE_SIZE
    out = np.zeros((size, size, 4), dtype=np.float32)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    light = viewport.light_uniforms()
    key = eo.normalize(np.asarray(light["u_key_dir"]))  # the model is a uniform scale: the same direction locally
    ref = eo.iris_light_table(key, spec.look.iris.rim_shadow_mm * eo.MM, 1.0, 0.8, G)
    close = (np.abs(out[..., :3] - ref[..., :3]).max(-1) < 2e-3) & (np.abs(out[..., 3] - ref[..., 3]) < 2e-2)
    assert close.mean() > 0.99, close.mean()  # half floats; a few texels at the edge of the key's reach flip
    # a bake inside a frame leaves the state as found
    spec2 = _iris(light=1.0, crescent=1.0, rim_shadow=0.5)
    viewport.set_object_entry("eye", shell_mesh(spec2), SCLERA_COLOUR, model_matrix=_model(), finish=FINISH,
                              eye=EyeDraw(spec2, None, SCLERA_COLOUR, FINISH, cornea_triangles(), variation=3))
    viewport.sync()
    before = snapshot_gl_state()
    viewport.render()
    assert passes.table_bakes == bakes + 2
    assert snapshot_gl_state() == before and gl.glGetError() == gl.GL_NO_ERROR


# -- AD-035 M1: the sclera's colour map (Manu 2026-11-17, S-1 .. S-13) -------------------------------------------------

#: Every shell variant's sources without a map (2 refractions x 4 levels x 2 reflections x fit x debug x look x iris),
#: float literals normalised to 9 significant digits (the generated constants' last digit may differ between NumPy
#: builds), hashed in order. Taken from `main` @ 5187c31 - the sources before AD-035.
PINNED_SOURCES_SHA256 = "0424ad123610865eb4ab55a577a9605f9e3726f337b3d0ad3d9332f3477e001a"
SCLERA_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "docs", "research",
                             "eye_sclera_assets_2026-11-17")
SYNTHETIC_MAP = os.path.normpath(os.path.join(SCLERA_ASSETS, "synthetic_sclera_front_disc_1024.png"))
#: The gradient test map: R = s, G = t (scaled into 0.15 .. 0.95), so a pixel's colour tells where it sampled.
GRADIENT_LO, GRADIENT_SPAN = 0.15, 0.8


def _source_digest(**kw) -> str:
    import hashlib
    import itertools
    import re

    floats = re.compile(r"-?\d+\.\d+(?:e[-+]?\d+)?")
    digest = hashlib.sha256()
    locations = {"position": 0, "normal": 1}
    for variant, level, reflection, fit, debug, look, iris in itertools.product(
            ("V2", "V3"), range(4), ("key", "studio"), (False, True), (False, True), (False, True), (False, True)):
        for src, _kind in es.shell_sources(locations, variant, level, reflection, fit, debug, look, iris, **kw):
            digest.update(floats.sub(lambda m: f"{float(m.group(0)):.9g}", src).encode())
    return digest.hexdigest()


def test_sources_without_a_map_are_the_ones_before_ad035():
    """AD-035 §6: an eye without a sclera map draws with the program before AD-035, character for character."""
    assert _source_digest() == _source_digest(sclera=False) == PINNED_SOURCES_SHA256
    locations = {"position": 0, "normal": 1}
    for look, iris in ((False, False), (True, False), (True, True)):
        plain = es.shell_sources(locations, "V2", 3, "studio", True, look=look, iris=iris)[1][0]
        assert "SCLERA_MAP" not in plain and "sclera_albedo(" not in plain and "u_sclera_texture" not in plain
        mapped = es.shell_sources(locations, "V2", 3, "studio", True, look=look, iris=iris, sclera=True)[1][0]
        assert "#define SCLERA_MAP 1\n" in mapped and "vec3 sclera_albedo(vec3 p)" in mapped
        assert "sclera_albedo(entry)" in mapped and "sclera_albedo(p)" in mapped  # the two reads, one mapping


#: AD-038 §5.4 (C6): every Worklight eye source - all `shell_sources` variants with `lookdev` off (the 8 arguments,
#: the sclera map included), `parity_sources` for both fits and `iris_table_sources`, 1,030 sources in that order,
#: floats normalised as in `_source_digest`. Taken from `main` @ 89f61fc, before LookDev touched `eye_shaders.py`.
PINNED_WORKLIGHT_SOURCES_SHA256 = "714a683b3ab967518c032312fc8e2327717d7f3d3afa0389bffa40d9b6df9bf0"


def _all_sources_digest(**kw) -> tuple[int, str]:
    import hashlib
    import itertools
    import re

    floats = re.compile(r"-?\d+\.\d+(?:e[-+]?\d+)?")
    digest, count = hashlib.sha256(), 0
    locations = {"position": 0, "normal": 1}
    sources = []
    for variant, level, reflection, fit, debug, look, iris, sclera in itertools.product(
            ("V2", "V3"), range(4), ("key", "studio"), (False, True), (False, True), (False, True), (False, True),
            (False, True)):
        sources += es.shell_sources(locations, variant, level, reflection, fit, debug, look, iris, sclera, **kw)
    if not kw:
        sources += es.parity_sources(False) + es.parity_sources(True) + es.iris_table_sources()
    for src, _kind in sources:
        digest.update(floats.sub(lambda m: f"{float(m.group(0)):.9g}", src).encode())
        count += 1
    return count, digest.hexdigest()


def test_every_worklight_source_is_the_one_before_lookdev():
    """AD-038 §5.4 / C6: the LookDev variant leaves every Worklight eye source character for character as it was."""
    assert _all_sources_digest() == (1030, PINNED_WORKLIGHT_SOURCES_SHA256)


def test_sclera_st_glsl_matches_numpy(parity):
    """The front disc's GLSL against `eye_optics.sclera_st`: sclera and cornea points, both poles, beyond the rim."""
    rng = np.random.default_rng(23)
    n = N
    theta = np.concatenate([rng.uniform(0.0, np.pi, n - 6), [0.0, 1e-7, np.pi, np.pi - 1e-7, eo.SCLERA_RIM, 2.5]])
    phi = rng.uniform(0.0, 2.0 * np.pi, n)
    radius = np.where(rng.uniform(size=n) < 0.3, rng.uniform(0.9, 1.1, n), 1.0)  # cornea entries lie off the sphere
    p = radius[:, None] * np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)
    x = _pack(p)
    a = _f32(x)
    got = parity[False].run("sclera_st", x)[:, :2]
    ring = math.asin(G.limbus_radius)
    ref = eo.sclera_st(a[:, :3], ring)
    assert np.all(np.isfinite(got)) and np.abs(got - ref).max() < 2e-5
    r = 2.0 * np.hypot(ref[:, 0] - 0.5, ref[:, 1] - 0.5)
    on_ring = np.abs(np.arctan2(np.hypot(a[:, 0], a[:, 1]), a[:, 2]) - ring) < 1e-9
    assert np.all(r <= 1.0 + 1e-12) and np.all(np.abs(r[on_ring] - eo.SCLERA_LIMBUS_SHARE) < 1e-9)
    assert np.abs(got[n - 6] - 0.5).max() < 1e-6 and np.abs(got[n - 5] - 0.5).max() < 1e-6  # the front pole: centre


def test_the_disc_is_anchored_to_the_anatomys_limbus():
    """The painted limbus stays on the eye's limbus when the limbus radius changes; the rim stays at 130 deg."""
    for limbus in (0.42, 0.49, 0.58):
        ring = math.asin(limbus)
        points = np.array([[limbus * math.cos(a), limbus * math.sin(a), math.sqrt(1 - limbus ** 2)]
                           for a in np.linspace(0, 2 * np.pi, 13)])
        st = eo.sclera_st(points, ring)
        assert np.allclose(np.hypot(st[:, 0] - 0.5, st[:, 1] - 0.5), 0.5 * eo.SCLERA_LIMBUS_SHARE, atol=1e-12)
        rim = np.array([[math.sin(eo.SCLERA_RIM), 0.0, math.cos(eo.SCLERA_RIM)]])
        assert np.allclose(eo.sclera_st(rim, ring), [[1.0, 0.5]], atol=1e-12)
    up = eo.sclera_st(np.array([[0.0, 0.6, 0.8], [0.6, 0.0, 0.8]]), math.asin(0.49))
    assert up[0, 1] > 0.5 and abs(up[0, 0] - 0.5) < 1e-12 and up[1, 0] > 0.5  # image up = +Y, right = +X


@pytest.fixture(scope="module")
def sclera_maps(gl_window):
    """PNG maps for the GL tests (pyglet decodes them as the app does): the gradient, white, black, uniform colours."""
    from mirai.iris_import import encode_png

    size = 512
    tmp = tempfile.TemporaryDirectory()
    t, s = np.mgrid[0:size, 0:size]
    st = (np.stack([s, size - 1 - t], -1) + 0.5) / size  # file rows run top-down: t = 1 at row 0
    paths = {}

    def write(name, rgb):
        rgba = np.empty((size, size, 4), np.uint8)
        rgba[..., :3] = np.clip(np.round(np.broadcast_to(rgb, (size, size, 3)) * 255.0), 0, 255)
        rgba[..., 3] = 255
        path = os.path.join(tmp.name, f"{name}.png")
        with open(path, "wb") as fh:
            fh.write(encode_png(rgba))
        paths[name] = path

    gradient = np.concatenate([GRADIENT_LO + GRADIENT_SPAN * st, np.full((size, size, 1), 0.55)], -1)
    write("gradient", gradient)
    write("white", np.ones(3))
    write("black", np.zeros(3))
    write("base", np.asarray(SCLERA_COLOUR))
    paths["base_colour"] = tuple(round(c * 255.0) / 255.0 for c in SCLERA_COLOUR)  # what the map stores
    paths["synthetic"] = SYNTHETIC_MAP
    yield paths
    tmp.cleanup()


def _model_turned(yaw_deg=0.0, pitch_deg=0.0, scale=SCALE) -> list[float]:
    """A placement turned like a gaze (yaw about +Y, then pitch about +X), column-major."""
    cy, sy = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))
    yaw = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    pitch = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    m = np.eye(4)
    m[:3, :3] = scale * (yaw @ pitch)
    return [float(v) for v in m.T.ravel()]


def _map_render(gl_window, spec=DEFAULT_EYE, sclera=None, colour=SCLERA_COLOUR, tint=(0.0, 0.0, 0.0, 0.0), yaw=0.0,
                pitch=0.0, distance=6.0, model=None, tier="fast", reflection="studio"):
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=distance)
    camera.set_view(math.radians(yaw), math.radians(pitch))
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=1.0)
    draw = EyeDraw(spec, None, tuple(colour), FINISH, cornea_triangles(), variation=3, sclera_texture=sclera,
                   sclera_tint=tuple(tint))
    viewport.set_object_entry("eye", shell_mesh(spec), tuple(colour), model_matrix=model or _model(), finish=FINISH,
                              eye=draw)
    viewport.set_eye_display(tier=tier, reflection=reflection)
    return _render(gl_window, viewport), camera, viewport


def _local_rays(camera, model):
    """Eye-local rays through the pixel centres (row 0 = top) for any placement `model` (column-major)."""
    view = np.array(camera.build_view_matrix()).reshape(4, 4).T
    proj = np.array(camera.build_projection_matrix(1.0)).reshape(4, 4).T
    inv = np.linalg.inv(proj @ view)
    to_local = np.linalg.inv(np.asarray(model, dtype=np.float64).reshape(4, 4).T)
    px = (np.arange(SIZE) + 0.5) / SIZE * 2.0 - 1.0
    x, y = np.meshgrid(px, -px)
    near = np.stack([x, y, -np.ones_like(x), np.ones_like(x)], -1) @ inv.T
    far = np.stack([x, y, np.ones_like(x), np.ones_like(x)], -1) @ inv.T
    near, far = (near / near[..., 3:]) @ to_local.T, (far / far[..., 3:]) @ to_local.T
    eye = to_local @ np.append(np.asarray(camera.eye(), dtype=np.float64), 1.0)
    return eye[:3], eo.normalize(far[..., :3] - near[..., :3])


def _map_points(camera, model, variant="V2"):
    """Per pixel: the eye-local point whose sclera colour the shader reads (the sclera hit, or the cornea's entry - for
    the limbal tissue and its cover over the iris) and its class (-1 sclera, LIMBUS cornea, 0 none), with a 2-pixel
    margin from every class boundary. Where the cornea shows no sclera colour (the open iris, the pupil) the recovered
    albedo is invalid anyway (`_albedo`: nothing lit)."""
    eye, d = _local_rays(camera, model)
    tr = eo.trace(eye, d, variant, G)
    hit_s, ts = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.zeros(3), 1.0)
    ps = eye + ts[..., None] * d
    hit_a, ta = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.array([0.0, 0.0, G.anterior_centre_z]),
                                G.cornea_radius)
    sclera = hit_s & (ps[..., 2] < G.limbus_z) & (~hit_a | (ts < ta) | (tr.kind == eo.MISS))
    kinds = np.where(sclera, -1, np.where(tr.kind != eo.MISS, eo.LIMBUS, 0))  # cornea: tissue or its cover
    point = np.where(sclera[..., None], ps, tr.entry)
    keep = kinds != 0
    for axis in (0, 1):
        for shift in (1, 2):
            keep &= (np.roll(kinds, shift, axis) == kinds) & (np.roll(kinds, -shift, axis) == kinds)
    return point, kinds, keep


def _albedo(gl_window, maps, name, **scene):
    """The albedo the shader read per pixel, recovered from three frames: the colour is linear in the albedo with
    everything else (reflections, highlights, lid band) added independently, so (M - K) / (W - K) is the map's
    value. Returns (albedo, valid, camera)."""
    frames = {}
    for key in (name, "white", "black"):
        frames[key], camera, _ = _map_render(gl_window, sclera=maps[key], **scene)
    lit = (frames["white"] - frames["black"]).astype(np.float64)
    valid = (lit[..., :2] > 50).all(-1) & (frames["white"] < 255).all(-1)  # light enough, nothing clipped
    return (frames[name] - frames["black"]) / np.maximum(lit, 1.0), valid, camera


#: The limbal tissue's colour = the sclera's (strength 0), and an overlap that lays it over the iris's edge, so the
#: cornea's side of the ring shows the map over a band of pixels (the cover is linear in the albedo as well).
L1_FLAT = dataclasses.replace(DEFAULT_EYE, limbus_level=1, strength=0.0, overlap_mm=0.8, asymmetry=True)


@pytest.mark.parametrize("yaw, pitch, gaze, tier", [
    (0.0, 0.0, (0.0, 0.0), "fast"),       # frontal at rest
    (0.0, 0.0, (25.0, 12.0), "fast"),     # frontal, the eye turned by a gaze
    (40.0, 10.0, (0.0, 0.0), "full"),     # three-quarter
    (40.0, 10.0, (-20.0, 8.0), "full"),   # three-quarter with a gaze
    (78.0, 0.0, (0.0, 0.0), "fast"),      # side
    (180.0, 0.0, (0.0, 0.0), "fast"),     # the back (isolated orbit only): the held rim
])
def test_the_map_is_sampled_where_the_numpy_twin_says_on_both_sides_of_the_limbus(gl_window, sclera_maps, yaw, pitch,
                                                                                  gaze, tier):
    """The colour each pixel read equals the gradient map at `eye_optics.sclera_st` of its eye-local point - on the
    sclera and on the limbal tissue seen through the cornea, at rest and turned by a gaze, from the front, three-quarter,
    side and back: the mapping is eye-local (it turns with the eye) and the same on both sides of the ring."""
    model = _model_turned(*gaze)
    spec = dataclasses.replace(L1_FLAT, look=dataclasses.replace(DEFAULT_LOOK, wet_sclera=0.8, irregularity_deg=0.5,
                                                                  lid_shadow=0.3, lid_band=0.7))
    albedo, valid, camera = _albedo(gl_window, sclera_maps, "gradient", spec=spec, yaw=yaw, pitch=pitch, model=model,
                                    distance=4.5, tier=tier)
    point, kinds, keep = _map_points(camera, model)
    theta = np.arctan2(np.hypot(point[..., 0], point[..., 1]), point[..., 2])
    use = keep & valid & (theta < math.radians(172.0))  # the back pole itself: any direction, a coarse mip there
    st = eo.sclera_st(point, math.asin(G.limbus_radius))
    expected = GRADIENT_LO + GRADIENT_SPAN * st
    error = np.abs(albedo[..., :2] - expected).max(-1)
    assert use.sum() > 1500, use.sum()
    assert np.percentile(error[use], 50) < 0.012 and np.percentile(error[use], 99) < 0.04, (
        np.percentile(error[use], 50), np.percentile(error[use], 99))
    tissue = use & (kinds == eo.LIMBUS)
    if yaw < 60.0:
        assert tissue.sum() > 50 and np.percentile(error[tissue], 99) < 0.04  # the cornea's side of the ring


def test_no_step_at_the_limbus(gl_window, sclera_maps):
    """Neighbouring pixels on either side of the ring (one reads the sclera branch, the other the cornea's limbal
    tissue) read neighbouring map values: the step across the ring is no larger than between neighbours elsewhere."""
    albedo, valid, camera = _albedo(gl_window, sclera_maps, "gradient", spec=L1_FLAT, distance=3.2, yaw=15.0)
    _point, kinds, _keep = _map_points(camera, _model())
    steps_ring, steps_else = [], []
    for axis in (0, 1):
        other, other_valid, other_kind = (np.roll(a, -1, axis) for a in (albedo, valid, kinds))
        pair = valid & other_valid & (kinds != 0) & (other_kind != 0)
        step = np.abs(other - albedo)[..., :2].max(-1)
        across = pair & (kinds != other_kind)
        steps_ring.append(step[across])
        steps_else.append(step[pair & (kinds == other_kind)])
    ring, rest = np.concatenate(steps_ring), np.concatenate(steps_else)
    assert len(ring) > 40 and len(rest) > 2000
    assert np.percentile(ring, 95) <= np.percentile(rest, 99) + 0.01, (np.percentile(ring, 95), np.percentile(rest, 99))


def test_the_synthetic_map_reads_as_painted(gl_window, sclera_maps):
    """The repository's synthetic map (`docs/research/eye_sclera_assets_2026-11-17/`) in the Eye Lab's close-up: the
    colour read on the sclera equals the image at the twin's coordinates (bilinear, full resolution - the close-up is
    about one texel per pixel; vessels make single pixels differ through the mip choice, so the median is checked)."""
    from mirai.iris_import import read_rgba

    image = read_rgba(SYNTHETIC_MAP)[..., :3] / 255.0
    spec = dataclasses.replace(L3_EYE, look=dataclasses.replace(DEFAULT_LOOK, wet_sclera=0.7, irregularity_deg=0.5))
    albedo, valid, camera = _albedo(gl_window, sclera_maps, "synthetic", spec=spec, distance=3.0, yaw=10.0,
                                    tier="full")
    point, kinds, keep = _map_points(camera, _model())
    use = keep & valid & (kinds == -1)
    expected = eo.sclera_texel(image, eo.sclera_st(point, math.asin(G.limbus_radius)))
    error = np.abs(albedo - expected).max(-1)
    assert use.sum() > 3000
    assert np.median(error[use]) < 0.02 and np.percentile(error[use], 90) < 0.06, (
        np.median(error[use]), np.percentile(error[use], 90))


@pytest.mark.parametrize("tier, level", [("fast", 0), ("fast", 3), ("full", 3)])
def test_a_uniform_map_draws_the_eye_as_its_base_colour_of_that_colour(gl_window, sclera_maps, tier, level):
    """S-7: the map replaces the base colour and nothing else - a map of one colour draws the same pixels as an eye of
    that base colour without a map (L0 / L3, fast and full with the wet film, irregularity, lid shadow and band, the
    iris values)."""
    spec = dataclasses.replace(L3_EYE, limbus_level=level, look=dataclasses.replace(
        DEFAULT_LOOK, wet_sclera=0.8, irregularity_deg=0.6, highlight_softness=0.5, lid_shadow=0.4, lid_band=0.8,
        iris=dataclasses.replace(DEFAULT_IRIS, light=1.0, crescent=1.0, rim_shadow=0.6, pupil_edge_mm=0.1)))
    base = sclera_maps["base_colour"]
    for yaw in (0.0, 35.0):
        mapped, _, _ = _map_render(gl_window, spec, sclera_maps["base"], colour=base, yaw=yaw, distance=4.0, tier=tier)
        plain, _, _ = _map_render(gl_window, spec, None, colour=base, yaw=yaw, distance=4.0, tier=tier)
        assert np.abs(mapped - plain).max() <= 1, (yaw, np.abs(mapped - plain).max())


def test_reflections_and_the_wet_film_do_not_depend_on_the_map(gl_window, sclera_maps):
    """§6 / audit §2.5, with the wet film fully on: at a black albedo only what is added independently of it remains -
    the film's and the cornea's reflections, dimmed by the lid band. That reflection-only frame is the same with a black
    map (the base colour set to grey, unused) and with a black base colour without a map. And the synthetic map's own
    contribution (the frame minus the black-map frame) is only scaled by the film's transmission (1 - F): never larger
    than without the film, and most of it remains - the map changes what the light falls on, not the reflection."""
    spec = dataclasses.replace(L3_EYE, look=dataclasses.replace(DEFAULT_LOOK, wet_sclera=1.0, irregularity_deg=0.7,
                                                                 highlight_softness=0.4, lid_band=0.8))
    for yaw in (0.0, 30.0):
        mapped, _, _ = _map_render(gl_window, spec, sclera_maps["black"], colour=(0.6, 0.6, 0.6), yaw=yaw, tier="full")
        plain, _, _ = _map_render(gl_window, spec, None, colour=(0.0, 0.0, 0.0), yaw=yaw, tier="full")
        assert np.abs(mapped - plain).max() <= 1 and mapped.max() > 60  # the reflections are there
    wet = {name: _map_render(gl_window, spec, sclera_maps[name], yaw=20.0, tier="full")[0]
           for name in ("synthetic", "black", "white")}
    dry_spec = dataclasses.replace(spec, look=dataclasses.replace(spec.look, wet_sclera=0.0, lid_band=0.0))
    dry = {name: _map_render(gl_window, dry_spec, sclera_maps[name], yaw=20.0, tier="full")[0]
           for name in ("synthetic", "black")}
    # the map's own contribution scales with the film's transmission (1 - F); the reflection term cancels exactly
    contrib_wet = (wet["synthetic"] - wet["black"]).astype(float)
    contrib_dry = (dry["synthetic"] - dry["black"]).astype(float)
    assert np.all(contrib_wet <= contrib_dry + 1) and contrib_wet.sum() > 0.8 * contrib_dry.sum()


def test_the_selection_tint_goes_over_the_map_and_none_is_the_map(gl_window, sclera_maps):
    """S-4: outside the Eye Lab a selected eye's map is tinted as a selected object's colour is; the app sends no tint
    while the Eye Lab is open (`test_eye_sclera.py`), and then the eye draws its map as it is."""
    from mirai.scene_objects import SELECTED_TINT, SELECTED_TINT_SHARE

    tint = (*SELECTED_TINT, SELECTED_TINT_SHARE)
    tinted, _, _ = _map_render(gl_window, DEFAULT_EYE, sclera_maps["white"], tint=tint, yaw=20.0)
    colour = tuple(1.0 + SELECTED_TINT_SHARE * (t - 1.0) for t in SELECTED_TINT)
    expected, _, _ = _map_render(gl_window, DEFAULT_EYE, None, colour=colour, yaw=20.0)
    assert np.abs(tinted - expected).max() <= 1
    untinted, _, _ = _map_render(gl_window, DEFAULT_EYE, sclera_maps["white"], yaw=20.0)
    white, _, _ = _map_render(gl_window, DEFAULT_EYE, None, colour=(1.0, 1.0, 1.0), yaw=20.0)
    assert np.abs(untinted - white).max() <= 1 and np.any(untinted != tinted)


def test_a_missing_map_draws_the_base_colour_with_the_program_before(gl_window, sclera_maps):
    plain, _, viewport = _map_render(gl_window, DEFAULT_EYE, None, yaw=20.0)
    missing, _, viewport2 = _map_render(gl_window, DEFAULT_EYE, os.path.join(tempfile.gettempdir(), "no_such.png"),
                                        yaw=20.0)
    assert np.array_equal(plain, missing)
    assert not any(key[-1] for key in viewport2.eye_pass.programs)  # no SCLERA_MAP program was built


@pytest.mark.parametrize("level", [0, 3])
@pytest.mark.parametrize("reflection", ["key", "studio"])
@pytest.mark.parametrize("variant", ["V2", "V3"])
@pytest.mark.parametrize("tier", ["fast", "full"])
def test_map_programs_draw_and_leave_the_gl_state_clean(gl_window, sclera_maps, level, reflection, variant, tier):
    """Every map variant compiles and draws in both tiers (S-3); afterwards no sampler or texture is left on the map's
    unit, the active unit is 0, and the shared cached texture keeps its own REPEAT wrap (the pass's sampler clamps)."""
    from pyglet import gl

    from gui.imgui_layer import snapshot_gl_state
    from viewport.eye_pass import SCLERA_UNIT

    spec = dataclasses.replace(_iris(light=1.0, crescent=1.0, relief=0.5, pupil_edge_mm=0.1), limbus_level=level,
                               fit_pupil=0.22, fit_limbus=0.88)
    spec = dataclasses.replace(spec, look=dataclasses.replace(spec.look, wet_sclera=0.7, lid_band=0.6))
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0)
    camera.set_view(math.radians(25.0), 0.0)
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=1.0)
    draw = EyeDraw(spec, None, SCLERA_COLOUR, FINISH, cornea_triangles(), variation=3,
                   sclera_texture=sclera_maps["synthetic"])
    viewport.set_object_entry("eye", shell_mesh(spec), SCLERA_COLOUR, model_matrix=_model(), finish=FINISH, eye=draw)
    viewport.set_eye_display(reflection=reflection, refraction=variant, tier=tier)
    img = _render(gl_window, viewport)
    assert np.sum(img.max(-1) > 0) > 3000
    assert any(key[-1] for key in viewport.eye_pass.programs)  # the SCLERA_MAP program drew
    before = snapshot_gl_state()
    viewport.render()
    assert snapshot_gl_state() == before
    unit, sampler, bound = gl.GLint(), gl.GLint(), gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(unit))
    assert unit.value == gl.GL_TEXTURE0
    gl.glActiveTexture(gl.GL_TEXTURE0 + SCLERA_UNIT)
    gl.glGetIntegerv(gl.GL_SAMPLER_BINDING, ctypes.byref(sampler))
    gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D, ctypes.byref(bound))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    assert sampler.value == 0 and bound.value == 0
    texture = GLRenderStore.texture(sclera_maps["synthetic"])
    wrap = gl.GLint()
    gl.glBindTexture(texture.target, texture.id)
    gl.glGetTexParameteriv(texture.target, gl.GL_TEXTURE_WRAP_S, ctypes.byref(wrap))
    gl.glBindTexture(texture.target, 0)
    assert wrap.value == gl.GL_REPEAT
    assert gl.glGetError() == gl.GL_NO_ERROR


# -- AD-038 §5: the eye's LOOKDEV variant (only added; every test above runs unchanged) -------------------------------

#: E4: every LOOKDEV shell source (`lookdev=True`, all 8 other arguments), float-normalised as `_source_digest`. Taken
#: at its introduction (AD-038 LD-1): a later change of the LOOKDEV GLSL re-pins it deliberately.
PINNED_LOOKDEV_SOURCES_SHA256 = "a554aad64d1b5fa3154f72abd2eec33e199680505b74b32e270e869440786f07"


def test_lookdev_sources_are_pinned():
    assert _all_sources_digest(lookdev=True) == (1024, PINNED_LOOKDEV_SOURCES_SHA256)
    locations = {"position": 0, "normal": 1}
    plain = es.shell_sources(locations, "V2", 3, "studio", True, look=True, iris=True)[1][0]
    looked = es.shell_sources(locations, "V2", 3, "studio", True, look=True, iris=True, lookdev=True)[1][0]
    assert "LOOKDEV" not in plain and "u_ld_" not in plain and "lookdev_output" not in plain
    assert "#define LOOKDEV 1\n" in looked and "vec3 lookdev_output(vec3 c)" in looked
    assert looked.index("vec3 lookdev_output(vec3 c)") < looked.index("void main()")


def _ld_state(**kw):
    from viewport import lookdev_optics as lo

    values = dict(preset="test", studio=lo.EYE_STUDIO, key=lo.StudioLight(True, 1.6, 45.0, 30.0, 5600.0, 0.1),
                  fill=lo.StudioLight(True, 0.5, -60.0, 5.0, 6500.0, 0.25),
                  rim=lo.StudioLight(True, 1.0, -150.0, 25.0, 7500.0, 0.05), env_intensity=0.3,
                  background=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    values.update(kw)
    return lo.LookdevState(**values)


@pytest.mark.parametrize("level", [0, 3])
@pytest.mark.parametrize("reflection", ["key", "studio"])
@pytest.mark.parametrize("variant", ["V2", "V3"])
@pytest.mark.parametrize("look", [False, True])
def test_lookdev_programs_draw_and_leave_the_gl_state_clean(gl_window, level, reflection, variant, look):
    from pyglet import gl

    spec = dataclasses.replace(_iris(light=0.8, crescent=1.0, rim_shadow=0.5, relief=0.5) if look else DEFAULT_EYE,
                               limbus_level=level, fit_pupil=0.22, fit_limbus=0.88)
    if look:
        spec = dataclasses.replace(spec, look=dataclasses.replace(spec.look, wet_sclera=0.7, highlight_softness=0.5,
                                                                  lid_shadow=0.3, lid_band=0.8))
    viewport, _ = _scene(spec, yaw=25.0)
    viewport.set_eye_display(tier="full", reflection=reflection, refraction=variant)
    worklight = _render(gl_window, viewport)
    viewport.set_shading("lookdev", _ld_state())
    gl.glUseProgram(0)
    from gui.imgui_layer import snapshot_gl_state

    before = snapshot_gl_state()
    img = _render(gl_window, viewport)
    assert snapshot_gl_state() == before and gl.glGetError() == gl.GL_NO_ERROR
    assert np.sum(img.max(-1) > 0) > 3000 and np.any(img != worklight)
    keys = list(viewport.eye_pass.programs)
    assert all(len(k) == 9 for k in keys) and {k[7] for k in keys} == {False, True}  # one Worklight, one LOOKDEV
    assert any(k[7] and k[5] == look and k[6] == look for k in keys)


def test_lookdev_iris_table_follows_the_lookdev_key(gl_window):
    """C5 / D2: the phase 4 key table is baked from `u_key_dir` - in the room the LookDev key; a studio rotation
    rebakes it once, a frame without a change does not."""
    spec = _iris(light=1.0, crescent=1.0, rim_shadow=0.5)
    viewport, _ = _scene(spec, yaw=10.0)
    viewport.set_eye_display(tier="full")
    viewport.set_shading("lookdev", _ld_state())
    passes = viewport.eye_pass
    _render(gl_window, viewport)
    bakes = passes.table_bakes
    assert bakes >= 1
    _render(gl_window, viewport)
    assert passes.table_bakes == bakes
    viewport.set_shading("lookdev", _ld_state(rotation=40.0))
    _render(gl_window, viewport)
    assert passes.table_bakes == bakes + 1


def test_lookdev_off_draws_the_worklight_eye(gl_window):
    """`lighting=None` (the Worklight) after LookDev frames is pixel for pixel the eye before them."""
    viewport, _ = _scene(_with(wet_sclera=0.5), yaw=20.0)
    viewport.set_eye_display(tier="full")
    before = _render(gl_window, viewport)
    viewport.set_shading("lookdev", _ld_state())
    _render(gl_window, viewport)
    viewport.set_shading("worklight")
    assert np.array_equal(_render(gl_window, viewport), before)


# -- AD-039 §5 (S2): the eye in the key's shadow (only added; every test above runs unchanged) ------------------------

#: T2-2: every LOOKDEV + LD_SHADOW shell source (`lookdev=True, ld_shadow=True`, all 8 other arguments), normalised as
#: `_source_digest`. Taken at its introduction (AD-039 S2): a later change of the eye's LD_SHADOW GLSL (or of the
#: shared `LD_SHADOW_SRC`) re-pins it deliberately.
PINNED_LD_SHADOW_SOURCES_SHA256 = "de3510eaf6944dd8893d59315c993b248bec1d1d47fdb4f704954f43c7d17931"
S2_KEY = (30.0, 65.0)


def _s2_state(key=S2_KEY, intensity=1.6, effects=None, **kw):
    from viewport import lookdev_optics as lo

    state = _ld_state(key=lo.StudioLight(True, intensity, key[0], key[1], 5600.0, 0.1), **kw)
    return dataclasses.replace(state, effects=effects) if effects is not None else state


def _plate(centre, normal, half, n=6) -> Mesh:
    """A square plate of n x n quads centred at `centre`, perpendicular to `normal`, facing it."""
    normal = eo.normalize(np.asarray(normal, dtype=np.float64))
    ref = np.array([0.0, 0.0, 1.0]) if abs(normal[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    a = eo.normalize(np.cross(normal, ref))
    b = np.cross(normal, a)
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex(tuple(float(c) for c in np.asarray(centre) + half * ((2 * i / n - 1) * a
                                                                                         + (2 * j / n - 1) * b)))
           for i in range(n + 1) for j in range(n + 1)}
    for i in range(n):
        for j in range(n):
            mesh.add_face([ids[i, j], ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]])
    return mesh


def _key_dir(state) -> np.ndarray:
    from viewport import lookdev_optics as lo

    return np.asarray(lo.frame_uniforms(state)["u_ld_light_dir"][0], dtype=np.float64)


def _s2_scene(spec, state, blocker: str | None, yaw=20.0, floor=True):
    """The eye at the origin in the room, a floor below it (a caster that does not shadow the eye, so the map exists)
    and `blocker`: None, "full" (a plate between the key and the whole eye) or "half" (its edge across the eye)."""
    from viewport.lookdev_pass import LookDraw

    grey = LookDraw((0.5, 0.5, 0.5), roughness=1.0, specular=0.0)
    viewport, camera = _scene(spec, yaw=yaw)
    viewport.set_eye_display(tier="full")
    if floor:
        viewport.set_object_entry("floor", _plate((0.0, -2.2, 0.0), (0.0, 1.0, 0.0), 3.0), (0.5, 0.5, 0.5), look=grey)
    if blocker is not None:
        k = _key_dir(state)
        side = eo.normalize(np.cross(k, np.array([0.0, 1.0, 0.0])))
        centre = 3.2 * k + (0.0 if blocker == "full" else 2.2) * side
        viewport.set_object_entry("blocker", _plate(centre, k, 2.2), (0.5, 0.5, 0.5), look=grey)
    viewport.set_shading("lookdev", state)
    return viewport, camera


def _eye_mask(gl_window, spec, state, yaw=20.0):
    """The eye's own pixels (an eye-only frame on black, eroded by one pixel)."""
    viewport, _ = _s2_scene(spec, state, None, yaw=yaw, floor=False)
    img = _render(gl_window, viewport)
    mask = img.max(-1) > 0
    return mask & np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1)


def _plate_mask(gl_window, spec, state, blocker, yaw=20.0):
    """Pixels a plate covers (drawn without the eye): excluded from eye comparisons."""
    viewport, _ = _s2_scene(spec, state, blocker, yaw=yaw)
    viewport.set_eye_display(preview=False)
    viewport.remove_object_entry("eye")
    img = _render(gl_window, viewport)
    mask = img.max(-1) > 0
    return mask | np.roll(mask, 1, 0) | np.roll(mask, -1, 0) | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)


def _s2_eye(look: str):
    """The eye variants S2 scales: plain (B1, B6 and the cornea's point key), a look with the wet film's soft key
    (B5) and the iris's key table (B2), a look with the point key on the film."""
    if look == "plain":
        return dataclasses.replace(DEFAULT_EYE, limbus_level=3)
    spec = dataclasses.replace(_iris(light=0.8, crescent=1.0, rim_shadow=0.5), limbus_level=3, fit_pupil=0.22,
                               fit_limbus=0.88)
    soft = 0.5 if look == "soft" else 0.0
    return dataclasses.replace(spec, look=dataclasses.replace(spec.look, wet_sclera=0.7, highlight_softness=soft,
                                                              lid_shadow=0.3, lid_band=0.8))


def test_ld_shadow_sources_are_pinned_and_the_old_ones_unchanged():
    """T2-2: the three eye pins as they were (above), a new pin over LOOKDEV + LD_SHADOW; the shadow's library is the
    skin's string, appended only with the define; `ld_shadow` without `lookdev` is the Worklight source."""
    from viewport import lookdev_shaders as ls

    assert _all_sources_digest() == (1030, PINNED_WORKLIGHT_SOURCES_SHA256)
    assert _all_sources_digest(lookdev=True) == (1024, PINNED_LOOKDEV_SOURCES_SHA256)
    assert _all_sources_digest(lookdev=True, ld_shadow=False) == (1024, PINNED_LOOKDEV_SOURCES_SHA256)
    assert _all_sources_digest(lookdev=True, ld_shadow=True) == (1024, PINNED_LD_SHADOW_SOURCES_SHA256)
    locations = {"position": 0, "normal": 1}
    for look, iris in ((False, False), (True, False), (True, True)):
        args = (locations, "V2", 3, "studio", True)
        worklight = es.shell_sources(*args, look=look, iris=iris)
        assert es.shell_sources(*args, look=look, iris=iris, ld_shadow=True) == worklight
        looked = es.shell_sources(*args, look=look, iris=iris, lookdev=True)[1][0]
        shadowed = es.shell_sources(*args, look=look, iris=iris, lookdev=True, ld_shadow=True)[1][0]
        assert "LD_SHADOW" not in looked and "ld_key_vis" not in looked and "u_ld_shadow" not in looked
        assert "#define LD_SHADOW 1\n" in shadowed and shadowed.count(ls.LD_SHADOW_SRC) == 1
        assert shadowed.index(ls.LD_COMMON_SRC) < shadowed.index(ls.LD_SHADOW_SRC) < shadowed.index("void main()")
        assert shadowed.count("ld_key_vis = ld_key_visibility(") == 1  # once, at the start of main()
        assert shadowed.index("ld_key_vis = ld_key_visibility(") < shadowed.index("bool cornea =")


@pytest.mark.parametrize("look", ["plain", "soft", "point"])
def test_a_blocker_between_key_and_eye_darkens_every_key_term(gl_window, look):
    """T2-1 + parity (`lookdev_optics.eye_key_dimmed`): a plate between the key and the eye takes the key's light off
    the whole eye - the eye in its full shadow equals the eye under a key of intensity 0 (every key term scaled,
    ambient / fill / rim / the studio's reflection kept); a plate whose edge crosses the eye leaves each pixel between
    the two; without a blocker the eye equals the frame with the eye shadow off (the S1 eye)."""
    from viewport import lookdev_optics as lo

    spec = _s2_eye(look)
    state = _s2_state()
    on = _s2_state(effects=lo.LookdevEffects(shadow=True, eye_shadow=True))
    off = _s2_state(effects=lo.LookdevEffects(shadow=True, eye_shadow=False))
    mask = _eye_mask(gl_window, spec, state)
    assert mask.sum() > 3000
    lit = _render(gl_window, _s2_scene(spec, on, None)[0])
    viewport, _ = _s2_scene(spec, off, None)
    s1 = _render(gl_window, viewport)
    assert np.array_equal(lit, s1)  # no blocker: pixel for pixel the S1 eye
    assert not any(len(k) == 10 for k in viewport.eye_pass.programs)  # eye shadow off: the S1 program
    viewport, _ = _s2_scene(spec, on, "full")
    shadowed = _render(gl_window, viewport)
    keys = [k for k in viewport.eye_pass.programs if len(k) == 10]
    assert keys and all(k[7] and k[8] for k in keys)  # the LOOKDEV + LD_SHADOW program drew
    dark = _render(gl_window, _s2_scene(spec, _s2_state(intensity=0.0), "full")[0])
    eye = mask & ~_plate_mask(gl_window, spec, state, "full")
    assert eye.sum() > 0.8 * mask.sum()
    delta = np.abs(shadowed - dark)[eye]
    assert delta.max() <= 2 and delta.mean() < 0.05  # full shadow = no key, for every term
    drop = (lit - shadowed).max(-1)[eye]
    assert np.mean(drop > 8) > 0.3 and np.percentile(drop, 99) > 40  # the key's light is gone
    half = _render(gl_window, _s2_scene(spec, on, "half")[0])
    eye_half = mask & ~_plate_mask(gl_window, spec, state, "half")
    lo_, hi_ = np.minimum(lit, dark)[eye_half], np.maximum(lit, dark)[eye_half]
    value = half[eye_half]
    assert np.all(value >= lo_ - 2) and np.all(value <= hi_ + 2)
    near_dark = np.all(np.abs(value - dark[eye_half]) <= 2, -1)
    near_lit = np.all(np.abs(value - lit[eye_half]) <= 2, -1)
    changed = np.any(lit[eye_half] != dark[eye_half], -1)
    assert np.mean(near_dark & changed) > 0.05 and np.mean(near_lit & changed) > 0.05  # the edge crosses the eye


def test_the_twin_lights_the_plain_sclera_in_full_light_and_full_shadow(gl_window):
    """Parity of the key's scaling (`lookdev_optics.eye_sclera_shadowed`, the plain sclera: `lit` + GGX, AD-038
    B1 / B6) against the GPU on the sclera's pixels: visibility 1 without, 0 under the blocker."""
    from viewport import lookdev_optics as lo
    from viewport.eye_pass import LOOKDEV_SCLERA_ROUGHNESS

    spec = dataclasses.replace(DEFAULT_EYE, limbus_level=0)
    state = _s2_state(fill=lo.StudioLight(False), rim=lo.StudioLight(False))
    sclera = None
    for blocker, vis in ((None, 1.0), ("full", 0.0)):
        viewport, camera = _s2_scene(spec, state, blocker, yaw=35.0)
        img = _render(gl_window, viewport)
        frame = viewport.lookdev_frame()
        if sclera is None:
            kinds = _cpu_kinds(camera, "V2")
            sclera = kinds == -1
            for axis in (0, 1):
                sclera &= np.roll(kinds, 1, axis) == -1
                sclera &= np.roll(kinds, -1, axis) == -1
            sclera &= ~_plate_mask(gl_window, spec, state, "full", yaw=35.0)
            assert sclera.sum() > 2000
            eye, d = _camera_rays(camera)
            hit, t = eo.sphere_entry(np.broadcast_to(eye, d.shape), d, np.zeros(3), 1.0)
            n = eo.normalize(eye + t[..., None] * d)
        values = eye_uniforms(viewport._eye_entries["eye"])
        colour = lo.eye_sclera_shadowed(np.asarray(values["u_sclera_albedo"]), n, -d, LOOKDEV_SCLERA_ROUGHNESS,
                                        values["u_cornea_f0"], frame, np.full(n.shape[:2], vis))
        expected = np.round(lo.lookdev_output(colour, frame["u_ld_exposure"]) * 255.0)
        delta = np.abs(img - expected)[sclera]
        assert np.percentile(delta, 99) <= 3 and delta.mean() < 1.0, (blocker, delta.max())


def test_eye_shadow_or_shadow_off_is_the_s1_eye(gl_window):
    """T2-3: with a blocker over the eye, `eye_shadow` off or `shadow` off draws the eye of the S1 frame - the
    LOOKDEV program of before (pinned), no map bound for it; the grey card (E7) is unchanged by construction
    (`test_gl_lookdev_pass.py`)."""
    from viewport import lookdev_optics as lo

    spec = _s2_eye("soft")
    state = _s2_state()
    mask = _eye_mask(gl_window, spec, state) & ~_plate_mask(gl_window, spec, state, "full")
    frames = {}
    for name, effects in (("eye off", lo.LookdevEffects(shadow=True, eye_shadow=False)),
                          ("shadow off", lo.LookdevEffects(shadow=False, eye_shadow=True)),
                          ("on", lo.LookdevEffects())):
        viewport, _ = _s2_scene(spec, _s2_state(effects=effects), "full")
        drawn = []
        original = viewport.eye_pass.draw

        def spy(*args, **kw):
            drawn.append(kw.get("shadow"))
            return original(*args, **kw)

        viewport.eye_pass.draw = spy
        frames[name] = _render(gl_window, viewport)
        assert drawn and all((s is not None) == (name == "on") for s in drawn)
        assert all(len(k) == 9 for k in viewport.eye_pass.programs) == (name != "on")
    # the eye with no blocker in the S1 build: the LOOKDEV program, which does not read the map
    viewport, _ = _s2_scene(spec, _s2_state(effects=lo.LookdevEffects(shadow=True, eye_shadow=False)), None)
    s1 = _render(gl_window, viewport)
    assert np.array_equal(frames["eye off"][mask], s1[mask])
    assert np.array_equal(frames["shadow off"][mask], s1[mask])
    assert np.any(frames["on"][mask] != s1[mask])


def _units_state() -> dict:
    from pyglet import gl

    from gui.imgui_layer import snapshot_gl_state

    def geti(name):
        buf = (gl.GLint * 1)()
        gl.glGetIntegerv(name, buf)
        return buf[0]

    state = snapshot_gl_state()
    state.update(draw_fbo=geti(gl.GL_DRAW_FRAMEBUFFER_BINDING), read_fbo=geti(gl.GL_READ_FRAMEBUFFER_BINDING),
                 depth_func=geti(gl.GL_DEPTH_FUNC), offset_fill=bool(gl.glIsEnabled(gl.GL_POLYGON_OFFSET_FILL)))
    active = geti(gl.GL_ACTIVE_TEXTURE)
    for unit in range(8):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        state[f"unit{unit}"] = (geti(gl.GL_TEXTURE_BINDING_2D), geti(gl.GL_TEXTURE_BINDING_BUFFER),
                                geti(gl.GL_SAMPLER_BINDING))
    gl.glActiveTexture(active)
    return state


@pytest.mark.parametrize("look", ["plain", "soft"])
def test_ld_shadow_programs_draw_and_leave_the_gl_state_clean(gl_window, look):
    """T2-4: the LOOKDEV + LD_SHADOW eye draws (the map on unit 6) and leaves the GL state as found - units 0-7 with
    their sampler bindings, framebuffers, program, caps; `glGetError` 0."""
    from pyglet import gl

    spec = _s2_eye(look)
    viewport, _ = _s2_scene(spec, _s2_state(), "half")
    _render(gl_window, viewport)  # compiles, renders the map
    gl.glUseProgram(0)
    before = _units_state()
    for rotation in (0.0, 15.0):  # a still frame, then one that renders the map again
        viewport.set_shading("lookdev", _s2_state(rotation=rotation))
        img = _render(gl_window, viewport)
        assert _units_state() == before and gl.glGetError() == gl.GL_NO_ERROR
    assert np.sum(img.max(-1) > 0) > 3000
    assert any(len(k) == 10 and k[8] for k in viewport.eye_pass.programs)


def test_prepare_lookdev_compiles_the_eye_variant_the_effects_need(gl_window):
    """AD-039 §5 / I-10: `prepare_lookdev` compiles the LOOKDEV + LD_SHADOW eye program before the frame (no compile
    in a frame); without a caster, or with the eye shadow off, the eye's program is the LOOKDEV one of before."""
    from viewport import lookdev_optics as lo

    spec = _s2_eye("plain")
    viewport, _ = _s2_scene(spec, _s2_state(), None)
    assert viewport.lookdev_prepare_needed() and viewport.prepare_lookdev() >= 2  # the floor's skin, the eye
    keys = list(viewport.eye_pass.programs)
    assert len(keys) == 1 and len(keys[0]) == 10 and keys[0][8] and not viewport.lookdev_prepare_needed()
    _render(gl_window, viewport)
    assert list(viewport.eye_pass.programs) == keys  # the frame compiled nothing
    viewport.set_lookdev_effects(lo.LookdevEffects(shadow=True, eye_shadow=False))
    assert viewport.lookdev_prepare_needed() and viewport.prepare_lookdev() == 1
    assert sorted(len(k) for k in viewport.eye_pass.programs) == [9, 10]
    lonely, _ = _s2_scene(spec, _s2_state(), None, floor=False)
    lonely.prepare_lookdev()
    assert [len(k) for k in lonely.eye_pass.programs] == [9]  # nothing casts: no shadow program for the eye
