"""GL sink of the app's symmetry display: plane outline and problem markers (AD-SYM-04 slice A2).

Q-2 = S-2 (Manu, 2026-10-14): the plane outline as lines, then the problem markers as points -
seam green, without partner magenta, ambiguous white. No partner markers (they stay in the
Symmetry Lab). `Application` builds this type from `init_scene(symmetry_overlay_type=...)` and
hands it to `mirai.symmetry_display.SymmetryDisplay`, which decides what is shown and pushes it
here (`set_segments`, `set_markers`); this module knows no symmetry, only its layers and look -
like `gl_line_overlay`/`gl_point_overlay`, whose classes it composes. `src/main.py` passes it
through `GL_TYPES`, so the Symmetry Lab, which shares that dict (AD-SYM-04 L-9), draws it too.

Look: the Lab's values (moved with the overlay from `experiments/symmetry_lab/lab_overlays.py`,
colour legend of the Lab README), `PROVISIONAL` in the app (AD-013 A5). The outline is
depth-tested, the points are not (like every point layer). Data needs no GL; vertex lists are
created on the first draw.
"""

from __future__ import annotations

from .gl_line_overlay import FlatColorLayers
from .gl_point_overlay import GLPointOverlay

PLANE_LAYER = "symmetry_plane"
SEAM_LAYER = "symmetry_seam"
UNPAIRED_LAYER = "symmetry_unpaired"
AMBIGUOUS_LAYER = "symmetry_ambiguous"
#: Point layers in draw order.
MARKER_LAYERS = (SEAM_LAYER, UNPAIRED_LAYER, AMBIGUOUS_LAYER)

# PROVISIONAL look: the Lab's values (lab_render.py as of 2026-10-03).
PLANE_COLOR = (0.4, 0.75, 1.0, 1.0)
SEAM_VERTEX_COLOR = (0.2, 0.9, 0.3, 1.0)
UNPAIRED_VERTEX_COLOR = (0.95, 0.2, 0.85, 1.0)
AMBIGUOUS_VERTEX_COLOR = (1.0, 1.0, 1.0, 1.0)
MARKER_POINT_SIZE = 7.0
PLANE_LINE_WIDTH = 1.0


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


class GLSymmetryOverlay:
    """Plane outline (4 lines) and the three marker layers; empty until data is pushed.

    Draw order: outline, then seam / unpaired / ambiguous points. The Viewport draws extra
    overlays after the tool lines and before its own point overlay, so the app's hover and
    selection points stay on top."""

    LAYER_STYLES = {**_PlaneLines.LAYER_STYLES, **_Markers.LAYER_STYLES}

    def __init__(self) -> None:
        self._lines = _PlaneLines()
        self._markers = _Markers()

    # -- data (no GL) -----------------------------------------------------------

    def set_segments(self, segments) -> None:
        """The outline as (start, end) world-position pairs; re-uploaded only if it differs."""
        self._lines._set(PLANE_LAYER, segments)

    def set_markers(self, seam, unpaired, ambiguous) -> None:
        """World positions of the three marker layers; each is rebuilt only if it differs."""
        for layer, positions in zip(MARKER_LAYERS, (seam, unpaired, ambiguous)):
            self._markers.set_points(layer, positions)

    def segments(self) -> list:
        """The current outline segments (diagnostics/tests)."""
        flat = self._lines._flat[PLANE_LAYER]
        points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        return list(zip(points[0::2], points[1::2]))

    def points(self, layer: str) -> list:
        """The current positions of one marker layer (diagnostics/tests)."""
        return self._markers.points(layer)

    # -- GL -----------------------------------------------------------------------

    def draw(self, camera_uniforms) -> None:
        self._lines.draw(camera_uniforms)
        self._markers.draw(camera_uniforms)
