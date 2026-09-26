"""`ShadingLabStore` — `GLRenderStore` subclass with the Key+Fill fragment shader.

Handoff WP-SHADE-LAB-01 Slice 1, E2/E4. Precedent for subclassing a
production store: `PlaygroundPygletStore(PygletStore)` (AD-010 Addendum).

What is inherited unchanged: the whole `ResourceStore` contract, VertexList
assembly (`_rebuild_vertex_list`) and in-place attribute patching — i.e. every
buffer path. `vertex_list_indexed()` is called on `self.program()`, which here
resolves to the lab program; the vertex shader is the production one
(`VERTEX_SRC`, imported), so the attribute layout is identical.

What is lab-owned: the fragment shader and `draw()`, which differs from the
parent only in the light uniforms (rig instead of `LIGHT_DIR`). Camera
uniforms, base color, highlight mix, depth test and back-face culling are the
parent's.

Pitfall (E2): `GLRenderStore._program` is a class-level lazy cache read via
`cls._program`. Without the own `_program = None` below, the subclass would
find the parent's attribute and — if production compiled first — silently
draw with the production shader (`tests/test_lab_store_gl.py::test_program_isolation`).

The rig is not a resource (E3): `set_rig_uniforms()` stores a plain dict that
`draw()` pushes as uniforms. Nothing about the rig ever reaches `allocate()`/
`update()`, so no rig change can count as an upload.
"""

from __future__ import annotations

from viewport.gl_render_store import VERTEX_SRC, GLRenderStore

from .lab_rig import PRESET_HEUTE, PRESETS, resolve

#: E4 — keep in sync with `lab_rig.shade()`.
FRAGMENT_SRC = """
#version 330 core
in vec3 v_normal;
in float v_highlight;

uniform vec3 u_base_color;
uniform vec3 u_key_dir;
uniform vec3 u_key_color;
uniform float u_key_wrap;
uniform vec3 u_fill_dir;
uniform vec3 u_fill_color;
uniform float u_fill_wrap;
uniform float u_ambient;

out vec4 out_color;

float wrap(float ndl, float w) { return max((ndl + w) / (1.0 + w), 0.0); }

void main() {
    vec3 n = normalize(v_normal);
    vec3 light = vec3(u_ambient)
               + u_key_color  * wrap(dot(n, u_key_dir),  u_key_wrap)
               + u_fill_color * wrap(dot(n, u_fill_dir), u_fill_wrap);
    vec3 shaded = u_base_color * light;
    vec3 highlighted = mix(shaded, vec3(1.0, 0.82, 0.15), clamp(v_highlight, 0.0, 1.0));
    out_color = vec4(highlighted, 1.0);
}
"""

RIG_UNIFORM_NAMES = (
    "u_key_dir", "u_key_color", "u_key_wrap",
    "u_fill_dir", "u_fill_color", "u_fill_wrap",
    "u_ambient",
)


def _build_lab_program():
    """Compiles the lab `ShaderProgram`. Requires an active GL context."""
    from pyglet.graphics.shader import Shader, ShaderProgram

    return ShaderProgram(Shader(VERTEX_SRC, "vertex"), Shader(FRAGMENT_SRC, "fragment"))


class ShadingLabStore(GLRenderStore):
    """Production draw path with the lab's Key+Fill fragment shader."""

    # Own class-level cache — must shadow the parent's (E2 pitfall, see module docstring).
    _program = None

    def __init__(self, stats) -> None:
        super().__init__(stats)
        # "Heute" until the window sets something else; world space needs no camera.
        self._rig_uniforms: dict = resolve(PRESETS[PRESET_HEUTE])

    @classmethod
    def program(cls):
        if cls._program is None:
            cls._program = _build_lab_program()
        return cls._program

    def set_rig_uniforms(self, uniforms: dict) -> None:
        """Stores the resolved rig (`lab_rig.resolve()`) for the next `draw()`.
        Pure CPU state — no resource, no upload."""
        missing = [name for name in RIG_UNIFORM_NAMES if name not in uniforms]
        if missing:
            raise KeyError(f"missing rig uniforms: {missing}")
        self._rig_uniforms = dict(uniforms)

    def rig_uniforms(self) -> dict:
        return dict(self._rig_uniforms)

    def draw(self, group: str = "mesh") -> None:
        """Parent `draw()` with the rig uniforms in place of `u_light_dir`."""
        from pyglet import gl

        vlist = self.vertex_list(group)
        if vlist is None:
            return

        program = self.program()
        program.use()
        self._apply_camera_uniforms(program)
        for name in RIG_UNIFORM_NAMES:
            program[name] = self._rig_uniforms[name]
        program["u_base_color"] = self._base_color()

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        vlist.draw(gl.GL_TRIANGLES)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
