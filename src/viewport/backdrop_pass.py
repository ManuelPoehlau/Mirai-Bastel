"""GL side of the backdrop (AD-042 §7.5): the photo quad, the passepartout and the gate line.

One program, an empty VAO and `gl_VertexID` (the LookDev background's pattern): corners, gate and colours are
uniforms, there is no vertex buffer. One RGBA8 texture at a time, uploaded once per `image_serial`. Every draw saves
and restores exactly the GL state it sets (depth test / write, blend and its four factors, cull face, polygon mode,
program, VAO, active unit, the unit-0 texture and sampler, the unpack alignment on upload).
Drawn as is: not exposed, not tone-mapped, not encoded (the LookDev background's rule, AD-038 §8).
"""

from __future__ import annotations

import ctypes

import numpy as np

VERTEX_SRC = """#version 330 core
uniform int u_mode;            // 0 = image quad, 1 = passepartout (4 rectangles outside the gate), 2 = gate line loop
uniform vec2 u_corners[4];     // top-left, top-right, bottom-right, bottom-left (NDC)
uniform vec2 u_gate;           // half size of the centred gate (NDC)
out vec2 v_uv;
out vec2 v_ndc;
const int TRI[6] = int[6](0, 1, 2, 0, 2, 3);
const vec2 UV[4] = vec2[4](vec2(0.0, 1.0), vec2(1.0, 1.0), vec2(1.0, 0.0), vec2(0.0, 0.0));
const vec2 LOOP[4] = vec2[4](vec2(-1.0, 1.0), vec2(1.0, 1.0), vec2(1.0, -1.0), vec2(-1.0, -1.0));
void main() {
    vec2 p;
    if (u_mode == 0) {
        int c = TRI[gl_VertexID];
        p = u_corners[c];
        v_uv = UV[c];
    } else if (u_mode == 1) {
        // top, bottom, left, right of the gate: (x0, y0, x1, y1) each, 6 vertices per rectangle
        int r = gl_VertexID / 6;
        vec4 box = r == 0 ? vec4(-1.0, u_gate.y, 1.0, 1.0)
                 : r == 1 ? vec4(-1.0, -1.0, 1.0, -u_gate.y)
                 : r == 2 ? vec4(-1.0, -u_gate.y, -u_gate.x, u_gate.y)
                 :          vec4(u_gate.x, -u_gate.y, 1.0, u_gate.y);
        vec2 s = LOOP[TRI[gl_VertexID - 6 * r]] * 0.5 + 0.5;  // 0..1 corner of the rectangle
        p = mix(box.xy, box.zw, s);
        v_uv = s;
    } else {
        p = LOOP[gl_VertexID] * u_gate;
        v_uv = vec2(0.0);
    }
    v_ndc = p;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""

FRAGMENT_SRC = """#version 330 core
uniform int u_mode;
uniform vec2 u_gate;
uniform sampler2D u_image;
uniform float u_opacity;
uniform vec4 u_color;
in vec2 v_uv;
in vec2 v_ndc;
out vec4 out_color;
void main() {
    if (u_mode == 0) {
        vec4 t = texture(u_image, v_uv);
        out_color = vec4(t.rgb, t.a * u_opacity);
    } else {
        out_color = u_color;
    }
}
"""

GATE_LINE_COLOUR = (0.82, 0.82, 0.82, 1.0)


class BackdropPass:
    def __init__(self) -> None:
        self._program = None
        self._vao = None
        self._texture = 0
        self._serial: int | None = None
        self.uploads = 0  # how many images were uploaded (tests: the same serial never re-uploads)
        self.draws = 0

    # -- resources ----------------------------------------------------------------------------------------------

    def _ensure_program(self) -> None:
        if self._program is not None:
            return
        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        self._program = ShaderProgram(Shader(VERTEX_SRC, "vertex"), Shader(FRAGMENT_SRC, "fragment"))
        vao = gl.GLuint()
        gl.glGenVertexArrays(1, ctypes.byref(vao))
        self._vao = vao.value

    def drop_image(self) -> None:
        """Delete the photo texture (a new serial, `set_backdrop(None)`); GL context required when there is one."""
        if self._texture:
            from pyglet import gl

            tex = gl.GLuint(self._texture)
            gl.glDeleteTextures(1, ctypes.byref(tex))
        self._texture = 0
        self._serial = None

    @property
    def has_texture(self) -> bool:
        return bool(self._texture)

    def _upload(self, image, serial: int) -> None:
        from pyglet import gl

        self.drop_image()
        rgba = np.ascontiguousarray(np.asarray(image, dtype=np.uint8)[::-1])  # GL: the bottom row first
        h, w = rgba.shape[:2]
        tex = gl.GLuint()
        gl.glGenTextures(1, ctypes.byref(tex))
        align = gl.GLint()
        gl.glGetIntegerv(gl.GL_UNPACK_ALIGNMENT, ctypes.byref(align))
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex.value)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                        rgba.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte)))
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, align.value)
        # bind first, then generate (the `load_texture` rule); without mipmaps if it fails
        try:
            gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
            min_filter = gl.GL_LINEAR_MIPMAP_LINEAR
        except gl.GLException:
            min_filter = gl.GL_LINEAR
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        self._texture = tex.value
        self._serial = serial
        self.uploads += 1

    def release(self) -> None:
        self.drop_image()
        if self._program is not None:
            from pyglet import gl

            self._program.delete()
            self._program = None
            vao = gl.GLuint(self._vao)
            gl.glDeleteVertexArrays(1, ctypes.byref(vao))
            self._vao = None

    # -- draws --------------------------------------------------------------------------------------------------

    def draw_image(self, backdrop) -> bool:
        """The photo quad (behind the meshes). False = nothing to draw (no image)."""
        if backdrop.image is None:
            return False
        self._ensure_program()
        from pyglet import gl

        with _SavedState(texture=True):
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindSampler(0, 0)
            if self._serial != backdrop.image_serial or not self._texture:
                self._upload(backdrop.image, backdrop.image_serial)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture)
            self._begin()
            program = self._program
            program["u_mode"] = 0
            program["u_image"] = 0
            program["u_opacity"] = float(backdrop.opacity)
            program["u_gate"] = tuple(float(g) for g in backdrop.gate)
            program["u_corners"] = [(float(x), float(y)) for x, y in backdrop.corners]
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)
        self.draws += 1
        return True

    def draw_gate(self, backdrop) -> None:
        """The passepartout (outside the gate, black at `passepartout` alpha) and the 1 px gate line."""
        self._ensure_program()
        from pyglet import gl

        with _SavedState(texture=False):
            self._begin()
            program = self._program
            program["u_gate"] = tuple(float(g) for g in backdrop.gate)
            if backdrop.passepartout > 0.0:
                program["u_mode"] = 1
                program["u_color"] = (0.0, 0.0, 0.0, float(backdrop.passepartout))
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 24)
            program["u_mode"] = 2
            program["u_color"] = GATE_LINE_COLOUR
            gl.glDrawArrays(gl.GL_LINE_LOOP, 0, 4)
        self.draws += 1

    def _begin(self) -> None:
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)  # filled in any display mode
        gl.glEnable(gl.GL_BLEND)
        # the destination alpha stays as it is (a capture reads it)
        gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ZERO, gl.GL_ONE)
        self._program.use()
        gl.glBindVertexArray(self._vao)


class _SavedState:
    """Saves the GL state the backdrop sets and restores it on exit."""

    def __init__(self, texture: bool) -> None:
        self.texture = texture

    def __enter__(self):
        from pyglet import gl

        def geti(name, count=1):
            buf = (gl.GLint * count)()
            gl.glGetIntegerv(name, buf)
            return buf[0] if count == 1 else tuple(buf)

        self.depth_test = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
        self.blend = bool(gl.glIsEnabled(gl.GL_BLEND))
        self.cull = bool(gl.glIsEnabled(gl.GL_CULL_FACE))
        self.depth_mask = geti(gl.GL_DEPTH_WRITEMASK)
        self.blend_factors = (geti(gl.GL_BLEND_SRC_RGB), geti(gl.GL_BLEND_DST_RGB),
                              geti(gl.GL_BLEND_SRC_ALPHA), geti(gl.GL_BLEND_DST_ALPHA))
        self.polygon_mode = geti(gl.GL_POLYGON_MODE, 2)
        self.program = geti(gl.GL_CURRENT_PROGRAM)
        self.vao = geti(gl.GL_VERTEX_ARRAY_BINDING)
        if self.texture:
            self.active = geti(gl.GL_ACTIVE_TEXTURE)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            self.tex0 = geti(gl.GL_TEXTURE_BINDING_2D)
            self.sampler0 = geti(gl.GL_SAMPLER_BINDING)
            gl.glActiveTexture(self.active)
        return self

    def __exit__(self, *exc) -> None:
        from pyglet import gl

        (gl.glEnable if self.depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
        (gl.glEnable if self.blend else gl.glDisable)(gl.GL_BLEND)
        (gl.glEnable if self.cull else gl.glDisable)(gl.GL_CULL_FACE)
        gl.glDepthMask(self.depth_mask)
        gl.glBlendFuncSeparate(*self.blend_factors)
        gl.glPolygonMode(gl.GL_FRONT_AND_BACK, self.polygon_mode[0])
        gl.glUseProgram(self.program)
        gl.glBindVertexArray(self.vao)
        if self.texture:
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.tex0)
            gl.glBindSampler(0, self.sampler0)
            gl.glActiveTexture(self.active)
