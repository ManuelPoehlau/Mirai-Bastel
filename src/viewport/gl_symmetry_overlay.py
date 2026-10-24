"""GL sink of the app's symmetry display: plane outline, problem markers and the Re-Symmetrize preview.

Q-2 = S-2 (Manu, 2026-10-14): the plane outline as lines, then the problem markers as points -
seam green, without partner magenta, ambiguous white. No partner markers (they stay in the
Symmetry Lab). `Application` builds this type from `init_scene(symmetry_overlay_type=...)` and
hands it to `mirai.symmetry_display.SymmetryDisplay`, which decides what is shown and pushes it
here (`set_segments`, `set_markers`); this module knows no symmetry, only its layers and look -
like `gl_line_overlay`/`gl_point_overlay`, whose classes it composes. `src/main.py` passes it
through `GL_TYPES`, so the Symmetry Lab, which shares that dict (AD-SYM-04 L-9), draws it too.

Slice A3 (2026-10-24) adds the Re-Symmetrize preview (`set_preview`), moved from the Lab's
`ResymPreviewLineOverlay` / `LabPointOverlay`: blue = a target-side vertex that will move, light
green = a seam vertex laid into the plane (both with a line to the new position), light red = a
target-side vertex without partner that stays. Lines and points without depth test, like the Lab's.

Look: the Lab's values (moved with the overlay from `experiments/symmetry_lab/lab_overlays.py`,
colour legend of the Lab README), `PROVISIONAL` in the app (AD-013 A5). The outline is
depth-tested, the points are not (like every point layer). Data needs no GL; vertex lists are
created on the first draw.
"""

from __future__ import annotations

from .gl_line_overlay import FlatColorLayers
from .gl_point_overlay import SELECTED_POINT_SIZE, GLPointOverlay

PLANE_LAYER = "symmetry_plane"
SEAM_LAYER = "symmetry_seam"
UNPAIRED_LAYER = "symmetry_unpaired"
AMBIGUOUS_LAYER = "symmetry_ambiguous"
#: Point layers in draw order.
MARKER_LAYERS = (SEAM_LAYER, UNPAIRED_LAYER, AMBIGUOUS_LAYER)
RESYM_MOVE_LAYER = "resym_move"
RESYM_SEAM_LAYER = "resym_seam"
RESYM_KEEP_LAYER = "resym_keep"
RESYM_MOVE_LINE_LAYER = "resym_move_lines"
RESYM_SEAM_LINE_LAYER = "resym_seam_lines"
PREVIEW_POINT_LAYERS = (RESYM_MOVE_LAYER, RESYM_SEAM_LAYER, RESYM_KEEP_LAYER)
PREVIEW_LINE_LAYERS = (RESYM_MOVE_LINE_LAYER, RESYM_SEAM_LINE_LAYER)

# PROVISIONAL look: the Lab's values (lab_render.py as of 2026-10-03).
PLANE_COLOR = (0.4, 0.75, 1.0, 1.0)
SEAM_VERTEX_COLOR = (0.2, 0.9, 0.3, 1.0)
UNPAIRED_VERTEX_COLOR = (0.95, 0.2, 0.85, 1.0)
AMBIGUOUS_VERTEX_COLOR = (1.0, 1.0, 1.0, 1.0)
MARKER_POINT_SIZE = 7.0
PLANE_LINE_WIDTH = 1.0
# The Lab's preview colours (lab_render.py as of 2026-10-03, moved from lab_overlays.py).
RESYM_MOVE_COLOR = (0.25, 0.5, 1.0, 1.0)
RESYM_SEAM_COLOR = (0.75, 1.0, 0.1, 1.0)
RESYM_KEEP_COLOR = (1.0, 0.55, 0.55, 1.0)
#: "large" in the Lab legend = the app's selection size.
RESYM_POINT_SIZE = SELECTED_POINT_SIZE
RESYM_LINE_WIDTH = 1.0


class _PlaneLines(FlatColorLayers):
    LAYERS = (PLANE_LAYER,)
    LAYER_STYLES = {PLANE_LAYER: (PLANE_COLOR, PLANE_LINE_WIDTH)}
    VERTS_PER_ITEM = 2

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES


class _Markers(GLPointOverlay):
    LAYERS = MARKER_LAYERS
    LAYER_STYLES = {
        SEAM_LAYER: (SEAM_VERTEX_COLOR, MARKER_POINT_SIZE),
        UNPAIRED_LAYER: (UNPAIRED_VERTEX_COLOR, MARKER_POINT_SIZE),
        AMBIGUOUS_LAYER: (AMBIGUOUS_VERTEX_COLOR, MARKER_POINT_SIZE),
    }


class _PreviewLines(FlatColorLayers):
    LAYERS = PREVIEW_LINE_LAYERS
    LAYER_STYLES = {
        RESYM_MOVE_LINE_LAYER: (RESYM_MOVE_COLOR, RESYM_LINE_WIDTH),
        RESYM_SEAM_LINE_LAYER: (RESYM_SEAM_COLOR, RESYM_LINE_WIDTH),
    }
    NO_DEPTH_LAYERS = frozenset(PREVIEW_LINE_LAYERS)
    VERTS_PER_ITEM = 2

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES


class _PreviewPoints(GLPointOverlay):
    LAYERS = PREVIEW_POINT_LAYERS
    LAYER_STYLES = {
        RESYM_MOVE_LAYER: (RESYM_MOVE_COLOR, RESYM_POINT_SIZE),
        RESYM_SEAM_LAYER: (RESYM_SEAM_COLOR, RESYM_POINT_SIZE),
        RESYM_KEEP_LAYER: (RESYM_KEEP_COLOR, RESYM_POINT_SIZE),
    }


class GLSymmetryOverlay:
    """Plane outline (4 lines) and the three marker layers; empty until data is pushed.

    Draw order: outline, seam / unpaired / ambiguous points, then the preview lines and points (the
    Lab's order since A2: the preview above the state markers). The Viewport draws extra
    overlays after the tool lines and before its own point overlay, so the app's hover and
    selection points stay on top."""

    LAYER_STYLES = {
        **_PlaneLines.LAYER_STYLES,
        **_Markers.LAYER_STYLES,
        **_PreviewLines.LAYER_STYLES,
        **_PreviewPoints.LAYER_STYLES,
    }

    def __init__(self) -> None:
        self._lines = _PlaneLines()
        self._markers = _Markers()
        self._preview_lines = _PreviewLines()
        self._preview_points = _PreviewPoints()

    # -- data (no GL) -----------------------------------------------------------

    def set_segments(self, segments) -> None:
        """The outline as (start, end) world-position pairs; re-uploaded only if it differs."""
        self._lines._set(PLANE_LAYER, segments)

    def set_markers(self, seam, unpaired, ambiguous) -> None:
        """World positions of the three marker layers; each is rebuilt only if it differs."""
        for layer, positions in zip(MARKER_LAYERS, (seam, unpaired, ambiguous)):
            self._markers.set_points(layer, positions)

    def set_preview(self, move_points, seam_points, keep_points, move_lines, seam_lines) -> None:
        """The Re-Symmetrize preview (all empty = closed): points and (start, end) line pairs."""
        for layer, positions in zip(PREVIEW_POINT_LAYERS, (move_points, seam_points, keep_points)):
            self._preview_points.set_points(layer, positions)
        for layer, segments in zip(PREVIEW_LINE_LAYERS, (move_lines, seam_lines)):
            self._preview_lines._set(layer, segments)

    def segments(self, layer: str = PLANE_LAYER) -> list:
        """The current segments of the outline or a preview line layer (diagnostics/tests)."""
        source = self._lines if layer == PLANE_LAYER else self._preview_lines
        flat = source._flat[layer]
        points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        return list(zip(points[0::2], points[1::2]))

    def points(self, layer: str) -> list:
        """The current positions of one marker or preview point layer (diagnostics/tests)."""
        if layer in PREVIEW_POINT_LAYERS:
            return self._preview_points.points(layer)
        return self._markers.points(layer)

    # -- GL -----------------------------------------------------------------------

    def draw(self, camera_uniforms) -> None:
        self._lines.draw(camera_uniforms)
        self._markers.draw(camera_uniforms)
        self._preview_lines.draw(camera_uniforms)
        self._preview_points.draw(camera_uniforms)
