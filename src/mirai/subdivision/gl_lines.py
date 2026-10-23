"""GL sink of the SubD line presentation: cage, isolines and highlighted chains (pyglet only in `draw`).

Reuses `viewport.gl_line_overlay.FlatColorLayers` (its flat-colour program, per-layer vertex lists
created on the first draw, uploads only when a layer's data differs; data needs no GL), like
`viewport.gl_symmetry_overlay`. It knows layers, look and depth behaviour; what is shown, in which
strength and with which depth mode decides `preview.SubdLinePresentation` (`set_style`, `set_depth`).

Per layer: colour + alpha (alpha < 1 = blended **without depth write**, so a faint secondary line
never punches a hole into a primary line or a highlight behind it) and one depth mode:
`lequal` (depth-tested on the polygon-offset surface), `always` (no depth test) or `greater` (only
where the surface hides it). Lines stay 1 px wide (the reference driver's core profile has no
reliable wider lines); the hierarchy is carried by opacity and colour.
"""

from __future__ import annotations

from viewport.gl_line_overlay import EDGE_LINE_WIDTH, FlatColorLayers

from .preview import (
    CAGE_RGB,
    DEPTH_ALWAYS,
    DEPTH_GREATER,
    DEPTH_LEQUAL,
    HOVER_RGBA,
    ISO_RGB,
    LINE_LAYERS,
    SELECTED_RGBA,
    CAGE_HOVER_LAYER,
    CAGE_LAYER,
    CAGE_SELECTED_LAYER,
    ISO_HOVER_LAYER,
    ISO_LAYER,
    ISO_SELECTED_LAYER,
)

_DEFAULT_STYLES = {
    CAGE_LAYER: ((*CAGE_RGB, 1.0), EDGE_LINE_WIDTH),
    ISO_LAYER: ((*ISO_RGB, 1.0), EDGE_LINE_WIDTH),
    ISO_HOVER_LAYER: (HOVER_RGBA, EDGE_LINE_WIDTH),
    ISO_SELECTED_LAYER: (SELECTED_RGBA, EDGE_LINE_WIDTH),
    CAGE_HOVER_LAYER: (HOVER_RGBA, EDGE_LINE_WIDTH),
    CAGE_SELECTED_LAYER: (SELECTED_RGBA, EDGE_LINE_WIDTH),
}


class GLSubdLineOverlay(FlatColorLayers):
    LAYERS = LINE_LAYERS
    LAYER_STYLES = _DEFAULT_STYLES
    VERTS_PER_ITEM = 2

    def __init__(self) -> None:
        super().__init__()
        # instance copies: the presentation changes alpha (secondary strength) and depth per instance
        self.LAYER_STYLES = dict(_DEFAULT_STYLES)
        self._depth: dict[str, str] = {layer: DEPTH_LEQUAL for layer in LINE_LAYERS}

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES

    # -- data (no GL) -----------------------------------------------------------------------------

    def set_segments(self, layer: str, segments) -> None:
        self._set(layer, segments)

    def set_style(self, layer: str, rgba) -> None:
        self.LAYER_STYLES[layer] = (tuple(float(c) for c in rgba), EDGE_LINE_WIDTH)

    def set_depth(self, layer: str, mode: str) -> None:
        if mode not in (DEPTH_LEQUAL, DEPTH_ALWAYS, DEPTH_GREATER):
            raise ValueError(mode)
        self._depth[layer] = mode

    def depth(self, layer: str) -> str:
        return self._depth[layer]

    def segment_count(self, layer: str) -> int:
        return self._count(layer)

    # -- GL -------------------------------------------------------------------------------------------

    def draw(self, camera_uniforms, layers=None) -> None:
        from pyglet import gl

        if len(camera_uniforms) != 32:
            return
        layers = self.LAYERS if layers is None else layers
        for layer in layers:
            if layer in self._stale:
                self._upload(layer)
                self._stale.discard(layer)
        drawn = [(layer, self._vertex_lists[layer]) for layer in layers if layer in self._vertex_lists]
        if not drawn:
            return
        program = self.program()
        program.use()
        program["u_view"] = tuple(camera_uniforms[0:16])
        program["u_proj"] = tuple(camera_uniforms[16:32])
        primitive = self._primitive()
        blend_was_enabled = gl.glIsEnabled(gl.GL_BLEND)
        for layer, vlist in drawn:
            color, line_width = self.LAYER_STYLES[layer]
            mode = self._depth[layer]
            if mode == DEPTH_ALWAYS:
                gl.glDisable(gl.GL_DEPTH_TEST)
            else:
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthFunc(gl.GL_GREATER if mode == DEPTH_GREATER else gl.GL_LEQUAL)
            blended = color[3] < 1.0
            if blended:
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            elif not blend_was_enabled:
                gl.glDisable(gl.GL_BLEND)
            # Neither a blended line nor the hidden part of a highlight may occlude anything.
            gl.glDepthMask(gl.GL_FALSE if blended or mode == DEPTH_GREATER else gl.GL_TRUE)
            program["u_color"] = color
            gl.glLineWidth(line_width)
            vlist.draw(primitive)
        gl.glDepthMask(gl.GL_TRUE)
        if not blend_was_enabled:
            gl.glDisable(gl.GL_BLEND)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDisable(gl.GL_DEPTH_TEST)
