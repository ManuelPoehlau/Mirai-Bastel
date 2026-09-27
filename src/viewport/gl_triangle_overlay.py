"""GLTriangleOverlay — selected / hovered faces as a fill on the mesh (WP-06 B5b).

Same precedent as `GLPointOverlay` and `GLLineOverlay`
(`VIEWPORT_V02_ARCHITECTURE.md` §4.7 Option A, AD-018 §7 addendum): a small
separate overlay geometry drawn in its own pass after the mesh and the wire,
before the edge highlight and the points. `GLRenderStore` is not touched.

What it draws: one `GL_TRIANGLES` vertex list per layer (`selected`, then
`hover` — Playground `on_draw` order, so a hovered selected face reads
lighter). The triangles are computed headless by
`SelectionOverlay.face_layers()` with the same fan triangulation as
`RenderMesh` and pushed in by `Viewport.sync()`; this class holds no
selection logic. Layer/upload/draw mechanics are shared with
`GLLineOverlay` (`FlatColorLayers`).

Look (E46, `PROVISIONAL`):

- selected: production yellow `(1.0, 0.82, 0.15)`, opaque fill (Playground
  structure, Playground orange replaced by the one production selection
  colour)
- hover: pale yellow `(0.95, 0.90, 0.35)`, alpha 0.55, blended (Playground)

Depth test `GL_LEQUAL` (Playground): the fill passes on the mesh's own
depth and stays hidden behind nearer geometry.
"""

from __future__ import annotations

from .gl_line_overlay import FlatColorLayers
from .gl_point_overlay import HOVER_COLOR, SELECTED_COLOR
from .overlay import HOVER_LAYER, SELECTED_LAYER

TRIANGLE_LAYERS = (SELECTED_LAYER, HOVER_LAYER)

SELECTED_FACE_COLOR = SELECTED_COLOR
HOVER_FACE_COLOR = HOVER_COLOR


class GLTriangleOverlay(FlatColorLayers):
    """Flat-colour face fills, drawn after the mesh (see module docstring)."""

    LAYERS = TRIANGLE_LAYERS
    # Line width is unused for triangles.
    LAYER_STYLES = {
        SELECTED_LAYER: (SELECTED_FACE_COLOR, 1.0),
        HOVER_LAYER: (HOVER_FACE_COLOR, 1.0),
    }
    VERTS_PER_ITEM = 3

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_TRIANGLES

    def set_triangles(self, layer: str, triangles) -> None:
        """Replaces `layer`'s triangles (`(a, b, c)` world positions each)."""
        self._set(layer, triangles)

    def triangle_count(self, layer: str) -> int:
        return self._count(layer)
