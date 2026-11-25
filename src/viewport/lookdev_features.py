"""LookDev P3 feature checks (AD-039 §2.2): what this GL context can do for each effect, checked by function, never by
GPU name (`GL_RENDERER`).

`probe()` runs once per GL context, the first time an effect needs it (never with `shading == "worklight"`): the
`LookdevPass` holds the report. A failed check turns its effect off (`lookdev_optics.effective`) and the viewport shows
one status line; the check does not retry in the session. The report is a plain value, so LD-3 can read it later.

S1 adds `depth_texture`: a DEPTH_COMPONENT24 texture with `GL_COMPARE_REF_TO_TEXTURE` attached to an FBO -
`glCheckFramebufferStatus == COMPLETE` and `glGetError` 0. S4 adds `sampler_objects`: `glGenSamplers` succeeds and
`glGetError` stays 0. S7 adds `texture_units`: `GL_MAX_TEXTURE_IMAGE_UNITS` covers the highest unit the skin binds
+ 1 - since S6 the triangles' material slots (`lookdev_shaders.REGION_UNIT`, 12; the maps use 9-11), so 13; S6's region
materials need it too. S5 adds `cube_rgba16f`: an RGBA16F cube of the production size with every level
allocated, each face of each level attached to an FBO in turn - every attachment `GL_FRAMEBUFFER_COMPLETE`, `glGetError`
0 (the LD-0 (c) check; it does not detect the reference PC's defect with sampling an FBO-rendered cube, which
`viewport.lookdev_cube.EnvCube` works around by copying the cube, AD-039 §11.1 run 4 / 5). AD-040 §4.1 (LD-3a) adds
`timer_query`: a `GL_TIME_ELAPSED` query begun and ended without a GL error (missing: Auto holds Mittel).
"""

from __future__ import annotations

from dataclasses import dataclass, fields

#: The status line of a feature that is missing (German, the app's status language).
FEATURE_STATUS = {"depth_texture": "LookDev: Schatten aus – Tiefentextur nicht verfügbar",
                  "sampler_objects": "LookDev: Durchleuchtung aus – Sampler-Objekte nicht verfügbar",
                  "cube_rgba16f": "LookDev: Umgebungs-Cube aus – Cube-Ziel nicht verfügbar",
                  "texture_units": "LookDev: Maps und Region-Materialien aus – zu wenige Textureinheiten",
                  "timer_query": "Qualität: Auto aus – Zeitmessung nicht verfügbar"}


@dataclass(frozen=True)
class FeatureReport:
    """One GL context's P3 features (True = present)."""

    depth_texture: bool = True
    sampler_objects: bool = True
    cube_rgba16f: bool = True
    texture_units: bool = True
    timer_query: bool = True

    def missing(self) -> tuple[str, ...]:
        return tuple(f.name for f in fields(self) if not getattr(self, f.name))

    def status_lines(self) -> tuple[str, ...]:
        return tuple(FEATURE_STATUS.get(name, f"LookDev: {name} nicht verfügbar") for name in self.missing())


def _depth_texture() -> bool:
    """A small DEPTH_COMPONENT24 compare texture as an FBO's depth attachment: complete and no GL error. Leaves the
    framebuffer, the texture binding of unit 0 and the active unit as found and deletes what it made."""
    import ctypes

    from pyglet import gl

    while gl.glGetError() != gl.GL_NO_ERROR:  # an earlier error must not fail this check
        pass
    draw_fbo, read_fbo, bound, active = gl.GLint(), gl.GLint(), gl.GLint(), gl.GLint()
    gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(draw_fbo))
    gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING, ctypes.byref(read_fbo))
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D, ctypes.byref(bound))
    texture, fbo = gl.GLuint(), gl.GLuint()
    gl.glGenTextures(1, ctypes.byref(texture))
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture.value)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24, 16, 16, 0, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, None)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glBindTexture(gl.GL_TEXTURE_2D, bound.value)
    gl.glGenFramebuffers(1, ctypes.byref(fbo))
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_TEXTURE_2D, texture.value, 0)
    gl.glDrawBuffer(gl.GL_NONE)
    gl.glReadBuffer(gl.GL_NONE)
    complete = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
    gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw_fbo.value)
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read_fbo.value)
    gl.glDeleteFramebuffers(1, ctypes.byref(fbo))
    gl.glDeleteTextures(1, ctypes.byref(texture))
    gl.glActiveTexture(active.value)
    return complete and gl.glGetError() == gl.GL_NO_ERROR


def _sampler_objects() -> bool:
    """A sampler object (GL 3.3 core): generated with a non-zero name, a parameter set, deleted; no GL error."""
    import ctypes

    from pyglet import gl

    while gl.glGetError() != gl.GL_NO_ERROR:  # an earlier error must not fail this check
        pass
    ident = gl.GLuint()
    gl.glGenSamplers(1, ctypes.byref(ident))
    made = ident.value != 0
    if made:
        gl.glSamplerParameteri(ident.value, gl.GL_TEXTURE_COMPARE_MODE, gl.GL_NONE)
        gl.glDeleteSamplers(1, ctypes.byref(ident))
    return made and gl.glGetError() == gl.GL_NO_ERROR


def _cube_rgba16f() -> bool:
    """An RGBA16F cube (`CUBE_SIZE`, `CUBE_LEVELS`), every face of every level as an FBO's colour attachment: complete
    and no GL error. Leaves the framebuffers, the cube binding of unit 0 and the active unit as found and deletes what it
    made."""
    import ctypes

    from pyglet import gl

    from .lookdev_shaders import CUBE_LEVELS, CUBE_SIZE

    while gl.glGetError() != gl.GL_NO_ERROR:  # an earlier error must not fail this check
        pass
    draw_fbo, read_fbo, bound, active = gl.GLint(), gl.GLint(), gl.GLint(), gl.GLint()
    gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(draw_fbo))
    gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING, ctypes.byref(read_fbo))
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_CUBE_MAP, ctypes.byref(bound))
    texture, fbo = gl.GLuint(), gl.GLuint()
    gl.glGenTextures(1, ctypes.byref(texture))
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture.value)
    for level in range(CUBE_LEVELS):
        side = CUBE_SIZE >> level
        for face in range(6):
            gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA16F, side, side, 0, gl.GL_RGBA,
                            gl.GL_FLOAT, None)
    gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, gl.GL_TEXTURE_MAX_LEVEL, CUBE_LEVELS - 1)
    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, bound.value)
    gl.glGenFramebuffers(1, ctypes.byref(fbo))
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
    complete = True
    for level in range(CUBE_LEVELS):
        for face in range(6):
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                      gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, texture.value, level)
            complete = complete and gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
    gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw_fbo.value)
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read_fbo.value)
    gl.glDeleteFramebuffers(1, ctypes.byref(fbo))
    gl.glDeleteTextures(1, ctypes.byref(texture))
    gl.glActiveTexture(active.value)
    return complete and gl.glGetError() == gl.GL_NO_ERROR


def _texture_units() -> bool:
    """`GL_MAX_TEXTURE_IMAGE_UNITS` (fragment units) above the highest unit the skin pass binds (AD-039 §2.4)."""
    import ctypes

    from pyglet import gl

    from .lookdev_shaders import MAP_UNITS, REGION_UNIT

    units = gl.GLint()
    gl.glGetIntegerv(gl.GL_MAX_TEXTURE_IMAGE_UNITS, ctypes.byref(units))
    return units.value >= max(*MAP_UNITS.values(), REGION_UNIT) + 1


def _timer_query() -> bool:
    """AD-040 §4.1: a `GL_TIME_ELAPSED` query generated, begun, ended and deleted without a GL error (none is active
    meanwhile: a probe's own query around the frame must not fail this check)."""
    import ctypes

    from pyglet import gl

    while gl.glGetError() != gl.GL_NO_ERROR:  # an earlier error must not fail this check
        pass
    current = gl.GLint()
    gl.glGetQueryiv(gl.GL_TIME_ELAPSED, gl.GL_CURRENT_QUERY, ctypes.byref(current))
    if current.value:  # another timer runs (a probe): the query exists, as `glGetQueryiv` did not fail
        return gl.glGetError() == gl.GL_NO_ERROR
    ident = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(ident))
    if not ident.value:
        return False
    gl.glBeginQuery(gl.GL_TIME_ELAPSED, ident.value)
    gl.glEndQuery(gl.GL_TIME_ELAPSED)
    gl.glDeleteQueries(1, ctypes.byref(ident))
    return gl.glGetError() == gl.GL_NO_ERROR


#: The checks, by feature (a test replaces one with a stub to force its failure, AD-039 §2.2).
CHECKS = {"depth_texture": _depth_texture, "sampler_objects": _sampler_objects, "cube_rgba16f": _cube_rgba16f,
          "texture_units": _texture_units, "timer_query": _timer_query}


def probe() -> FeatureReport:
    """Every P3 check in the current GL context. A check that raises counts as missing."""
    results = {}
    for name, check in CHECKS.items():
        try:
            results[name] = bool(check())
        except Exception:  # a driver that refuses the call: the feature is missing, the room keeps running
            results[name] = False
    return FeatureReport(**results)
