"""GLPointOverlay — round vertex points drawn on top of the mesh (WP-06 B2b).

`VIEWPORT_V02_ARCHITECTURE.md` §4.7 Option A (separate small overlay
geometry, drawn in its own pass after the base mesh), recorded in the
AD-018 §7 addendum (2026-09-26). Lives deliberately outside
`GLRenderStore`, which keeps its one-declared-group scope boundary.

What it draws: one `GL_POINTS` vertex list per layer
(`overlay.POINT_LAYERS`: `hover`, then `selected`), each rebuilt only when
that layer's positions actually changed (`set_points()`). The positions
themselves are computed headless by `SelectionOverlay.point_layers()` and
pushed in by `Viewport.sync()`; this class holds no selection logic.

Look (Artist A10/A11, 2026-09-26; sizes/hover color = Playground values,
technical reference only: `playground/window.py` `_HOVER_COLOR`, selected
8 px, hover 10 px):

- selected: production yellow `(1.0, 0.82, 0.15)`, opaque, 8 px
- hover:    pale yellow `(0.95, 0.90, 0.35)`, alpha 0.55, 10 px — PROVISIONAL

Points are round (fragment discards outside the unit circle of
`gl_PointCoord`, 1-px smoothstep edge, blending on) and ignore depth, so
they stay visible through the mesh (Playground behaviour).

Like `GLRenderStore`, the program is compiled lazily on first draw
(class-level, shared - one GL context) and vertex lists are only created
inside `draw()`, so constructing an instance and calling `set_points()` needs
no GL context.
"""

from __future__ import annotations

from .overlay import HOVER_LAYER, POINT_LAYERS, SELECTED_LAYER

SELECTED_COLOR = (1.0, 0.82, 0.15, 1.0)
SELECTED_POINT_SIZE = 8.0
HOVER_COLOR = (0.95, 0.90, 0.35, 0.55)
HOVER_POINT_SIZE = 10.0

LAYER_STYLES: dict[str, tuple[tuple[float, float, float, float], float]] = {
    HOVER_LAYER: (HOVER_COLOR, HOVER_POINT_SIZE),
    SELECTED_LAYER: (SELECTED_COLOR, SELECTED_POINT_SIZE),
}

POINT_VERTEX_SRC = """
#version 330 core
in vec3 position;

uniform mat4 u_view;
uniform mat4 u_proj;
uniform float u_point_size;

void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    gl_PointSize = u_point_size;
}
"""

POINT_FRAGMENT_SRC = """
#version 330 core
uniform vec4 u_color;
uniform float u_point_size;

out vec4 out_color;

void main() {
    // gl_PointCoord spans the point square as [0,1]^2; r == 1.0 is the circle edge.
    float r = length(gl_PointCoord * 2.0 - 1.0);
    if (r > 1.0) {
        discard;
    }
    float edge = 2.0 / u_point_size;  // one pixel, in units of r
    float alpha = 1.0 - smoothstep(1.0 - edge, 1.0, r);
    out_color = vec4(u_color.rgb, u_color.a * alpha);
}
"""


def _build_program():
    """Compiles the shared point `ShaderProgram`. Requires an active GL context."""
    from pyglet.graphics.shader import Shader, ShaderProgram

    vertex_shader = Shader(POINT_VERTEX_SRC, "vertex")
    fragment_shader = Shader(POINT_FRAGMENT_SRC, "fragment")
    return ShaderProgram(vertex_shader, fragment_shader)


class GLPointOverlay:
    """Flat-color round point layers, drawn after the mesh (see module docstring)."""

    _program = None  # lazily compiled, shared across instances (one GL context)

    def __init__(self) -> None:
        self._positions: dict[str, list[tuple[float, float, float]]] = {
            layer: [] for layer in POINT_LAYERS
        }
        self._vertex_lists: dict[str, object] = {}
        self._stale: set[str] = set()
        #: Number of vertex-list rebuilds so far (diagnostics/tests).
        self.rebuilds = 0

    @classmethod
    def program(cls):
        if cls._program is None:
            cls._program = _build_program()
        return cls._program

    # -- data (no GL) -----------------------------------------------------------

    def set_points(self, layer: str, positions) -> None:
        """Replaces `layer`'s world positions. Marks the layer for a rebuild
        only if the positions actually differ from the current ones."""
        if layer not in LAYER_STYLES:
            raise KeyError(f"unknown point layer: {layer!r}")
        new = [tuple(p) for p in positions]
        if new == self._positions[layer]:
            return
        self._positions[layer] = new
        self._stale.add(layer)

    def points(self, layer: str) -> list[tuple[float, float, float]]:
        return list(self._positions[layer])

    # -- GL -----------------------------------------------------------------------

    def vertex_list(self, layer: str):
        """The layer's current VertexList, or None (empty layer / not yet drawn)."""
        return self._vertex_lists.get(layer)

    def _rebuild(self, layer: str) -> None:
        from pyglet import gl

        old = self._vertex_lists.pop(layer, None)
        if old is not None:
            old.delete()
        positions = self._positions[layer]
        if positions:
            flat = [c for p in positions for c in p]
            self._vertex_lists[layer] = self.program().vertex_list(
                len(positions), gl.GL_POINTS, position=("f", flat)
            )
        self.rebuilds += 1

    def draw(self, camera_uniforms) -> None:
        """Draws all non-empty layers (hover, then selected) with the given
        camera packet: 32 floats, view matrix then projection matrix - the
        same layout `RenderMesh` uploads as `camera_uniforms`."""
        from pyglet import gl

        if len(camera_uniforms) != 32:
            return
        for layer in POINT_LAYERS:
            if layer in self._stale:
                self._rebuild(layer)
        self._stale.clear()
        if not self._vertex_lists:
            return

        program = self.program()
        program.use()
        program["u_view"] = tuple(camera_uniforms[0:16])
        program["u_proj"] = tuple(camera_uniforms[16:32])

        blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
        gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        for layer in POINT_LAYERS:
            vlist = self._vertex_lists.get(layer)
            if vlist is None:
                continue
            color, size = LAYER_STYLES[layer]
            program["u_color"] = color
            program["u_point_size"] = size
            vlist.draw(gl.GL_POINTS)
        if not blend_was_enabled:
            gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_PROGRAM_POINT_SIZE)
