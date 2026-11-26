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

Deformed cage (GUI Phase A3, 2026-11-03, `PROVISIONAL`): with a cage source set (`set_cage_source`, the app's
`_shown_cage`: the skin stage's posed surface, else the morph mix - one mesh with the edit mesh's IDs and topology,
patched in place) the triangles are placed at the cage's positions, so the shading sits on the surface the window
shows (the wire follows it too); the topology still comes from the synced edit mesh. A watch on the cage makes a
pose or weight step re-sync the positions; with nothing shaded the cage is not watched. Picking, the selection and
the Soft bands read the viewport's cage (`Application._query_cage`: the posed surface while posed, else the morph mix;
AD-028 §7.1, 2026-11-17); the Soft field is still computed on the rest mesh.

Weight heatmap (AD-041 §5, slice 2, `PROVISIONAL`): `set_heat(heat)` hands over a `mirai.weight_heatmap.WeightHeat`
while the Weight Room is open; the overlay then draws it instead of the dict weights - every shown face, one colour
per *vertex* (no fan-split face colour), opaque, on the cage source like the face shading. It is uploaded as arrays
(one indexed draw: positions, colours, triangle rows) and only what changed is sent: the colour rows a dab wrote
(`WeightHeat.take_color_rows`, merged into ranges), the positions when the cage moved (the pose follows the paint),
everything after a topology change. Headless (`sync` without GL) the arrays are held for tests (`heat_arrays`).
"""

from __future__ import annotations

import ctypes
from typing import Callable, Mapping, Optional

import numpy as np

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
        self._dirty = False
        self._cage_source: Optional[Callable[[], Optional[Mesh]]] = None
        self._cage: Optional[Mesh] = None
        self._cage_watch = None
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
        # -- the weight heatmap (module docstring) --
        self._heat = None
        self._heat_topology = -1
        self._heat_position_revision = -1
        self._heat_positions: Optional[np.ndarray] = None
        #: what the next draw uploads: positions / indices whole, colours whole (None) or by row ranges
        self._heat_pending = {"positions": False, "indices": False, "colors": []}
        self._heat_gl = None  # (vao, position buffer, colour buffer, index buffer)
        self._heat_gl_size = (0, 0)  # (rows, indices) the buffers were allocated for
        #: diagnostics (tests): whole colour uploads, colour range uploads, position uploads
        self.heat_full_uploads = 0
        self.heat_range_uploads = 0
        self.heat_position_uploads = 0

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

    @property
    def dirty(self) -> bool:
        """Viewport contract: re-sync - the weights changed, or the shown cage was swapped or moved."""
        if self._dirty:
            return True
        if self._heat is not None and self._heat.pending():
            return True
        if not (self._shown or self._heat is not None) or self._cage_source is None:
            return False
        cage = self._cage_source()
        if cage is not self._cage:
            return True
        return cage is not None and bool(self._cage_watch.peek().vertices)

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = bool(value)

    def set_cage_source(self, source: Optional[Callable[[], Optional[Mesh]]]) -> None:
        """`source()` = the deformed cage of the synced mesh (same IDs) the window shows, None = the rest shape."""
        self._cage_source = source
        self._dirty = True

    def set_weights(self, weights: Mapping[VertexId, float]) -> None:
        self._shown = weights
        self._triangles = None
        self.dirty = True
        self.pushes += 1

    def set_heat(self, heat) -> None:
        """AD-041 §5: draw `heat` (a `WeightHeat`) instead of the dict weights; None = back to the face shading."""
        if heat is self._heat:
            return
        self._heat = heat
        self._heat_topology = -1
        self._heat_position_revision = -1
        self._heat_positions = None
        self._dirty = True

    @property
    def heat(self):
        return self._heat

    def heat_arrays(self):
        """(positions (n, 3) float32, colours (n, 4) float32, triangle rows (m, 3) uint32) of the heatmap as last synced;
        None without one (tests, diagnostics)."""
        heat = self._heat
        if heat is None or self._heat_positions is None:
            return None
        return self._heat_positions, heat.colors, heat.tris

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
        if self._heat is not None:
            self._set_shading([], [])
            self._sync_heat()
            return
        self._follow_topology(mesh)
        cage = self._follow_cage()
        if not self._shown:
            self._set_shading([], [])
            return
        if self._triangles is None:
            self._triangles = shaded_triangles(mesh, self._shown)
            self._corner_colors = triangle_colors(self._shown, self._triangles, self.look)
            self.scans += 1
        positions = None
        if cage is not None:
            try:
                positions = triangle_positions(cage, self._triangles)
            except (KeyError, ValueError):
                positions = None  # the cage is behind the mesh's topology for this frame: the rest shape
        self._set_shading(positions if positions is not None else triangle_positions(mesh, self._triangles),
                          self._corner_colors)

    def _sync_heat(self) -> None:
        """The heatmap's arrays brought up to date (module docstring): only what changed is marked for the upload."""
        heat = self._heat
        heat.refresh()
        moved = self._cage_moved()
        cage = self._follow_cage()
        pending = self._heat_pending
        if heat.topology_revision != self._heat_topology:
            self._heat_topology = heat.topology_revision
            pending["indices"] = True
            pending["colors"] = None
            moved = True
        rows = heat.take_color_rows()
        if rows is None:
            pending["colors"] = None
        elif rows and pending["colors"] is not None:
            pending["colors"].extend(rows)
        if cage is None and heat.position_revision != self._heat_position_revision:
            moved = True
        if moved or self._heat_positions is None:
            self._heat_position_revision = heat.position_revision
            self._heat_positions = np.ascontiguousarray(heat.positions(cage), dtype=np.float32)
            pending["positions"] = True

    def _cage_moved(self) -> bool:
        cage = self._cage_source() if self._cage_source is not None else None
        if cage is not self._cage:
            return True
        return cage is not None and bool(self._cage_watch.peek().vertices)

    def _follow_cage(self) -> Optional[Mesh]:
        """The cage the triangles sit on now (None = the synced mesh); watched only while something is shaded."""
        shown = self._shown or self._heat is not None
        cage = self._cage_source() if self._cage_source is not None and shown else None
        if cage is not self._cage:
            if self._cage_watch is not None:
                self._cage_watch.close()
            self._cage = cage
            self._cage_watch = cage.watch() if cage is not None else None
        elif cage is not None:
            self._cage_watch.take()
        return cage

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
        if self._heat is not None:
            self._draw_heat(camera_uniforms)
            return
        if self._heat_gl is not None:
            self._release_heat_gl()
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

    # -- the weight heatmap's GL (AD-041 §5) ----------------------------------------------------------------------

    def _upload_heat(self) -> bool:
        """Sends what `_sync_heat` marked; False = nothing to draw."""
        from pyglet import gl

        heat, positions, pending = self._heat, self._heat_positions, self._heat_pending
        if positions is None or not len(heat.tris):
            return False
        colors = np.ascontiguousarray(heat.colors, dtype=np.float32)
        indices = np.ascontiguousarray(heat.tris, dtype=np.uint32).reshape(-1)
        size = (len(positions), indices.size)
        program = self.program()
        if self._heat_gl is None:
            names = (gl.GLuint * 3)()
            gl.glGenBuffers(3, names)
            vao = gl.GLuint()
            gl.glGenVertexArrays(1, ctypes.byref(vao))
            self._heat_gl = (vao.value, names[0], names[1], names[2])
            self._heat_gl_size = (0, 0)
        vao, pos_buffer, col_buffer, idx_buffer = self._heat_gl
        was = gl.GLint()
        gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING, ctypes.byref(was))
        gl.glBindVertexArray(vao)
        if size != self._heat_gl_size:
            pending["positions"] = pending["indices"] = True
            pending["colors"] = None
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, pos_buffer)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, positions.nbytes, None, gl.GL_DYNAMIC_DRAW)
            location = gl.glGetAttribLocation(program.id, b"position")
            gl.glEnableVertexAttribArray(location)
            gl.glVertexAttribPointer(location, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, col_buffer)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, colors.nbytes, None, gl.GL_DYNAMIC_DRAW)
            location = gl.glGetAttribLocation(program.id, b"colors")
            gl.glEnableVertexAttribArray(location)
            gl.glVertexAttribPointer(location, 4, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
            self._heat_gl_size = size
        if pending["positions"]:
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, pos_buffer)
            gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, positions.nbytes, positions.ctypes.data)
            self.heat_position_uploads += 1
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, col_buffer)
        if pending["colors"] is None:
            gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, colors.nbytes, colors.ctypes.data)
            self.heat_full_uploads += 1
        elif pending["colors"]:
            from viewport.gl_edge_buffer import runs

            stride = colors.strides[0]
            for lo, hi in runs(pending["colors"], HEAT_MERGE_GAP):
                gl.glBufferSubData(gl.GL_ARRAY_BUFFER, lo * stride, (hi - lo) * stride, colors.ctypes.data + lo * stride)
            self.heat_range_uploads += 1
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        if pending["indices"]:
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, idx_buffer)  # (recorded in the VAO)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices.ctypes.data, gl.GL_DYNAMIC_DRAW)
        gl.glBindVertexArray(was.value)
        self._heat_pending = {"positions": False, "indices": False, "colors": []}
        return True

    def _draw_heat(self, camera_uniforms) -> None:
        from pyglet import gl

        if not self._upload_heat():
            return
        program = self.program()
        program.use()
        program["u_view"] = tuple(camera_uniforms[0:16])
        program["u_proj"] = tuple(camera_uniforms[16:32])
        blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
        was = gl.GLint()
        gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING, ctypes.byref(was))
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBindVertexArray(self._heat_gl[0])
        gl.glDrawElements(gl.GL_TRIANGLES, self._heat_gl_size[1], gl.GL_UNSIGNED_INT, 0)
        gl.glBindVertexArray(was.value)
        gl.glDepthMask(gl.GL_TRUE)
        if not blend_was_enabled:
            gl.glDisable(gl.GL_BLEND)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        program.stop()

    def _release_heat_gl(self) -> None:
        from pyglet import gl

        vao, *buffers = self._heat_gl
        gl.glDeleteBuffers(3, (gl.GLuint * 3)(*buffers))
        gl.glDeleteVertexArrays(1, ctypes.byref(gl.GLuint(vao)))
        self._heat_gl = None
        self._heat_gl_size = (0, 0)
        self._heat_pending = {"positions": False, "indices": False, "colors": []}


#: Heatmap colour rows closer than this are uploaded as one range.
HEAT_MERGE_GAP = 64
