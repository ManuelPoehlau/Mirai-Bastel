"""GLLineOverlay — mesh edges as lines on or instead of the faces (WP-06 B5a).

Same precedent as `GLPointOverlay` (`VIEWPORT_V02_ARCHITECTURE.md` §4.7
Option A, AD-018 §7 addendum): a separate small overlay geometry drawn in
its own pass after the base mesh, deliberately outside `GLRenderStore`,
which keeps its one-declared-group scope boundary.

What it draws: one `GL_LINES` vertex list, two vertices per edge. The
segment positions are computed headless by `wireframe.edge_segments()` and
pushed in by `Viewport.sync()` (only while edges are shown); this class
holds no mesh logic.

Look (E41, `PROVISIONAL`, Playground values as the starting point —
technical reference only: `playground/window.py` `_EDGE_COLOR`): dark grey
`(0.15, 0.15, 0.15)`, 1 px. Depth test on with `GL_LEQUAL` (E40), so edges
on the visible surface show and edges behind it are hidden; the faces are
pushed back by `GLRenderStore`'s polygon offset while edges are drawn. In
pure Wireframe there are no faces, so every edge is visible.

Like `GLPointOverlay`, the program is compiled lazily on first draw
(class-level, shared - one GL context) and the vertex list is only created
inside `draw()`, so constructing an instance and calling `set_segments()`
needs no GL context.
"""

from __future__ import annotations

EDGE_COLOR = (0.15, 0.15, 0.15, 1.0)
EDGE_LINE_WIDTH = 1.0

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
    """Compiles the shared line `ShaderProgram`. Requires an active GL context."""
    from pyglet.graphics.shader import Shader, ShaderProgram

    vertex_shader = Shader(LINE_VERTEX_SRC, "vertex")
    fragment_shader = Shader(LINE_FRAGMENT_SRC, "fragment")
    return ShaderProgram(vertex_shader, fragment_shader)


class GLLineOverlay:
    """Flat-color edge lines, drawn after the mesh (see module docstring)."""

    _program = None  # lazily compiled, shared across instances (one GL context)

    def __init__(self) -> None:
        self._flat: list[float] = []
        self._vertex_list = None
        self._stale = False
        #: Number of GPU vertex-list uploads so far (diagnostics/tests).
        self.uploads = 0

    @classmethod
    def program(cls):
        if cls._program is None:
            cls._program = _build_program()
        return cls._program

    # -- data (no GL) -----------------------------------------------------------

    def set_segments(self, segments) -> None:
        """Replaces all segments (`(a, b)` world-position pairs). Marks the
        overlay for an upload only if the positions actually differ."""
        flat = [c for a, b in segments for c in (*a, *b)]
        if flat == self._flat:
            return
        self._flat = flat
        self._stale = True

    def segment_count(self) -> int:
        return len(self._flat) // 6

    # -- GL -----------------------------------------------------------------------

    def vertex_list(self):
        """The current VertexList, or None (no segments / not yet drawn)."""
        return self._vertex_list

    def _upload(self) -> None:
        from pyglet import gl

        n_verts = len(self._flat) // 3
        vlist = self._vertex_list
        if vlist is not None and vlist.count == n_verts:
            # Same edge count (a move, undo/redo of a move): overwrite the
            # positions in place instead of reallocating every dirty frame.
            vlist.position[:] = self._flat
        else:
            if vlist is not None:
                vlist.delete()
            self._vertex_list = None
            if n_verts:
                self._vertex_list = self.program().vertex_list(
                    n_verts, gl.GL_LINES, position=("f", self._flat)
                )
        self.uploads += 1

    def draw(self, camera_uniforms) -> None:
        """Draws the lines with the given camera packet: 32 floats, view matrix
        then projection matrix - the same layout `RenderMesh` uploads as
        `camera_uniforms`."""
        from pyglet import gl

        if len(camera_uniforms) != 32:
            return
        if self._stale:
            self._upload()
            self._stale = False
        if self._vertex_list is None:
            return

        program = self.program()
        program.use()
        program["u_view"] = tuple(camera_uniforms[0:16])
        program["u_proj"] = tuple(camera_uniforms[16:32])
        program["u_color"] = EDGE_COLOR

        gl.glLineWidth(EDGE_LINE_WIDTH)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        self._vertex_list.draw(gl.GL_LINES)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
