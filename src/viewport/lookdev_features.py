"""LookDev P3 feature checks (AD-039 §2.2): what this GL context can do for each effect, checked by function, never by
GPU name (`GL_RENDERER`).

`probe()` runs once per GL context, the first time an effect needs it (never with `shading == "worklight"`): the
`LookdevPass` holds the report. A failed check turns its effect off (`lookdev_optics.effective`) and the viewport shows
one status line; the check does not retry in the session. The report is a plain value, so LD-3 can read it later.

S1 adds `depth_texture`: a DEPTH_COMPONENT24 texture with `GL_COMPARE_REF_TO_TEXTURE` attached to an FBO -
`glCheckFramebufferStatus == COMPLETE` and `glGetError` 0. The later slices add theirs here (`sampler_objects`,
`cube_rgba16f`, `texture_units`).
"""

from __future__ import annotations

from dataclasses import dataclass, fields

#: The status line of a feature that is missing (German, the app's status language).
FEATURE_STATUS = {"depth_texture": "LookDev: Schatten aus – Tiefentextur nicht verfügbar"}


@dataclass(frozen=True)
class FeatureReport:
    """One GL context's P3 features (True = present)."""

    depth_texture: bool = True

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


#: The checks, by feature (a test replaces one with a stub to force its failure, AD-039 §2.2).
CHECKS = {"depth_texture": _depth_texture}


def probe() -> FeatureReport:
    """Every P3 check in the current GL context. A check that raises counts as missing."""
    results = {}
    for name, check in CHECKS.items():
        try:
            results[name] = bool(check())
        except Exception:  # a driver that refuses the call: the feature is missing, the room keeps running
            results[name] = False
    return FeatureReport(**results)
