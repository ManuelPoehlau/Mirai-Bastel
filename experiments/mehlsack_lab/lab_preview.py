"""Surface preview of the influence (Slice 2a E14, Manu O1: the C4D principle) — lab-local.

Headless part: `preview_color(w)` and `preview_triangles(mesh, weights)`. Every face touched
by the influence (at least one vertex with `w != 0`) is fan-triangulated like `RenderMesh`
(`viewport.derived.triangulate_mesh_face`) and each triangle corner carries the colour of
its vertex's weight:

- `w > 0` → orange, `w < 0` → blue (the lab's "blue = against" convention, A8);
- strength is the alpha, proportional to `|w|`: `alpha = |w| · PREVIEW_ALPHA_MAX`, so the
  orange/blue reads more saturated over the grey surface the stronger the weight
  (seeds, `w = 1`, at full strength);
- `w = 0` (and vertices outside the influence) → alpha 0, transparent.

GL interpolates the corner colours across the face. Where a face spans a sign change the
colours blend through (no exact zero line inside the face) — an observation for the README,
not hidden.

GL part: `GLInfluencePreviewOverlay` subclasses the production `GLTriangleOverlay` (one
layer; the subclassing precedent of `GLSignedBandOverlay` / AD-018 §7) with a lab-local
program that adds a per-vertex colour attribute. `src/viewport`, `RenderMesh` and its shader
are untouched (AD-020 §5.1 c stays rejected for the app). It draws like the B5b face
highlight: depth test `GL_LEQUAL` on the faces, which `GLRenderStore` pushes back with its
polygon offset (the scene already sets it for the wire). It only receives weights from the
lab; it computes no influence. Off by default (`P`, A9). Colours are `PROVISIONAL`.
"""

from __future__ import annotations

from typing import Mapping

from core import Mesh, VertexId
from viewport.derived import triangulate_mesh_face
from viewport.gl_triangle_overlay import GLTriangleOverlay

RGBA = tuple[float, float, float, float]

#: PROVISIONAL hues and the strongest alpha (seeds); the shaded surface stays visible below.
PREVIEW_ORANGE = (1.0, 0.50, 0.05)
PREVIEW_BLUE = (0.15, 0.45, 1.0)
PREVIEW_ALPHA_MAX = 0.85
PREVIEW_LAYER = "influence_preview"


def preview_color(weight: float) -> RGBA:
    """Colour of one weight (module docstring)."""
    if weight == 0.0:
        return (*PREVIEW_ORANGE, 0.0)
    rgb = PREVIEW_ORANGE if weight > 0.0 else PREVIEW_BLUE
    return (*rgb, min(1.0, abs(weight)) * PREVIEW_ALPHA_MAX)


def touched_faces(mesh: Mesh, weights: Mapping[VertexId, float]) -> list:
    """Faces with at least one vertex of non-zero weight, in face-id order."""
    if not weights:
        return []
    return [
        f for f in mesh.all_face_ids()
        if any(weights.get(v, 0.0) != 0.0 for v in mesh.face_vertices(f))
    ]


def preview_triangles(mesh: Mesh, weights: Mapping[VertexId, float]) -> tuple[list, list]:
    """`(triangles, colours)`: each triangle three world positions, each colour entry the
    three corner RGBA values — at the mesh's current positions."""
    triangles: list = []
    colours: list = []
    position = mesh.vertex_position
    for face in touched_faces(mesh, weights):
        for tri in triangulate_mesh_face(mesh, face):
            triangles.append(tuple(position(v) for v in tri))
            colours.append(tuple(preview_color(weights.get(v, 0.0)) for v in tri))
    return triangles, colours


PREVIEW_VERTEX_SRC = """
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

PREVIEW_FRAGMENT_SRC = """
#version 330 core
in vec4 v_color;
out vec4 out_color;

void main() {
    out_color = v_color;
}
"""


class GLInfluencePreviewOverlay(GLTriangleOverlay):
    """Per-vertex coloured influence triangles (see module docstring)."""

    LAYERS = (PREVIEW_LAYER,)
    # The colour comes per vertex; the layer style only marks the layer as blended.
    LAYER_STYLES = {PREVIEW_LAYER: ((1.0, 1.0, 1.0, 0.5), 1.0)}

    _program = None  # own program, not the parent's flat-colour one

    def __init__(self) -> None:
        super().__init__()
        self._colors: list[float] = []
        self.visible = False
        self.weights: Mapping[VertexId, float] = {}
        self._weights_revision = 0
        #: (mesh version, weights revision, visible) the layer was last built for
        self._built_for = None

    @classmethod
    def program(cls):
        if cls._program is None:
            from pyglet.graphics.shader import Shader, ShaderProgram

            cls._program = ShaderProgram(Shader(PREVIEW_VERTEX_SRC, "vertex"),
                                         Shader(PREVIEW_FRAGMENT_SRC, "fragment"))
        return cls._program

    # -- data (no GL) --------------------------------------------------------------------

    def set_weights(self, weights: Mapping[VertexId, float]) -> None:
        self.weights = weights
        self._weights_revision += 1

    def set_preview(self, triangles, colours) -> None:
        flat = [c for tri in triangles for p in tri for c in p]
        flat_colours = [c for corners in colours for rgba in corners for c in rgba]
        if flat == self._flat[PREVIEW_LAYER] and flat_colours == self._colors:
            return
        self._flat[PREVIEW_LAYER] = flat
        self._colors = flat_colours
        self._stale.add(PREVIEW_LAYER)

    def colors(self) -> list[float]:
        return list(self._colors)

    def sync(self, mesh: Mesh, version: int) -> None:
        """Rebuilds the triangles when positions, weights or visibility changed."""
        key = (version, self._weights_revision, self.visible)
        if key == self._built_for:
            return
        self._built_for = key
        if self.visible:
            self.set_preview(*preview_triangles(mesh, self.weights))
        else:
            self.set_preview([], [])

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
        if PREVIEW_LAYER in self._stale:
            self._upload(PREVIEW_LAYER)
            self._stale.discard(PREVIEW_LAYER)
        vlist = self._vertex_lists.get(PREVIEW_LAYER)
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
        # Translucent: no depth writes, so overlapping preview faces never hide each other.
        gl.glDepthMask(gl.GL_FALSE)
        vlist.draw(self._primitive())
        gl.glDepthMask(gl.GL_TRUE)
        if not blend_was_enabled:
            gl.glDisable(gl.GL_BLEND)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
