"""GL sink of the SubD line presentation: cage and isolines (pyglet only inside `draw`).

Composes `viewport.gl_line_overlay.FlatColorLayers` (same program, vertex lists created on the
first draw, data needs no GL), like `viewport.gl_symmetry_overlay`. It knows layers, look and the
per-layer depth test; what is shown decides `preview.SubdLinePresentation`.

Look (`PROVISIONAL`, the SubD Lab's values): cage = the app's wire grey; isolines = a cooler slate,
so the two stay distinguishable.
"""

from __future__ import annotations

from viewport.gl_line_overlay import EDGE_COLOR, EDGE_LINE_WIDTH, FlatColorLayers

from .preview import CAGE_LAYER, ISO_LAYER

CAGE_COLOR = EDGE_COLOR
ISO_COLOR = (0.22, 0.34, 0.52, 1.0)


class GLSubdLineOverlay(FlatColorLayers):
    LAYERS = (CAGE_LAYER, ISO_LAYER)
    LAYER_STYLES = {
        CAGE_LAYER: (CAGE_COLOR, EDGE_LINE_WIDTH),
        ISO_LAYER: (ISO_COLOR, EDGE_LINE_WIDTH),
    }
    VERTS_PER_ITEM = 2

    def __init__(self) -> None:
        super().__init__()
        self._no_depth: set[str] = set()

    @property
    def NO_DEPTH_LAYERS(self) -> frozenset:  # noqa: N802 - read through `self` by FlatColorLayers.draw
        return frozenset(self._no_depth)

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES

    def set_segments(self, layer: str, segments) -> None:
        self._set(layer, segments)

    def set_depth_test(self, layer: str, enabled: bool) -> None:
        if enabled:
            self._no_depth.discard(layer)
        else:
            self._no_depth.add(layer)

    def segment_count(self, layer: str) -> int:
        return self._count(layer)
