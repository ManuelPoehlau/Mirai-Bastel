"""GLLineOverlay — mesh edges as lines on or instead of the faces (WP-06 B5a),
plus the hovered / selected edge highlight (WP-06 B5b).

Same precedent as `GLPointOverlay` (`VIEWPORT_V02_ARCHITECTURE.md` §4.7
Option A, AD-018 §7 addendum): a separate small overlay geometry drawn in
its own pass after the base mesh, deliberately outside `GLRenderStore`,
which keeps its one-declared-group scope boundary.

What it draws: one `GL_LINES` vertex list per layer, two vertices per edge.
Layers (`LINE_LAYERS`):

- `wire` (B5a): every mesh edge, from `wireframe.edge_segments()`, pushed in
  by `Viewport.sync()` only while edges are shown.
- `hover`, `selected` (B5b): the hovered edge and the selected edges, from
  `SelectionOverlay.line_layers()`.
- `tool_preview`, `tool_active` (B7, Knife session, `overlay.TOOL_LAYERS`):
  the hovered/locked edge plus the start → prospective-point line preview
  (hover style), and the session's path edges so far (selected style).

The viewport draws `wire` right after the mesh and `hover`/`selected` after
the face highlight (`draw(..., layers=...)`); this class holds no mesh or
selection logic.

Look (`PROVISIONAL`, Playground values as the starting point — technical
reference only: `playground/window.py` `_EDGE_COLOR`, `_HOVER_COLOR`):

- wire: dark grey `(0.15, 0.15, 0.15)`, 1 px (E41)
- hover: pale yellow `(0.95, 0.90, 0.35)`, alpha 0.55, blended, 1 px (E46)
- selected: production yellow `(1.0, 0.82, 0.15)`, 1 px (E46 — one selection
  colour for all modes instead of the Playground orange)

Depth test on with `GL_LEQUAL` (E40/E45), so edges on the visible surface
show and edges behind it are hidden — except `NO_DEPTH_LAYERS`
(`tool_preview`, B7 `PROVISIONAL`): the line preview runs straight across a
face whose triangulated surface (non-planar quads on the head mesh) can lie
in front of it, so it is drawn on top like the points; the faces are pushed back by
`GLRenderStore`'s polygon offset while the wire is drawn. In pure Wireframe
there are no faces, so every edge is visible.

`FlatColorLayers` is the shared layer/upload/draw mechanics, also used by
`gl_triangle_overlay.GLTriangleOverlay`. Like `GLPointOverlay`, the program
is compiled lazily on first draw (class-level, shared - one GL context) and
vertex lists are only created inside `draw()`, so constructing an instance
and setting data needs no GL context.
"""

from __future__ import annotations

from .gl_point_overlay import HOVER_COLOR, SELECTED_COLOR
from .overlay import (
    HOVER_LAYER,
    SELECTED_LAYER,
    TOOL_ACTIVE_LAYER,
    TOOL_LAYERS,
    TOOL_PREVIEW_LAYER,
)

WIRE_LAYER = "wire"
#: Draw order when several layers are drawn in one call (hover under selected,
#: like the points; tool layers last).
LINE_LAYERS = (WIRE_LAYER, HOVER_LAYER, SELECTED_LAYER) + TOOL_LAYERS

EDGE_COLOR = (0.15, 0.15, 0.15, 1.0)
EDGE_LINE_WIDTH = 1.0
HOVER_EDGE_LINE_WIDTH = 1.0
SELECTED_EDGE_LINE_WIDTH = 1.0

LINE_VERTEX_SRC = """
#version 330 core
in vec3 position;

uniform mat4 u_view;
uniform mat4 u_proj;

void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
}
"""

LINE_FRAGMENT_SRC = """
#version 330 core
uniform vec4 u_color;

out vec4 out_color;

void main() {
    out_color = u_color;
}
"""


def _build_program():
    """Compiles the shared flat-colour `ShaderProgram`. Requires an active GL
    context."""
    from pyglet.graphics.shader import Shader, ShaderProgram

    vertex_shader = Shader(LINE_VERTEX_SRC, "vertex")
    fragment_shader = Shader(LINE_FRAGMENT_SRC, "fragment")
    return ShaderProgram(vertex_shader, fragment_shader)


class FlatColorLayers:
    """Named layers of flat-colour primitives, one vertex list each.

    Subclasses set `LAYERS` (draw order), `LAYER_STYLES` (layer → (rgba,
    line width)), `VERTS_PER_ITEM` and `_primitive()`. A layer whose colour
    has alpha < 1 is drawn blended."""

    LAYERS: tuple[str, ...] = ()
    LAYER_STYLES: dict[str, tuple[tuple[float, float, float, float], float]] = {}
    #: Layers drawn without the depth test (on top of the mesh).
    NO_DEPTH_LAYERS: frozenset[str] = frozenset()
    VERTS_PER_ITEM = 1

    _program = None  # lazily compiled, shared across instances (one GL context)

    def __init__(self) -> None:
        self._flat: dict[str, list[float]] = {layer: [] for layer in self.LAYERS}
        self._vertex_lists: dict[str, object] = {}
        self._stale: set[str] = set()
        #: Number of GPU vertex-list uploads so far, all layers (diagnostics/tests).
        self.uploads = 0

    @classmethod
    def program(cls):
        if cls._program is None:
            cls._program = _build_program()
        return cls._program

    @staticmethod
    def _primitive():
        raise NotImplementedError

    # -- data (no GL) -----------------------------------------------------------

    def _set(self, layer: str, items) -> None:
        """Replaces `layer`'s items (each a tuple of `VERTS_PER_ITEM` world
        positions). Marks the layer for an upload only if it actually differs."""
        if layer not in self.LAYER_STYLES:
            raise KeyError(f"unknown layer: {layer!r}")
        flat = [c for item in items for p in item for c in p]
        if flat == self._flat[layer]:
            return
        self._flat[layer] = flat
        self._stale.add(layer)

    def _count(self, layer: str) -> int:
        return len(self._flat[layer]) // (3 * self.VERTS_PER_ITEM)

    # -- GL -----------------------------------------------------------------------

    def vertex_list(self, layer: str):
        """The layer's current VertexList, or None (empty / not yet drawn)."""
        return self._vertex_lists.get(layer)

    def _upload(self, layer: str) -> None:
        flat = self._flat[layer]
        n_verts = len(flat) // 3
        vlist = self._vertex_lists.get(layer)
        if vlist is not None and vlist.count == n_verts:
            # Same element count (a move, undo/redo of a move): overwrite the
            # positions in place instead of reallocating every dirty frame.
            vlist.position[:] = flat
        else:
            if vlist is not None:
                vlist.delete()
            self._vertex_lists.pop(layer, None)
            if n_verts:
                self._vertex_lists[layer] = self.program().vertex_list(
                    n_verts, self._primitive(), position=("f", flat)
                )
        self.uploads += 1

    def draw(self, camera_uniforms, layers=None) -> None:
        """Draws `layers` (default: all, in `LAYERS` order) with the given
        camera packet: 32 floats, view matrix then projection matrix - the
        same layout `RenderMesh` uploads as `camera_uniforms`."""
        from pyglet import gl

        if len(camera_uniforms) != 32:
            return
        layers = self.LAYERS if layers is None else layers
        for layer in layers:
            if layer in self._stale:
                self._upload(layer)
                self._stale.discard(layer)
        drawn = [
            (layer, self._vertex_lists[layer])
            for layer in layers
            if layer in self._vertex_lists
        ]
        if not drawn:
            return

        program = self.program()
        program.use()
        program["u_view"] = tuple(camera_uniforms[0:16])
        program["u_proj"] = tuple(camera_uniforms[16:32])

        primitive = self._primitive()
        blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        for layer, vlist in drawn:
            if layer in self.NO_DEPTH_LAYERS:
                gl.glDisable(gl.GL_DEPTH_TEST)
            else:
                gl.glEnable(gl.GL_DEPTH_TEST)
            color, line_width = self.LAYER_STYLES[layer]
            if color[3] < 1.0:
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            elif not blend_was_enabled:
                gl.glDisable(gl.GL_BLEND)
            program["u_color"] = color
            gl.glLineWidth(line_width)
            vlist.draw(primitive)
        if not blend_was_enabled:
            gl.glDisable(gl.GL_BLEND)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)


class GLLineOverlay(FlatColorLayers):
    """Flat-colour edge lines, drawn after the mesh (see module docstring)."""

    LAYERS = LINE_LAYERS
    LAYER_STYLES = {
        WIRE_LAYER: (EDGE_COLOR, EDGE_LINE_WIDTH),
        HOVER_LAYER: (HOVER_COLOR, HOVER_EDGE_LINE_WIDTH),
        SELECTED_LAYER: (SELECTED_COLOR, SELECTED_EDGE_LINE_WIDTH),
        TOOL_PREVIEW_LAYER: (HOVER_COLOR, HOVER_EDGE_LINE_WIDTH),
        TOOL_ACTIVE_LAYER: (SELECTED_COLOR, SELECTED_EDGE_LINE_WIDTH),
    }
    NO_DEPTH_LAYERS = frozenset({TOOL_PREVIEW_LAYER})
    VERTS_PER_ITEM = 2

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES

    def set_segments(self, segments, layer: str = WIRE_LAYER) -> None:
        """Replaces `layer`'s segments (`(a, b)` world-position pairs)."""
        self._set(layer, segments)

    def segment_count(self, layer: str = WIRE_LAYER) -> int:
        return self._count(layer)

    def vertex_list(self, layer: str = WIRE_LAYER):
        return super().vertex_list(layer)

    def draw(self, camera_uniforms, layers=(WIRE_LAYER,)) -> None:
        super().draw(camera_uniforms, layers)
