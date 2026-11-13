"""Lookdev step 1 (2026-11-13): OpenGL capability probe for the Eye Proof - cube maps in RGBA8 / RGBA16F / RGBA32F,
explicit mip sampling (`textureLod`), linear and trilinear filtering, seamless cube filtering, and the GPU cost of a
full-frame cube fetch.

Usage (from the repo root; opens a hidden pyglet window and GL context of its own - no Mirai `Application`, no import
from `src/`):
    python experiments/lookdev_gpu_probe/probe_gl_caps.py
    python experiments/lookdev_gpu_probe/probe_gl_caps.py --images <folder>      # + seam panoramas as PNG

Every check renders into an offscreen framebuffer of its own and reads the result back with `glReadPixels`, so the
verdicts rest on sampled values, not on allocation succeeding:

A  allocation + sampling: full-mip cubes at 64..512 per format; a GLSL 330 shader samples 24 quadrant centres; the
   values must come back exactly (float formats carry values above 1 and down to 2^-10 that an 8-bit store loses).
B  explicit mip levels: one marker value per level and face; `textureLod` at integer lods, below 0 and above the
   last level, must return that level's marker.
C  filtering: bilinear on a linear gradient (on and between texel centres), and trilinear blending between levels
   (`textureLod` swept in 1/8 steps); errors in units of one texel / level step.
D  seams: a smooth function of the direction on every level; sample pairs straddling all 12 cube edges with
   GL_TEXTURE_CUBE_MAP_SEAMLESS disabled and enabled.
T  timing: one full-frame pass per variant (sphere-reflection directions, one `textureLod` per fragment, sharp and
   rough lod, seamless off / on, per format, plus a pass without fetch) into an RGBA8 offscreen target at 1024x768 and
   1920x1080, GL_TIME_ELAPSED p50 / p95 / min / max over --draws rounds after 5 unmeasured, variants interleaved.
R  hygiene: every GL object the probe made is deleted (`glIs*` false afterwards), the GL state it touched is back as
   it found it, and `glGetError` is clean.

Set the NVIDIA driver to "prefer maximum performance" first on the reference PC (REFERENCE_HARDWARE.md §2). A result
from a software renderer (llvmpipe, ...) says nothing about a GPU driver: the probe names it in its output. Plain ASCII.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

import numpy as np  # noqa: E402

from lookdev_gpu_probe import cube_math as cm  # noqa: E402

REPO_ROOT = _EXPERIMENTS_DIR.parent
PROBE_NAME = "Lookdev GL capability probe (2026-11-13)"
WINDOW_SIZE = (256, 256)  # the window is never drawn to; every pass has its own framebuffer
CHECK_SIZE = 64  # B, D: a 64^2 cube, 7 levels down to 1x1
GRADIENT_SIZE = 16  # C: few texels, so an 8-bit gradient has a large step
ALLOC_SIZES = (64, 128, 256, 512)
TIMING_SIZES = ((1024, 768), (1920, 1080))
TIMING_CUBE = 128
SHARP_LOD, ROUGH_LOD = 0.0, 4.5
WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 40
READBACK_WIDTH, READBACK_ROWS = 256, 128  # up to 32768 samples per pass
PANORAMA = (256, 128)
SAMPLE_UNIT, CUBE_UNIT = 1, 2  # unit 0 belongs to pyglet text / imgui in the app (audit I-5); kept free here too
SNAPSHOT_UNITS = 4

# Enums the probe may need beyond a GL 3.3 header (values from the GL registry).
GL_MAX_TEXTURE_MAX_ANISOTROPY = 0x84FF
NVX_DEDICATED_VIDMEM, NVX_TOTAL_AVAILABLE, NVX_CURRENT_AVAILABLE = 0x9047, 0x9048, 0x9049
NVX_EVICTION_COUNT, NVX_EVICTED_MEMORY = 0x904A, 0x904B
ATI_TEXTURE_FREE_MEMORY = 0x87FC
GL_CONTEXT_PROFILE_MASK, GL_CONTEXT_FLAGS = 0x9126, 0x821E
GL_TEXTURE_BUFFER_BINDING, GL_TEXTURE_BINDING_BUFFER = 0x8C2A, 0x8C2C
GL_CLAMP_READ_COLOR = 0x891C
ERROR_NAMES = {0x0500: "GL_INVALID_ENUM", 0x0501: "GL_INVALID_VALUE", 0x0502: "GL_INVALID_OPERATION",
               0x0505: "GL_OUT_OF_MEMORY", 0x0506: "GL_INVALID_FRAMEBUFFER_OPERATION"}
FBO_STATUS = {0x8CD5: "COMPLETE", 0x8CD6: "INCOMPLETE_ATTACHMENT", 0x8CD7: "INCOMPLETE_MISSING_ATTACHMENT",
              0x8CDD: "UNSUPPORTED", 0x8D56: "INCOMPLETE_MULTISAMPLE", 0x8219: "UNDEFINED"}
COMPONENT_TYPES = {0x1406: "FLOAT", 0x8C17: "UNORM", 0x8F9C: "SNORM", 0x1404: "INT", 0x1405: "UINT", 0: "NONE"}
INTERNAL_NAMES = {0x8058: "RGBA8", 0x881A: "RGBA16F", 0x8814: "RGBA32F", 0x1908: "RGBA"}

VERTEX_SRC = """#version 330 core
layout(location = 0) in vec2 a_position;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""

SAMPLE_FRAGMENT_SRC = """#version 330 core
// One fragment per sample: direction xyz and lod w from a buffer texture, the cube sampled with textureLod.
uniform samplerBuffer u_samples;
uniform samplerCube u_cube;
uniform int u_width;
uniform int u_count;
uniform float u_scale;
layout(location = 0) out vec4 frag_colour;
void main() {
    int i = int(gl_FragCoord.y) * u_width + int(gl_FragCoord.x);
    if (i >= u_count) {
        frag_colour = vec4(0.0);
        return;
    }
    vec4 s = texelFetch(u_samples, i);
    frag_colour = textureLod(u_cube, s.xyz, s.w) * u_scale;
}
"""

TIMING_FRAGMENT_SRC = """#version 330 core
// A close-up of a reflecting sphere filling the frame height: every fragment reflects the view off the sphere normal
// (pixels beyond the disc take the rim normal), so the lookups sweep all six faces and cross every edge.
uniform samplerCube u_cube;
uniform vec2 u_size;
uniform float u_lod;
uniform int u_fetches;
layout(location = 0) out vec4 frag_colour;
void main() {
    vec2 p = gl_FragCoord.xy / u_size * 2.0 - 1.0;
    p.x *= u_size.x / u_size.y;
    float r2 = dot(p, p);
    vec2 q = r2 > 0.98 ? p * inversesqrt(r2) * 0.99 : p;
    vec3 n = vec3(q, sqrt(max(1.0 - dot(q, q), 0.0)));
    vec3 r = reflect(vec3(0.0, 0.0, -1.0), n);
    vec3 colour = 0.5 + 0.5 * r;
    for (int k = 0; k < u_fetches; ++k) {
        colour += textureLod(u_cube, r + vec3(0.0, 0.002 * float(k), 0.0), u_lod).rgb;
    }
    frag_colour = vec4(colour / float(u_fetches + 1), 1.0);
}
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", nargs="+", default=[f"{w}x{h}" for w, h in TIMING_SIZES], metavar="WxH",
                        help="timing target sizes (default: 1024x768 1920x1080)")
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS, help="measured timing rounds")
    parser.add_argument("--cube-size", type=int, default=TIMING_CUBE, help="edge of the timing cube (power of two)")
    parser.add_argument("--rough-lod", type=float, default=ROUGH_LOD, help="lod of the 'rough' timing rows")
    parser.add_argument("--fetches", type=int, default=1, help="cube fetches per fragment in the timing rows")
    parser.add_argument("--alloc-sizes", nargs="+", type=int, default=list(ALLOC_SIZES), metavar="N",
                        help="cube edges for check A (default: 64 128 256 512)")
    parser.add_argument("--images", metavar="FOLDER", help="write seam panoramas (PNG) into this folder")
    parser.add_argument("--no-timing", action="store_true", help="skip T (checks only)")
    return parser


def parse_size(text: str) -> tuple[int, int]:
    w, _, h = text.lower().partition("x")
    if not (w.isdigit() and h.isdigit()) or int(w) < 1 or int(h) < 1:
        raise SystemExit(f"bad size {text!r}: expected WxH, e.g. 1920x1080")
    return int(w), int(h)


def cpu_name() -> str:
    """CPU model: Windows from the registry, Linux from /proc/cpuinfo (as `drag_cost/probe_drag_gl.cpu_name`)."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


# -- small GL helpers ------------------------------------------------------------------------------------------------


def drain_errors(gl) -> list[str]:
    errors = []
    for _ in range(32):
        code = gl.glGetError()
        if code == gl.GL_NO_ERROR:
            break
        errors.append(ERROR_NAMES.get(code, hex(code)))
    return errors


def get_ints(gl, enum: int, count: int = 1) -> tuple[int, ...] | None:
    buf = (gl.GLint * 16)()
    gl.glGetIntegerv(enum, buf)
    return None if drain_errors(gl) else tuple(buf[:count])


def get_floats(gl, enum: int, count: int = 1) -> tuple[float, ...] | None:
    buf = (gl.GLfloat * 16)()
    gl.glGetFloatv(enum, buf)
    return None if drain_errors(gl) else tuple(round(v, 6) for v in buf[:count])


def is_enabled(gl, cap: int) -> bool | None:
    value = bool(gl.glIsEnabled(cap))
    return None if drain_errors(gl) else value


def gl_string(gl, name: int, index: int | None = None) -> str:
    ptr = gl.glGetString(name) if index is None else gl.glGetStringi(name, index)
    text = ctypes.cast(ptr, ctypes.c_char_p).value if ptr else None
    drain_errors(gl)
    return text.decode("ascii", errors="replace") if text else ""


def c_name(text: str):
    return ctypes.create_string_buffer(text.encode("ascii"))


# -- GL state: snapshot, restore, diff -------------------------------------------------------------------------------


def _int_state(gl) -> list[tuple[str, int, int]]:
    return [
        ("GL_CURRENT_PROGRAM", gl.GL_CURRENT_PROGRAM, 1),
        ("GL_VERTEX_ARRAY_BINDING", gl.GL_VERTEX_ARRAY_BINDING, 1),
        ("GL_ARRAY_BUFFER_BINDING", gl.GL_ARRAY_BUFFER_BINDING, 1),
        ("GL_TEXTURE_BUFFER_BINDING", GL_TEXTURE_BUFFER_BINDING, 1),
        ("GL_DRAW_FRAMEBUFFER_BINDING", gl.GL_DRAW_FRAMEBUFFER_BINDING, 1),
        ("GL_READ_FRAMEBUFFER_BINDING", gl.GL_READ_FRAMEBUFFER_BINDING, 1),
        ("GL_RENDERBUFFER_BINDING", gl.GL_RENDERBUFFER_BINDING, 1),
        ("GL_ACTIVE_TEXTURE", gl.GL_ACTIVE_TEXTURE, 1),
        ("GL_VIEWPORT", gl.GL_VIEWPORT, 4),
        ("GL_UNPACK_ALIGNMENT", gl.GL_UNPACK_ALIGNMENT, 1),
        ("GL_PACK_ALIGNMENT", gl.GL_PACK_ALIGNMENT, 1),
        ("GL_UNPACK_ROW_LENGTH", gl.GL_UNPACK_ROW_LENGTH, 1),
        ("GL_PACK_ROW_LENGTH", gl.GL_PACK_ROW_LENGTH, 1),
        ("GL_CLAMP_READ_COLOR", GL_CLAMP_READ_COLOR, 1),
    ]


def _enable_state(gl) -> list[tuple[str, int]]:
    return [("GL_TEXTURE_CUBE_MAP_SEAMLESS", gl.GL_TEXTURE_CUBE_MAP_SEAMLESS), ("GL_DEPTH_TEST", gl.GL_DEPTH_TEST),
            ("GL_BLEND", gl.GL_BLEND), ("GL_CULL_FACE", gl.GL_CULL_FACE), ("GL_SCISSOR_TEST", gl.GL_SCISSOR_TEST),
            ("GL_FRAMEBUFFER_SRGB", gl.GL_FRAMEBUFFER_SRGB)]


def _unit_state(gl) -> list[tuple[str, int]]:
    return [("GL_TEXTURE_BINDING_2D", gl.GL_TEXTURE_BINDING_2D),
            ("GL_TEXTURE_BINDING_CUBE_MAP", gl.GL_TEXTURE_BINDING_CUBE_MAP),
            ("GL_TEXTURE_BINDING_BUFFER", GL_TEXTURE_BINDING_BUFFER)]


def snapshot(gl) -> dict:
    """The GL state this probe touches (and a few neighbours it must not), as plain values."""
    state: dict = {name: get_ints(gl, enum, n) for name, enum, n in _int_state(gl)}
    state.update({name: is_enabled(gl, cap) for name, cap in _enable_state(gl)})
    state["GL_COLOR_CLEAR_VALUE"] = get_floats(gl, gl.GL_COLOR_CLEAR_VALUE, 4)
    active = state["GL_ACTIVE_TEXTURE"][0] if state["GL_ACTIVE_TEXTURE"] else gl.GL_TEXTURE0
    for unit in range(SNAPSHOT_UNITS):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        for name, enum in _unit_state(gl):
            state[f"unit {unit} {name}"] = get_ints(gl, enum)
    gl.glActiveTexture(active)
    return state


def restore(gl, state: dict) -> None:
    """Puts back the bindings and switches a pass changes (the inverse of what the passes below do)."""

    def first(name: str, default: int = 0) -> int:
        value = state.get(name)
        return value[0] if value else default

    gl.glUseProgram(first("GL_CURRENT_PROGRAM"))
    gl.glBindVertexArray(first("GL_VERTEX_ARRAY_BINDING"))
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, first("GL_ARRAY_BUFFER_BINDING"))
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, first("GL_TEXTURE_BUFFER_BINDING"))
    gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, first("GL_DRAW_FRAMEBUFFER_BINDING"))
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, first("GL_READ_FRAMEBUFFER_BINDING"))
    gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, first("GL_RENDERBUFFER_BINDING"))
    targets = {"GL_TEXTURE_BINDING_2D": gl.GL_TEXTURE_2D, "GL_TEXTURE_BINDING_CUBE_MAP": gl.GL_TEXTURE_CUBE_MAP,
               "GL_TEXTURE_BINDING_BUFFER": gl.GL_TEXTURE_BUFFER}
    for unit in range(SNAPSHOT_UNITS):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        for name, target in targets.items():
            gl.glBindTexture(target, first(f"unit {unit} {name}"))
    gl.glActiveTexture(first("GL_ACTIVE_TEXTURE", gl.GL_TEXTURE0))
    if state.get("GL_VIEWPORT"):
        gl.glViewport(*state["GL_VIEWPORT"])
    seamless = state.get("GL_TEXTURE_CUBE_MAP_SEAMLESS")
    if seamless is not None:
        (gl.glEnable if seamless else gl.glDisable)(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)


@contextmanager
def preserved(gl):
    saved = snapshot(gl)
    try:
        yield
    finally:
        restore(gl, saved)


# -- resource bookkeeping --------------------------------------------------------------------------------------------


class Resources:
    """Every GL object the probe creates, so that all of them are deleted and the deletion can be checked."""

    KINDS = ("texture", "buffer", "framebuffer", "renderbuffer", "query", "vertex_array", "program", "shader")

    def __init__(self, gl) -> None:
        self.gl = gl
        self.live: dict[str, list[int]] = {kind: [] for kind in self.KINDS}
        self.created: dict[str, set[int]] = {kind: set() for kind in self.KINDS}  # names (drivers reuse them)
        self.made: dict[str, int] = {kind: 0 for kind in self.KINDS}

    def _add(self, kind: str, name: int) -> int:
        self.live[kind].append(name)
        self.created[kind].add(name)
        self.made[kind] += 1
        return name

    def _gen(self, kind: str, fn) -> int:
        name = self.gl.GLuint()
        fn(1, ctypes.byref(name))
        return self._add(kind, name.value)

    def texture(self) -> int:
        return self._gen("texture", self.gl.glGenTextures)

    def buffer(self) -> int:
        return self._gen("buffer", self.gl.glGenBuffers)

    def framebuffer(self) -> int:
        return self._gen("framebuffer", self.gl.glGenFramebuffers)

    def renderbuffer(self) -> int:
        return self._gen("renderbuffer", self.gl.glGenRenderbuffers)

    def query(self) -> int:
        return self._gen("query", self.gl.glGenQueries)

    def vertex_array(self) -> int:
        return self._gen("vertex_array", self.gl.glGenVertexArrays)

    def program(self, vertex_src: str, fragment_src: str) -> int:
        gl = self.gl
        program = self._add("program", gl.glCreateProgram())
        shaders = []
        try:
            for source, kind in ((vertex_src, gl.GL_VERTEX_SHADER), (fragment_src, gl.GL_FRAGMENT_SHADER)):
                shader = self._add("shader", gl.glCreateShader(kind))
                shaders.append(shader)
                text = ctypes.create_string_buffer(source.encode("ascii"))
                pointer = ctypes.cast(ctypes.pointer(ctypes.cast(text, ctypes.POINTER(gl.GLchar))),
                                      ctypes.POINTER(ctypes.POINTER(gl.GLchar)))
                gl.glShaderSource(shader, 1, pointer, None)
                gl.glCompileShader(shader)
                status = gl.GLint()
                gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS, ctypes.byref(status))
                if not status.value:
                    raise RuntimeError(f"shader compile failed: {self._log(shader, gl.glGetShaderInfoLog)}")
                gl.glAttachShader(program, shader)
            gl.glLinkProgram(program)
            status = gl.GLint()
            gl.glGetProgramiv(program, gl.GL_LINK_STATUS, ctypes.byref(status))
            if not status.value:
                raise RuntimeError(f"program link failed: {self._log(program, gl.glGetProgramInfoLog)}")
        finally:
            for shader in shaders:
                gl.glDetachShader(program, shader)
                self.delete("shader", shader)
        return program

    def _log(self, name: int, fn) -> str:
        buf = ctypes.create_string_buffer(4096)
        length = self.gl.GLsizei()
        fn(name, 4096, ctypes.byref(length), ctypes.cast(buf, ctypes.POINTER(self.gl.GLchar)))
        return buf.value.decode("ascii", errors="replace").strip()

    def delete(self, kind: str, name: int) -> None:
        gl = self.gl
        if name not in self.live[kind]:
            return
        self.live[kind].remove(name)
        ref = ctypes.byref(gl.GLuint(name))
        {"texture": lambda: gl.glDeleteTextures(1, ref), "buffer": lambda: gl.glDeleteBuffers(1, ref),
         "framebuffer": lambda: gl.glDeleteFramebuffers(1, ref),
         "renderbuffer": lambda: gl.glDeleteRenderbuffers(1, ref), "query": lambda: gl.glDeleteQueries(1, ref),
         "vertex_array": lambda: gl.glDeleteVertexArrays(1, ref), "program": lambda: gl.glDeleteProgram(name),
         "shader": lambda: gl.glDeleteShader(name)}[kind]()

    def release_all(self) -> None:
        self.gl.glUseProgram(0)  # a program in use is only flagged for deletion
        for kind in reversed(self.KINDS):
            for name in list(self.live[kind]):
                self.delete(kind, name)

    def leaks(self) -> list[str]:
        """Names still alive after `release_all` (by the probe's own list and by `glIs*`)."""
        gl = self.gl
        checks = {"texture": gl.glIsTexture, "buffer": gl.glIsBuffer, "framebuffer": gl.glIsFramebuffer,
                  "renderbuffer": gl.glIsRenderbuffer, "query": gl.glIsQuery, "vertex_array": gl.glIsVertexArray,
                  "program": gl.glIsProgram, "shader": gl.glIsShader}
        found = [f"{kind} {name} (not deleted)" for kind in self.KINDS for name in self.live[kind]]
        found += [f"{kind} {name} (glIs* true after delete)" for kind in self.KINDS
                  for name in sorted(self.created[kind]) if checks[kind](name)]
        drain_errors(gl)
        return found

    def counts(self) -> str:
        return ", ".join(f"{self.made[kind]} {kind}" for kind in self.KINDS if self.made[kind])


# -- GL objects of the passes ----------------------------------------------------------------------------------------


def fullscreen_triangle(gl, res: Resources) -> int:
    """A VAO with one triangle covering the viewport (attribute 0, so no compatibility-profile surprises)."""
    vao, vbo = res.vertex_array(), res.buffer()
    data = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype=np.float32)
    with preserved(gl):
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data.ctypes.data, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
    return vao


def colour_target(gl, res: Resources, internal: int, width: int, height: int) -> tuple[int, int, str]:
    """An FBO with one colour renderbuffer; (fbo, renderbuffer, completeness)."""
    fbo, rb = res.framebuffer(), res.renderbuffer()
    with preserved(gl):
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, rb)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, internal, width, height)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, rb)
        status = FBO_STATUS.get(gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER), "unknown")
    errors = drain_errors(gl)
    return fbo, rb, status if not errors else f"{status} ({', '.join(errors)})"


def make_cube(gl, res: Resources, fmt: cm.CubeFormat, levels: list[np.ndarray]) -> tuple[int, list[str], str]:
    """A cube map with the given mip levels, trilinear, clamp to edge; (texture, GL errors, what the driver reports
    for level 0 of +X: internal format, red component type and size)."""
    internal = {"RGBA8": gl.GL_RGBA8, "RGBA16F": gl.GL_RGBA16F, "RGBA32F": gl.GL_RGBA32F}[fmt.internal]
    gl_type = {"ubyte": gl.GL_UNSIGNED_BYTE, "half": gl.GL_HALF_FLOAT, "float": gl.GL_FLOAT}[fmt.upload]
    tex = res.texture()
    drain_errors(gl)
    with preserved(gl):
        gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, tex)
        for pname, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR),
                             (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE),
                             (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE),
                             (gl.GL_TEXTURE_BASE_LEVEL, 0), (gl.GL_TEXTURE_MAX_LEVEL, len(levels) - 1)):
            gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, pname, value)
        for level, values in enumerate(levels):
            data = cm.to_upload(values, fmt)
            n = data.shape[1]
            for face in range(6):
                image = np.ascontiguousarray(data[face])
                gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, internal, n, n, 0, gl.GL_RGBA,
                                gl_type, image.ctypes.data)
        reported = []
        for pname in (gl.GL_TEXTURE_INTERNAL_FORMAT, gl.GL_TEXTURE_RED_TYPE, gl.GL_TEXTURE_RED_SIZE):
            value = gl.GLint()
            gl.glGetTexLevelParameteriv(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X, 0, pname, ctypes.byref(value))
            reported.append(value.value)
        errors = drain_errors(gl)
    driver = (f"{INTERNAL_NAMES.get(reported[0], hex(reported[0]))}, "
              f"R {COMPONENT_TYPES.get(reported[1], hex(reported[1]))} {reported[2]} bit")
    return tex, errors, driver


class SamplePass:
    """Samples a cube at a list of (direction, lod) and reads the results back as float."""

    def __init__(self, gl, res: Resources) -> None:
        self.gl, self.res = gl, res
        self.program = res.program(VERTEX_SRC, SAMPLE_FRAGMENT_SRC)
        self.vao = fullscreen_triangle(gl, res)
        self.sample_buffer, self.sample_texture = res.buffer(), res.texture()
        self.fbo, self.rb, status = colour_target(gl, res, gl.GL_RGBA32F, READBACK_WIDTH, READBACK_ROWS)
        self.float_target = status == "COMPLETE"
        self.target_report = f"RGBA32F colour renderbuffer: {status}"
        if not self.float_target:  # fall back to the RGBA8 target the picker uses on the reference PC
            res.delete("framebuffer", self.fbo)
            res.delete("renderbuffer", self.rb)
            self.fbo, self.rb, status8 = colour_target(gl, res, gl.GL_RGBA8, READBACK_WIDTH, READBACK_ROWS)
            if status8 != "COMPLETE":
                raise RuntimeError(f"no read-back target: RGBA32F {status}, RGBA8 {status8}")
            self.target_report += " -> fallback RGBA8 (values scaled into [0, 1], 8-bit read-back step)"
        self.locations = {name: gl.glGetUniformLocation(self.program, c_name(name))
                          for name in ("u_samples", "u_cube", "u_width", "u_count", "u_scale")}

    @property
    def capacity(self) -> int:
        return READBACK_WIDTH * READBACK_ROWS

    def run(self, cube: int, dirs: np.ndarray, lods, value_max: float = 1.0,
            seamless: bool = True) -> tuple[np.ndarray, float]:
        """(values (n, 4) float64, read-back step). With the RGBA8 fallback the shader scales by 1 / value_max."""
        gl = self.gl
        dirs = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
        count = len(dirs)
        if count > self.capacity:
            raise ValueError(f"{count} samples > {self.capacity}")
        data = np.empty((count, 4), dtype=np.float32)
        data[:, :3] = dirs
        data[:, 3] = np.broadcast_to(np.asarray(lods, dtype=np.float64), (count,))
        scale = 1.0 if self.float_target else 1.0 / value_max
        rows = -(-count // READBACK_WIDTH)
        out = np.zeros((rows, READBACK_WIDTH, 4), dtype=np.float32)
        with preserved(gl):
            gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, self.sample_buffer)
            gl.glBufferData(gl.GL_TEXTURE_BUFFER, data.nbytes, data.ctypes.data, gl.GL_STREAM_DRAW)
            gl.glActiveTexture(gl.GL_TEXTURE0 + SAMPLE_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_BUFFER, self.sample_texture)
            gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, self.sample_buffer)
            gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, cube)
            (gl.glEnable if seamless else gl.glDisable)(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
            gl.glViewport(0, 0, READBACK_WIDTH, rows)
            gl.glUseProgram(self.program)
            loc = self.locations
            gl.glUniform1i(loc["u_samples"], SAMPLE_UNIT)
            gl.glUniform1i(loc["u_cube"], CUBE_UNIT)
            gl.glUniform1i(loc["u_width"], READBACK_WIDTH)
            gl.glUniform1i(loc["u_count"], count)
            gl.glUniform1f(loc["u_scale"], scale)
            gl.glBindVertexArray(self.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glReadPixels(0, 0, READBACK_WIDTH, rows, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data)
        values = out.reshape(-1, 4)[:count].astype(np.float64) / scale
        return values, (0.0 if self.float_target else value_max / 255.0)


# -- the checks ------------------------------------------------------------------------------------------------------


class Report:
    """Lines for the output and one verdict per (check, format)."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.verdicts: dict[str, list[tuple[str, str]]] = {}

    def add(self, line: str = "") -> None:
        self.lines.append(line)

    def verdict(self, check: str, label: str, status: str) -> None:
        self.verdicts.setdefault(check, []).append((label, status))


def memory_kib(gl, extensions: set[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    if "GL_NVX_gpu_memory_info" in extensions:
        for name, enum in (("dedicated", NVX_DEDICATED_VIDMEM), ("total available", NVX_TOTAL_AVAILABLE),
                           ("current available", NVX_CURRENT_AVAILABLE), ("eviction count", NVX_EVICTION_COUNT),
                           ("evicted", NVX_EVICTED_MEMORY)):
            value = get_ints(gl, enum)
            if value is not None:
                out[name] = value[0]
    if "GL_ATI_meminfo" in extensions:
        value = get_ints(gl, ATI_TEXTURE_FREE_MEMORY, 4)
        if value is not None:
            out["texture free (ATI)"] = value[0]
    return out


def free_kib(gl, extensions: set[str]) -> int | None:
    mem = memory_kib(gl, extensions)
    return mem.get("current available", mem.get("texture free (ATI)"))


def mib(n_bytes: float) -> str:
    return f"{n_bytes / 2 ** 20:.2f} MiB"


def check_allocation(gl, res, sp: SamplePass, fmt: cm.CubeFormat, sizes: list[int], max_cube: int,
                     extensions: set[str], report: Report) -> None:
    dirs, keys = cm.quadrant_samples()
    intended = np.array([cm.quadrant_value(f, q, fmt.hdr) for f, q in keys])
    expected = cm.stored(intended, fmt)
    rel = {"RGBA16F": 1e-3, "RGBA32F": 1e-5}.get(fmt.internal, 0.0)  # 16F: one half-float step for driver rounding
    statuses = []
    for size in sizes:
        if size > max_cube:
            report.add(f"    {size:>4}^2  skipped: larger than GL_MAX_CUBE_MAP_TEXTURE_SIZE {max_cube}")
            continue
        before = free_kib(gl, extensions)
        start = time.perf_counter()
        tex, errors, driver = make_cube(gl, res, fmt, cm.quadrant_pattern(size, fmt.hdr))
        gl.glFinish()
        upload_ms = (time.perf_counter() - start) * 1000.0
        values, quantum = sp.run(tex, dirs, 0.0, value_max=float(np.max(expected)))
        errors += drain_errors(gl)
        after = free_kib(gl, extensions)
        ok = cm.within(values, expected, 1e-5 + quantum, rel)
        status = cm.PASS if ok.all() and not errors else cm.FAIL
        statuses.append(status)
        memory = f"computed {mib(cm.cube_bytes(size, fmt.bytes_per_texel))}"
        if before is not None and after is not None:
            memory += f", free video memory {(after - before) / 1024:+.2f} MiB"
        hint = cm.clamp_diagnosis(values, expected) if status == cm.FAIL else ""
        report.add(f"    {size:>4}^2  driver: {driver}; GL errors: {', '.join(errors) or 'none'}; "
                   f"sampled {int(ok.sum())}/{len(ok)} exact, max err {cm.max_error(values, expected):.3g}; "
                   f"upload+mips {upload_ms:.1f} ms; {memory}  {status}" + (f"  ({hint})" if hint else ""))
        res.delete("texture", tex)
    report.verdict("A", fmt.label, cm.FAIL if cm.FAIL in statuses else (cm.PASS if statuses else cm.OPEN))


def check_mips(gl, res, sp: SamplePass, fmt: cm.CubeFormat, report: Report) -> None:
    """B (integer lods) and C2 (fractional lods) on the marker cube."""
    levels = len(cm.level_sizes(CHECK_SIZE))
    tex, errors, _ = make_cube(gl, res, fmt, cm.marker_pattern(CHECK_SIZE, fmt.hdr))
    dirs, faces = cm.marker_directions()

    def stored(v):
        return cm.stored(v, fmt)

    def sample(lods: list[float]) -> tuple[np.ndarray, np.ndarray, float]:
        all_dirs = np.tile(dirs, (len(lods), 1))
        all_lods = np.repeat(lods, len(dirs))
        expected = np.array([cm.marker_expected(lod, int(f), levels, fmt.hdr, stored)
                             for lod, f in zip(all_lods, np.tile(faces, len(lods)))])
        values, quantum = sp.run(tex, all_dirs, all_lods, value_max=float(np.max(expected)))
        return values, expected, quantum

    integer_lods = [-1.0] + [float(k) for k in range(levels)] + [float(levels), levels + 1.5]
    values, expected, quantum = sample(integer_lods)
    errors += drain_errors(gl)
    mask = cm.marker_mask(len(integer_lods))
    rel = 1e-3 if fmt.internal == "RGBA16F" else 1e-5
    ok = cm.within(values, expected, 1e-5 + quantum, rel, mask)
    per_lod = ok.reshape(len(integer_lods), len(dirs)).all(axis=1)
    status_b = cm.PASS if ok.all() and not errors else cm.FAIL
    wrong = [f"{lod:g}" for lod, good in zip(integer_lods, per_lod) if not good]
    report.add(f"  [B] {fmt.label:<8} lods {', '.join(f'{v:g}' for v in integer_lods)} x 12 directions: "
               f"{int(ok.sum())}/{len(ok)} exact, max err {cm.max_error(values, expected, mask):.3g}"
               + (f", wrong at lod {', '.join(wrong)}" if wrong else "")
               + f"; GL errors: {', '.join(errors) or 'none'}  {status_b}")
    report.verdict("B", fmt.label, status_b)

    sweep = [round(k * 0.1, 6) for k in range(10 * (levels - 1) + 1)]  # tenths: not exact in a binary lod fraction
    values, expected, quantum = sample(sweep)
    mask = cm.marker_mask(len(sweep))
    step = cm.marker_step(fmt.hdr)
    err = cm.max_error(values, expected, mask) / step
    tolerance = 0.02 + (0.5 * fmt.quantum + quantum) / step
    monotonic = bool(np.all(np.diff(values[:, 0].reshape(len(sweep), len(dirs)), axis=0) >= -1e-6))
    status_c2 = cm.PASS if err <= tolerance and monotonic and not drain_errors(gl) else cm.FAIL
    report.add(f"  [C] {fmt.label:<8} trilinear: lod 0..{levels - 1} in 0.1 steps x 12 directions, max err "
               f"{err:.4f} level step (tolerance {tolerance:.4f}), monotonic {'yes' if monotonic else 'NO'}  "
               f"{status_c2}")
    res.delete("texture", tex)
    report.verdict("C", f"{fmt.label} trilinear", status_c2)


def check_gradient(gl, res, sp: SamplePass, fmt: cm.CubeFormat, report: Report) -> None:
    """C1: bilinear filtering inside a level, on and between texel centres, both axes, every face."""
    tex, errors, _ = make_cube(gl, res, fmt, cm.gradient_pattern(GRADIENT_SIZE, fmt.hdr))
    dirs, expected = cm.gradient_samples(GRADIENT_SIZE, fmt.hdr)
    values, quantum = sp.run(tex, dirs, 0.0, value_max=float(np.max(expected)) or 1.0)
    errors += drain_errors(gl)
    step = cm.gradient_step(fmt.hdr)
    err = cm.max_error(values[:, :2], expected) / step
    tolerance = 0.02 + (0.5 * fmt.quantum + quantum) / step
    status = cm.PASS if err <= tolerance and not errors else cm.FAIL
    hint = "  (about 0.5 means nearest filtering)" if err >= 0.25 else ""
    report.add(f"  [C] {fmt.label:<8} bilinear: {len(dirs)} samples on a {GRADIENT_SIZE}^2 gradient (fifths of a "
               f"texel), max err {err:.4f} texel step (tolerance {tolerance:.4f}; 8-bit weights give <= 0.002); "
               f"GL errors: {', '.join(errors) or 'none'}  {status}{hint}")
    res.delete("texture", tex)
    report.verdict("C", f"{fmt.label} bilinear", status)


def check_seams(gl, res, sp: SamplePass, fmt: cm.CubeFormat, report: Report, images: Path | None) -> None:
    levels = cm.smooth_pattern(CHECK_SIZE)
    tex, errors, _ = make_cube(gl, res, fmt, levels)
    samples = cm.seam_samples()
    stored_levels = [cm.stored(level, fmt) for level in levels]
    keys = ("a", "b", "ia", "ib")
    per_level = len(samples["a"])
    dirs = np.concatenate([samples[k] for _ in levels for k in keys])
    lods = np.concatenate([np.full(per_level, float(level)) for level in range(len(levels)) for _ in keys])
    measured = {}
    for seamless in (False, True):
        values, quantum = sp.run(tex, dirs, lods, seamless=seamless)
        measured[seamless] = values.reshape(len(levels), len(keys), per_level, 4)
    errors += drain_errors(gl)
    rows, emulation = [], 0.0
    for level, (n, content) in enumerate(zip(cm.level_sizes(CHECK_SIZE), stored_levels)):
        off, on = measured[False][level], measured[True][level]
        rows.append(cm.SeamRow(level, n, cm.seam_step(content, samples), cm.max_jump(off[0], off[1]),
                               cm.max_jump(on[0], on[1]), cm.max_jump(on[2], on[3])))
        for k, key in enumerate(("a", "b")):
            emulation = max(emulation, cm.max_error(off[k][:, :3], cm.bilinear_clamp(content, samples[key])[:, :3]))
    total_quantum = fmt.quantum + quantum
    status, reading = cm.seam_verdict(rows, total_quantum)
    if errors:
        status, reading = cm.FAIL, f"GL errors {', '.join(errors)}; " + reading
    report.add(f"  [D] {fmt.label:<8} 12 edges x {len(cm.SEAM_POSITIONS)} positions, pairs {cm.SEAM_DELTA:g} either "
               f"side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge "
               f"bilinear per face")
    report.add(f"      {'level':>5} {'size':>5} {'expected off':>13} {'jump off':>9} {'jump on':>9} "
               f"{'interior':>9} {'on <= tol':>10}")
    for r in rows:
        tol = cm.seam_tolerance(r, total_quantum)
        report.add(f"      {r.level:>5} {r.size:>5} {r.step:>13.5f} {r.jump_off:>9.5f} {r.jump_on:>9.5f} "
                   f"{r.interior:>9.5f} {'yes' if r.jump_on <= tol else 'NO':>10}")
    report.add(f"      seamless-off values vs the clamp-to-edge emulation: max err {emulation:.2g}")
    report.add(f"      -> {status}: {reading}")
    report.verdict("D", fmt.label, status)
    if images is not None:
        write_panorama(gl, sp, tex, len(levels), images / f"seams_{fmt.label}.png")
        report.add(f"      image: {images / f'seams_{fmt.label}.png'} (rows lod "
                   f"{', '.join(str(v) for v in panorama_lods(len(levels)))} top to bottom; left seamless off, "
                   f"right on)")
    res.delete("texture", tex)


def panorama_lods(levels: int) -> list[int]:
    return sorted({0, levels // 2, levels - 2, levels - 1})


def write_panorama(gl, sp: SamplePass, tex: int, levels: int, path: Path) -> None:
    width, height = PANORAMA
    dirs = cm.equirect_directions(width, height).reshape(-1, 3)
    rows = []
    for lod in panorama_lods(levels):
        tiles = [sp.run(tex, dirs, float(lod), seamless=seamless)[0][:, :3].reshape(height, width, 3)
                 for seamless in (False, True)]
        tiles.insert(1, np.ones((height, 2, 3)))  # a white divider
        rows.append(np.concatenate(tiles, axis=1))
        rows.append(np.ones((2, 2 * width + 2, 3)))
    path.parent.mkdir(parents=True, exist_ok=True)
    cm.write_png(path, np.concatenate(rows[:-1], axis=0))


def timing(gl, res, sizes: list[tuple[int, int]], cube_size: int, rough_lod: float, draws: int, fetches: int,
           max_renderbuffer: int, report: Report) -> None:
    program = res.program(VERTEX_SRC, TIMING_FRAGMENT_SRC)
    vao = fullscreen_triangle(gl, res)
    loc = {name: gl.glGetUniformLocation(program, c_name(name)) for name in ("u_cube", "u_size", "u_lod", "u_fetches")}
    cubes = {}
    for fmt in cm.FORMATS:
        tex, errors, _ = make_cube(gl, res, fmt, cm.smooth_pattern(cube_size))
        cubes[fmt.label] = tex
        if errors:
            report.add(f"  {fmt.label} timing cube: GL errors {', '.join(errors)}")
    variants = [("no fetch (baseline)", cubes[cm.RGBA8.label], 0.0, False, 0)]
    for fmt in cm.FORMATS:
        for lod, lod_name in ((SHARP_LOD, "sharp"), (rough_lod, "rough")):
            for seamless in (False, True):
                variants.append((f"{fmt.label} {lod_name} lod {lod:g} seamless {'on' if seamless else 'off'}",
                                 cubes[fmt.label], lod, seamless, fetches))
    query = res.query()
    report.add(f"  cube {cube_size}^2 + mips (smooth content), {fetches} textureLod per fragment, full-frame "
               f"sphere-reflection directions; {draws} rounds after {WARMUP_ROUNDS}, variants interleaved")
    for width, height in sizes:
        if max(width, height) > max_renderbuffer:
            report.add(f"  {width}x{height}: skipped, larger than GL_MAX_RENDERBUFFER_SIZE {max_renderbuffer}")
            continue
        fbo, rb, status = colour_target(gl, res, gl.GL_RGBA8, width, height)
        if status != "COMPLETE":
            report.add(f"  {width}x{height}: RGBA8 target {status}, skipped")
            continue
        samples: dict[str, list[float]] = {name: [] for name, *_ in variants}
        value = ctypes.c_uint64()
        with preserved(gl):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glViewport(0, 0, width, height)
            gl.glUseProgram(program)
            gl.glUniform1i(loc["u_cube"], CUBE_UNIT)
            gl.glUniform2f(loc["u_size"], float(width), float(height))
            gl.glBindVertexArray(vao)
            gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
            for round_ in range(WARMUP_ROUNDS + draws):
                for name, tex, lod, seamless, n_fetch in variants:
                    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, tex)
                    (gl.glEnable if seamless else gl.glDisable)(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
                    gl.glUniform1f(loc["u_lod"], lod)
                    gl.glUniform1i(loc["u_fetches"], n_fetch)
                    gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
                    gl.glEndQuery(gl.GL_TIME_ELAPSED)
                    gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
                    if round_ >= WARMUP_ROUNDS:
                        samples[name].append(value.value / 1e6)
        errors = drain_errors(gl)
        res.delete("framebuffer", fbo)
        res.delete("renderbuffer", rb)
        base = cm.timing_summary(samples[variants[0][0]])[0]
        pixels = width * height
        report.add(f"  {width}x{height} ({pixels} px, 100 % covered), GL_TIME_ELAPSED ms; GL errors: "
                   f"{', '.join(errors) or 'none'}")
        report.add(f"    {'variant':<42} {'p50':>7} {'p95':>7} {'min':>7} {'max':>7} {'- baseline':>11} "
                   f"{'ns/px':>6}")
        for name, *_ in variants:
            p50, p95, low, high = cm.timing_summary(samples[name])
            report.add(f"    {name:<42} {p50:7.3f} {p95:7.3f} {low:7.3f} {high:7.3f} {p50 - base:11.3f} "
                       f"{p50 * 1e6 / pixels:6.2f}")
        if cm.timing_unstable(samples):
            report.add("    NOTE the GPU times vary a lot: is the driver set to maximum performance?")
    for tex in cubes.values():
        res.delete("texture", tex)
    report.verdict("T", "timing", cm.INFO)


# -- main ------------------------------------------------------------------------------------------------------------


def context_info(gl, window, pyglet) -> tuple[list[str], dict, set[str], list[str]]:
    version = gl_string(gl, gl.GL_VERSION)
    renderer = gl_string(gl, gl.GL_RENDERER)
    count = get_ints(gl, gl.GL_NUM_EXTENSIONS) or (0,)
    extensions = sorted(gl_string(gl, gl.GL_EXTENSIONS, i) for i in range(count[0]))
    profile = get_ints(gl, GL_CONTEXT_PROFILE_MASK)
    profile_name = {1: "core", 2: "compatibility"}.get(profile[0] if profile else -1, "not reported")
    flags = get_ints(gl, GL_CONTEXT_FLAGS)
    try:
        screens = ", ".join(f"{s.width}x{s.height}" for s in pyglet.display.get_display().get_screens())
    except Exception as exc:  # noqa: BLE001 - informational only
        screens = f"unknown ({type(exc).__name__})"
    lines = [
        f"GL_VERSION: {version}",
        f"GL_RENDERER: {renderer}",
        f"GL_VENDOR: {gl_string(gl, gl.GL_VENDOR)}",
        f"GL_SHADING_LANGUAGE_VERSION: {gl_string(gl, gl.GL_SHADING_LANGUAGE_VERSION)}",
        f"Context: {profile_name} profile, flags {flags[0] if flags else 'n/a'}; pyglet default config "
        "(as src/main.py)",
        f"Window {window.width}x{window.height} (hidden), "
        f"framebuffer {'x'.join(map(str, window.get_framebuffer_size()))}, "
        f"scale {getattr(window, 'scale', 'n/a')}, dpi {getattr(window, 'dpi', 'n/a')}; screens: {screens}",
    ]
    limits: dict = {}
    for name, n in (("GL_MAX_TEXTURE_IMAGE_UNITS", 1), ("GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS", 1),
                    ("GL_MAX_TEXTURE_SIZE", 1), ("GL_MAX_CUBE_MAP_TEXTURE_SIZE", 1), ("GL_MAX_SAMPLES", 1),
                    ("GL_MAX_COLOR_ATTACHMENTS", 1), ("GL_MAX_DRAW_BUFFERS", 1), ("GL_MAX_TEXTURE_BUFFER_SIZE", 1),
                    ("GL_MAX_RENDERBUFFER_SIZE", 1), ("GL_MAX_VIEWPORT_DIMS", 2),
                    ("GL_MAX_FRAGMENT_UNIFORM_COMPONENTS", 1)):
        value = get_ints(gl, getattr(gl, name), n)
        limits[name] = (value if n > 1 else value[0]) if value else None
    bias = get_floats(gl, gl.GL_MAX_TEXTURE_LOD_BIAS)
    limits["GL_MAX_TEXTURE_LOD_BIAS"] = bias[0] if bias else None
    if {"GL_EXT_texture_filter_anisotropic", "GL_ARB_texture_filter_anisotropic"} & set(extensions):
        aniso = get_floats(gl, GL_MAX_TEXTURE_MAX_ANISOTROPY)
        limits["GL_MAX_TEXTURE_MAX_ANISOTROPY"] = aniso[0] if aniso else None
    return lines, limits, set(extensions), extensions


def run(args) -> list[str]:
    import pyglet
    from pyglet import gl

    sizes = [parse_size(s) for s in args.sizes]
    window = pyglet.window.Window(width=WINDOW_SIZE[0], height=WINDOW_SIZE[1], visible=False)
    window.switch_to()
    drain_errors(gl)  # anything pending belongs to context creation, not to the probe
    report = Report()
    lines = [
        f"{PROBE_NAME}: cube maps, textureLod, filtering, seams, full-frame fetch cost",
        f"Platform: {platform.platform()}",
        f"CPU: {cpu_name()} ({os.cpu_count()} logical cores)",
        f"Python: {platform.python_version()} ({platform.python_implementation()}), numpy {np.__version__}, "
        f"pyglet {pyglet.version}",
        f"Interpreter: {sys.executable}",
        f"Source: {cm.source_state(REPO_ROOT)}",
    ]
    info, limits, extensions, all_extensions = context_info(gl, window, pyglet)
    lines += info
    renderer = info[1].split(": ", 1)[1]
    if cm.software_renderer(renderer):
        lines.append("EVIDENCE: SOFTWARE RENDERER - these results are TESTED [C] at best and say nothing about the "
                     "9800 GTX driver; its GL_TIME_ELAPSED is not a GPU time.")
    else:
        lines.append("EVIDENCE: hardware renderer - label the results MEASURED [RPC] or MEASURED [MAIN] by machine.")
    lines.append("")
    lines.append("Limits:")
    for name, value in limits.items():
        lines.append(f"  {name:<38} {value if value is not None else 'query failed'}")
    lines.append("Extensions (Lookdev-relevant):")
    for name, why in cm.RELEVANT_EXTENSIONS:
        lines.append(f"  {'yes' if name in extensions else 'no ':<4} {name:<40} {why}")
    memory = memory_kib(gl, extensions)
    lines.append("GPU memory (KiB): " + (", ".join(f"{k} {v}" for k, v in memory.items()) if memory
                                         else "not exposed (neither GL_NVX_gpu_memory_info nor GL_ATI_meminfo)"))
    before = snapshot(gl)
    res = Resources(gl)
    images = Path(args.images).resolve() if args.images else None
    failures: list[str] = []

    def guarded(title: str, fn, *fn_args) -> None:
        try:
            fn(*fn_args)
        except Exception:  # noqa: BLE001 - a broken check is reported, the others still run
            failures.append(title)
            report.add(f"  ERROR in {title}:")
            report.add("    " + traceback.format_exc().strip().replace("\n", "\n    "))
            drain_errors(gl)

    try:
        sp = SamplePass(gl, res)
        report.add(f"Read-back target: {sp.target_report}")
        report.add("")
        max_cube = limits.get("GL_MAX_CUBE_MAP_TEXTURE_SIZE") or 0
        report.add("[A] cube allocation + sampling (full mip chain, textureLod lod 0 at 24 quadrant centres)")
        for fmt in cm.ALLOCATION_FORMATS:
            report.add(f"  {fmt.label}:")
            guarded(f"A {fmt.label}", check_allocation, gl, res, sp, fmt, args.alloc_sizes, max_cube, extensions,
                    report)
        report.add("")
        report.add(f"[B] explicit mip levels / [C] filtering ({CHECK_SIZE}^2 marker cube, {GRADIENT_SIZE}^2 gradient)")
        for fmt in cm.FORMATS:
            guarded(f"B/C {fmt.label}", check_mips, gl, res, sp, fmt, report)
            guarded(f"C {fmt.label}", check_gradient, gl, res, sp, fmt, report)
        report.add("")
        report.add(f"[D] seams ({CHECK_SIZE}^2 smooth cube, every level)")
        for fmt in cm.FORMATS:
            guarded(f"D {fmt.label}", check_seams, gl, res, sp, fmt, report, images)
        report.add("")
        if not args.no_timing:
            report.add("[T] full-frame cube fetch cost (RGBA8 offscreen target)")
            guarded("T", timing, gl, res, sizes, args.cube_size, args.rough_lod, args.draws, args.fetches,
                    limits.get("GL_MAX_RENDERBUFFER_SIZE") or 0, report)
            report.add("")
    except Exception:  # noqa: BLE001
        failures.append("setup")
        report.add("ERROR in setup:")
        report.add("  " + traceback.format_exc().strip().replace("\n", "\n  "))
    finally:
        restore(gl, before)
        res.release_all()
        gl.glFinish()
        leaks = res.leaks()
        after = snapshot(gl)
        diff = cm.state_diff(before, after)
        final_errors = drain_errors(gl)
        memory_after = memory_kib(gl, extensions)
        window.close()
    hygiene = cm.PASS if not leaks and not diff and not final_errors else cm.FAIL
    report.add("[R] resources and GL state")
    report.add(f"  created: {res.counts()}; still alive after release: {', '.join(leaks) or 'none'}")
    report.add(f"  GL state after the probe vs before: {'identical' if not diff else 'DIFFERENT: ' + '; '.join(diff)}")
    report.add(f"  glGetError at the end: {', '.join(final_errors) or 'none'}")
    if memory and memory_after:
        report.add("  GPU memory after release (KiB): " + ", ".join(f"{k} {v}" for k, v in memory_after.items()))
    report.add(f"  -> {hygiene}")
    report.verdict("R", "hygiene", hygiene)
    for title in failures:
        report.verdict("ERROR", title, cm.FAIL)
    lines += report.lines
    lines.append("")
    lines.append("Summary (raw verdicts of this run - label them by machine in the results file):")
    for check, entries in report.verdicts.items():
        lines.append(f"  {check:<5} " + "; ".join(f"{label} {status}" for label, status in entries))
    lines.append("")
    lines.append(f"All extensions ({len(all_extensions)}):")
    row = "  "
    for name in all_extensions:
        if len(row) + len(name) + 1 > 118:
            lines.append(row.rstrip())
            row = "  "
        row += name + " "
    lines.append(row.rstrip())
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for size in args.alloc_sizes + [args.cube_size]:
        cm.level_sizes(size)  # raises for a non-power of two
    for line in run(args):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
