"""GPU parity of `lookdev_shaders` against `lookdev_optics` (AD-038 §6, E5): decode, tone curves and output, `sh9`,
`ld_studio`, `ld_diffuse`, GGX (`direct_specular`, `ld_specular`; AD-039 S3: `ld_direct_dual`, `ld_specular_dual`; S8:
`ld_area_wrap`, `ld_diffuse_area`), one fragment per input into an RGBA32F target. The `AREA_DIFFUSE` body blocks with and
without `SHADOW` / `DUAL_LOBE` in the real pass: `tests/test_gl_lookdev_shadow.py`.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_parity.py -q`."""

from __future__ import annotations

import ctypes

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from viewport import eye_shaders as es  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport import lookdev_shaders as ls  # noqa: E402

N = 2048
FUNCS = {"decode": 0, "output": 1, "sh9": 2, "studio": 3, "diffuse": 4, "direct": 5, "specular": 6, "direct_dual": 7,
         "specular_dual": 8, "area_wrap": 9, "diffuse_area": 10}

BODY = """
uniform samplerBuffer u_inputs;
uniform int u_width;
uniform int u_count;
uniform int u_func;
layout(location = 0) out vec4 out_value;
void main() {
    int i = int(gl_FragCoord.y) * u_width + int(gl_FragCoord.x);
    if (i >= u_count) { out_value = vec4(0.0); return; }
    vec4 a = texelFetch(u_inputs, 3 * i);
    vec4 b = texelFetch(u_inputs, 3 * i + 1);
    vec4 c = texelFetch(u_inputs, 3 * i + 2);
    vec3 o = vec3(0.0);
    if (u_func == 0) o = srgb_decode(a.xyz);
    else if (u_func == 1) o = lookdev_output(a.xyz);
    else if (u_func == 2) o = sh9(a.xyz);
    else if (u_func == 3) o = ld_studio(a.xyz, b.x);
    else if (u_func == 4) o = ld_diffuse(a.xyz, b.xyz);
    else if (u_func == 5) o = vec3(direct_specular(a.xyz, b.xyz, c.xyz, a.w, b.w));
    else if (u_func == 6) o = ld_specular(a.xyz, b.xyz, c.x, c.y);
    else if (u_func == 7) o = vec3(ld_direct_dual(a.xyz, b.xyz, c.xyz, a.w, c.w, b.w));
    else if (u_func == 8) o = ld_specular_dual(a.xyz, b.xyz, c.x, c.y);
    else if (u_func == 9) o = ld_area_wrap(a.x, b.xyz, a.y);
    else if (u_func == 10) o = ld_diffuse_area(a.xyz, b.xyz);
    out_value = vec4(o, 1.0);
}
"""

STUDIO = lo.Studio((0.25, 0.22, 0.2), (0.12, 0.12, 0.13), (0.03, 0.03, 0.035),
                   (lo.Softbox(40.0, 25.0, 25.0, 18.0, (6.0, 5.8, 5.5)), lo.Softbox(-120.0, 10.0, 5.0, 30.0, (3.0, 3.0, 3.2)),
                    lo.Softbox(180.0, 60.0, 30.0, 10.0, (1.0, 1.0, 1.0))))


def _state(**kw):
    values = dict(preset="parity", studio=STUDIO, key=lo.StudioLight(True, 1.6, 45.0, 30.0, 5600.0, 0.1),
                  fill=lo.StudioLight(True, 0.7, -60.0, 5.0, 6500.0, 0.25),
                  rim=lo.StudioLight(True, 1.4, -150.0, 25.0, 7500.0, 0.05), rotation=33.0, env_intensity=0.8,
                  exposure=0.5)
    values.update(kw)
    return lo.LookdevState(**values)


class _Parity:
    WIDTH = 256

    def __init__(self) -> None:
        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        from viewport.gl_render_store import _register_sampler_buffer_uniform

        _register_sampler_buffer_uniform()
        self.gl = gl
        fragment = ("#version 330 core\n" + ls.LD_BRDF_SRC + ls.LD_COMMON_SRC + ls.LD_AREA_SRC + ls.LD_DUAL_LOBE_SRC
                    + BODY)
        self.program = ShaderProgram(Shader(es.FULLSCREEN_VERTEX_SRC, "vertex"), Shader(fragment, "fragment"))

        def gen(fn) -> int:
            ident = gl.GLuint()
            fn(1, ctypes.byref(ident))
            return ident.value

        self.buffer, self.tex = gen(gl.glGenBuffers), gen(gl.glGenTextures)
        self.fbo, self.rbo, self.vao, self.vbo = (gen(gl.glGenFramebuffers), gen(gl.glGenRenderbuffers),
                                                  gen(gl.glGenVertexArrays), gen(gl.glGenBuffers))
        gl.glBindVertexArray(self.vao)
        tri = (gl.GLfloat * 6)(-1.0, -1.0, 3.0, -1.0, -1.0, 3.0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tri), tri, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
        gl.glBindVertexArray(0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

    def run(self, func: str, inputs: np.ndarray, values: dict) -> np.ndarray:
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
        values = dict(values, u_inputs=3, u_width=self.WIDTH, u_count=count, u_func=FUNCS[func])
        active = self.program.uniforms
        for name, value in values.items():
            if name in active:
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
        return out.reshape(-1, 4)[:count, :3].astype(np.float64)

    def release(self) -> None:
        gl = self.gl
        self.program.delete()
        for fn, ident in ((gl.glDeleteBuffers, self.buffer), (gl.glDeleteBuffers, self.vbo),
                          (gl.glDeleteTextures, self.tex), (gl.glDeleteFramebuffers, self.fbo),
                          (gl.glDeleteRenderbuffers, self.rbo), (gl.glDeleteVertexArrays, self.vao)):
            fn(1, ctypes.byref(gl.GLuint(ident)))


@pytest.fixture(scope="module")
def parity():
    try:
        win = pyglet.window.Window(width=64, height=64, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    p = _Parity()
    yield p
    p.release()
    win.close()


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


def _unit(n, seed):
    x = np.random.default_rng(seed).normal(size=(n, 3))
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def test_decode_and_output(parity):
    rng = np.random.default_rng(1)
    c = rng.uniform(-0.1, 1.1, (N, 3))
    values = lo.frame_uniforms(_state())
    got = parity.run("decode", _pack(c), values)
    assert np.abs(got - lo.srgb_decode(_f32(c))).max() < 2e-6
    hdr = rng.uniform(0.0, 6.0, (N, 3))
    for curve in ("reinhard", "clamp"):
        values = lo.frame_uniforms(_state(tone_curve=curve))
        got = parity.run("output", _pack(hdr), values)
        assert np.abs(got - lo.lookdev_output(_f32(hdr), values["u_ld_exposure"], curve)).max() < 2e-6


def test_sh9_and_ld_diffuse(parity):
    values = lo.frame_uniforms(_state())
    n = _unit(N, 2)
    got = parity.run("sh9", _pack(n), values)
    assert np.abs(got - lo.sh9_eval(values["u_ld_sh"], _f32(n))).max() < 2e-6
    wrap = np.random.default_rng(3).uniform(0.0, 0.5, (N, 3))
    got = parity.run("diffuse", _pack(np.c_[n, np.zeros(N)], wrap), values)
    assert np.abs(got - lo.ld_diffuse(_f32(n), _f32(wrap), values)).max() < 5e-6


@pytest.mark.parametrize("roughness", [0.0, 0.05, 0.3, 0.7])
def test_ld_studio(parity, roughness):
    values = lo.frame_uniforms(_state())
    d = _unit(N, 4)
    got = parity.run("studio", _pack(np.c_[d, np.zeros(N)], np.full(N, roughness)), values)
    ref = lo.ld_studio(_f32(d), roughness, STUDIO)
    assert np.abs(got - ref).max() < 2e-4 * max(1.0, float(ref.max()))  # atan / erf in float32 at the box edges


def test_ggx(parity):
    rng = np.random.default_rng(5)
    values = lo.frame_uniforms(_state())
    n = _unit(N, 6)
    v = lo.eo.normalize(n + rng.normal(scale=0.6, size=(N, 3)))
    l = lo.eo.normalize(n + rng.normal(scale=0.8, size=(N, 3)))
    rough, f0 = rng.uniform(0.1, 1.0, N), rng.uniform(0.02, 0.08, N)  # sharper lobes amplify float32 in h
    got = parity.run("direct", _pack(np.c_[n, rough], np.c_[v, f0], l), values)[:, 0]
    ref = lo.direct_specular(_f32(n), _f32(v), _f32(l), _f32(rough), _f32(f0))
    assert np.abs(got - ref).max() < 1e-3 * max(1.0, float(ref.max()))
    zero = np.zeros(N)
    got = parity.run("specular", _pack(np.c_[n, zero], np.c_[v, zero], np.c_[rough, f0]), values)
    ref = lo.ld_specular(_f32(n), _f32(v), _f32(rough), _f32(f0), values)
    assert np.abs(got - ref).max() < 1e-3 * max(1.0, float(ref.max()))


def test_dual_lobe(parity):
    """AD-039 §6 (S3): `ld_direct_dual` with random light sizes and `ld_specular_dual` with the frame's three lights
    against their NumPy twins."""
    rng = np.random.default_rng(7)
    values = lo.frame_uniforms(_state())
    n = _unit(N, 8)
    v = lo.eo.normalize(n + rng.normal(scale=0.6, size=(N, 3)))
    l = lo.eo.normalize(n + rng.normal(scale=0.8, size=(N, 3)))
    rough, f0, size = rng.uniform(0.1, 1.0, N), rng.uniform(0.02, 0.08, N), rng.uniform(0.0, 0.3, N)
    got = parity.run("direct_dual", _pack(np.c_[n, rough], np.c_[v, f0], np.c_[l, size]), values)[:, 0]
    ref = lo.ld_direct_dual(_f32(n), _f32(v), _f32(l), _f32(rough), _f32(size), _f32(f0))
    assert np.abs(got - ref).max() < 1e-3 * max(1.0, float(ref.max()))
    zero = np.zeros(N)
    got = parity.run("specular_dual", _pack(np.c_[n, zero], np.c_[v, zero], np.c_[rough, f0]), values)
    ref = lo.ld_specular_dual(_f32(n), _f32(v), _f32(rough), _f32(f0), values)
    assert np.abs(got - ref).max() < 1e-3 * max(1.0, float(ref.max()))
    # the dual lobe is not the single one (a sharper peak, a broader tail)
    single = lo.ld_specular(_f32(n), _f32(v), _f32(rough), _f32(f0), values)
    assert np.abs(ref - single).max() > 1e-3


def test_area_wrap_and_diffuse_area(parity):
    """AD-039 §23 (S8): `ld_area_wrap` over the band and both sides of it (sizes 0 - 1, wraps 0 - 0.5) and
    `ld_diffuse_area` with the frame's three lights at sizes 0.5 / 0.25 / 1 against their NumPy twins; size 0 is
    `ld_wrap` on the GPU too."""
    rng = np.random.default_rng(9)
    ndl, size = rng.uniform(-1.0, 1.0, N), rng.uniform(0.0, 1.0, N)
    size[:256] = 0.0
    wrap = rng.uniform(0.0, 0.5, (N, 3))
    values = lo.frame_uniforms(_state())
    got = parity.run("area_wrap", _pack(np.c_[ndl, size, np.zeros(N), np.zeros(N)], wrap), values)
    ref = lo.ld_area_wrap(_f32(ndl), _f32(wrap), _f32(size))  # per row: ndl, size and wrap broadcast row by row
    assert np.abs(got - ref).max() < 2e-6
    assert np.abs(got[:256] - lo.ld_wrap(_f32(ndl[:256]), _f32(wrap[:256]))).max() < 3e-5
    values = lo.frame_uniforms(_state(key=lo.StudioLight(True, 1.6, 45.0, 30.0, 5600.0, 0.5),
                                      fill=lo.StudioLight(True, 0.7, -60.0, 5.0, 6500.0, 0.25),
                                      rim=lo.StudioLight(True, 1.4, -150.0, 25.0, 7500.0, 1.0)))
    n = _unit(N, 10)
    got = parity.run("diffuse_area", _pack(np.c_[n, np.zeros(N)], wrap), values)
    ref = lo.ld_diffuse_area(_f32(n), _f32(wrap), values)
    assert np.abs(got - ref).max() < 5e-6
    assert np.abs(ref - lo.ld_diffuse(_f32(n), _f32(wrap), values)).max() > 1e-2  # the band is there
