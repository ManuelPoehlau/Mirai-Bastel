"""GL sink of the influence face shading (2026-10-22, `PROVISIONAL`; display idea adapted from the
Mehlsack Lab's `GLInfluencePreviewOverlay`, nothing imported from `experiments/`).

An extra overlay (`Viewport.add_overlay`, H1 contract: `sync(mesh, selection)`, `dirty`,
`draw(camera_uniforms)`) built on `GLTriangleOverlay` with a program that adds a per-vertex colour.
It declares `DRAW_UNDER_HIGHLIGHTS`: the Viewport draws it right after the mesh, before the wire and
the selection / hover fills and edge highlights, so those stay on top of the translucent shading.

`Application` pushes the weights with `set_weights()`; `sync()` only turns them into triangles at the
mesh's current positions - it never computes influence. The touched-triangle list (a scan over all
faces) is kept until the weights change or a `MeshWatch` reports a face change, so hover and selection
syncs and drags cost one position lookup per shaded corner.
"""

from __future__ import annotations

from typing import Mapping

from core import Mesh, VertexId
from viewport.gl_triangle_overlay import GLTriangleOverlay

from .shading import shaded_triangles, triangle_colors, triangle_positions

SHADING_LAYER = "soft_shading"

_VERTEX_SRC = """
#version 330 core
in vec3 position;
in vec4 colors;

uniform mat4 u_view;
uniform mat4 u_proj;

out vec4 v_color;

void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    v_color = colors;
}
"""

_FRAGMENT_SRC = """
#version 330 core
in vec4 v_color;
out vec4 out_color;

void main() {
    out_color = v_color;
}
"""


class GLSoftShadingOverlay(GLTriangleOverlay):
    """Per-corner coloured influence triangles (see module docstring)."""

    LAYERS = (SHADING_LAYER,)
    # The colour comes per vertex; the style only marks the layer as blended.
    LAYER_STYLES = {SHADING_LAYER: ((1.0, 1.0, 1.0, 0.5), 1.0)}
    #: Viewport hook: drawn before the wire and the selection / hover highlights.
    DRAW_UNDER_HIGHLIGHTS = True

    _program = None  # own program, not the flat-colour one of the parent

    def __init__(self) -> None:
        super().__init__()
        self._shown: Mapping[VertexId, float] = {}
        self.look = "color"
        self._colors: list[float] = []
        self._triangles: list | None = None  # touched triangles (vertex ids); None = rebuild
        self._corner_colors: list = []
        self._synced_mesh = None
        self._watch = None
        #: True until the next `sync()`: the weights changed (or none were synced yet).
        self.dirty = False
        #: Number of `set_weights` calls so far (diagnostics/tests).
        self.pushes = 0
        #: Number of full face scans so far (diagnostics/tests).
        self.scans = 0

    @classmethod
    def program(cls):
        if cls._program is None:
            from pyglet.graphics.shader import Shader, ShaderProgram

            cls._program = ShaderProgram(Shader(_VERTEX_SRC, "vertex"), Shader(_FRAGMENT_SRC, "fragment"))
        return cls._program

    # -- data (no GL) --------------------------------------------------------------------

    @property
    def weights(self) -> Mapping[VertexId, float]:
        return self._shown

    def set_weights(self, weights: Mapping[VertexId, float]) -> None:
        self._shown = weights
        self._triangles = None
        self.dirty = True
        self.pushes += 1

    def set_look(self, look: str) -> None:
        """Colours of the shading (`settings.LOOKS`); recomputed at the next sync."""
        self.look = look
        self._triangles = None
        self.dirty = True

    def colors(self) -> list[float]:
        return list(self._colors)

    def triangles(self) -> list[float]:
        """The flat world positions currently held (diagnostics/tests)."""
        return list(self._flat[SHADING_LAYER])

    def sync(self, mesh: Mesh, selection) -> None:
        """Viewport contract. Positions at the mesh's current vertex positions."""
        self.dirty = False
        self._follow_topology(mesh)
        if not self._shown:
            self._set_shading([], [])
            return
        if self._triangles is None:
            self._triangles = shaded_triangles(mesh, self._shown)
            self._corner_colors = triangle_colors(self._shown, self._triangles, self.look)
            self.scans += 1
        self._set_shading(triangle_positions(mesh, self._triangles), self._corner_colors)

    def _follow_topology(self, mesh: Mesh) -> None:
        """Drop the cached triangles when the mesh was swapped or a face changed since the last sync."""
        if mesh is not self._synced_mesh:
            if self._watch is not None:
                self._watch.close()
            self._synced_mesh = mesh
            self._watch = mesh.watch()
            self._triangles = None
        elif self._watch.take().faces:
            self._triangles = None

    def _set_shading(self, triangles, corner_colors) -> None:
        flat = [c for tri in triangles for p in tri for c in p]
        flat_colors = [c for corners in corner_colors for rgba in corners for c in rgba]
        if flat == self._flat[SHADING_LAYER] and flat_colors == self._colors:
            return
        self._flat[SHADING_LAYER] = flat
        self._colors = flat_colors
        self._stale.add(SHADING_LAYER)

    # -- GL --------------------------------------------------------------------------------

    def _upload(self, layer: str) -> None:
        flat = self._flat[layer]
        n_verts = len(flat) // 3
        vlist = self._vertex_lists.pop(layer, None)
        if vlist is not None:
            vlist.delete()
        if n_verts:
            self._vertex_lists[layer] = self.program().vertex_list(
                n_verts, self._primitive(), position=("f", flat), colors=("f", self._colors)
            )
        self.uploads += 1

    def draw(self, camera_uniforms, layers=None) -> None:
        from pyglet import gl

        if len(camera_uniforms) != 32:
            return
        if SHADING_LAYER in self._stale:
            self._upload(SHADING_LAYER)
            self._stale.discard(SHADING_LAYER)
        vlist = self._vertex_lists.get(SHADING_LAYER)
        if vlist is None:
            return
        program = self.program()
        program.use()
        program["u_view"] = tuple(camera_uniforms[0:16])
        program["u_proj"] = tuple(camera_uniforms[16:32])
        blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # Translucent: no depth writes, so overlapping shaded faces never hide each other.
        gl.glDepthMask(gl.GL_FALSE)
        vlist.draw(self._primitive())
        gl.glDepthMask(gl.GL_TRUE)
        if not blend_was_enabled:
            gl.glDisable(gl.GL_BLEND)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
