"""Lab-Overlays auf dem Production-Viewport (WP-SYM-LAB-03 Slice 1b, Hook H1).

Zwei Unterklassen der `src`-Overlays, angehängt über `Viewport.add_overlay`; `src`
kennt weder diese Layer noch ihre Farben (Plan §3.1 H1, AD-013 I7):

- `SymmetryPlaneOverlay` (`FlatColorLayers`, `GL_LINES`): Umriss der Symmetrie-Ebene
  aus `lab_draw_data.plane_outline_data` (Slice 3), hellblau, mit Depth-Test wie im
  alten Renderer.
- `SymmetryStateOverlay` (`GLPointOverlay`): Seam grün, ohne Partner magenta,
  mehrdeutig weiß (`symmetry_report`), ohne Depth-Test wie alle Punkte.

Farben und Punktgröße = die Werte aus `lab_render.py` (README-Farblegende); hier
kopiert statt importiert, weil `lab_render` mit dem alten Renderer in Slice 5 geht.

Zeichenreihenfolge (README „Zeichenreihenfolge"): der Viewport zeichnet die
Zusatz-Overlays nach den Tool-Linien und vor seinem Punkt-Overlay, also liegen
Hover und Auswahl über den Symmetrie-Markierungen.

Neu berechnet wird in `sync(mesh, selection)`, das der Viewport bei jeder
Selektions-/Hover-, Positions- oder Topologie-Meldung aufruft (deckt Undo/Redo,
Drag und Knife-Commit ab) — und wenn `dirty` gesetzt ist: ein Shift+S ändert nur
die Definition und meldet dem Viewport nichts, das Lab setzt dann `dirty` selbst.
Kein Cache: der Befund kostet pro Meldung, nicht pro Frame (Plan §1.3; ob das bei
einem symmetrischen Drag reicht, misst Slice 2, A3).
"""

from __future__ import annotations

from core import Mesh, Selection
from viewport.gl_line_overlay import FlatColorLayers
from viewport.gl_point_overlay import GLPointOverlay

from .lab_draw_data import plane_outline_data
from .lab_symmetry import current_axis, symmetry_report

PLANE_LAYER = "symmetry_plane"
SEAM_LAYER = "symmetry_seam"
UNPAIRED_LAYER = "symmetry_unpaired"
AMBIGUOUS_LAYER = "symmetry_ambiguous"

# Werte aus lab_render.py (Stand 2026-10-03).
PLANE_COLOR = (0.4, 0.75, 1.0, 1.0)
SEAM_VERTEX_COLOR = (0.2, 0.9, 0.3, 1.0)
UNPAIRED_VERTEX_COLOR = (0.95, 0.2, 0.85, 1.0)
AMBIGUOUS_VERTEX_COLOR = (1.0, 1.0, 1.0, 1.0)
STATE_POINT_SIZE = 7.0
PLANE_LINE_WIDTH = 1.0


class SymmetryPlaneOverlay(FlatColorLayers):
    """Ebenen-Umriss (4 Linien), leer bei Symmetrie aus."""

    LAYERS = (PLANE_LAYER,)
    LAYER_STYLES = {PLANE_LAYER: (PLANE_COLOR, PLANE_LINE_WIDTH)}
    VERTS_PER_ITEM = 2

    def __init__(self) -> None:
        super().__init__()
        self.dirty = False

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES

    def sync(self, mesh: Mesh, selection: Selection) -> None:
        flat = plane_outline_data(mesh, current_axis(mesh))
        points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        self._set(PLANE_LAYER, list(zip(points[0::2], points[1::2])))
        self.dirty = False

    def segments(self) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
        """Die aktuellen Linien (Diagnose/Tests)."""
        flat = self._flat[PLANE_LAYER]
        points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        return list(zip(points[0::2], points[1::2]))


class SymmetryStateOverlay(GLPointOverlay):
    """Seam / ohne Partner / mehrdeutig als Punkte, leer bei Symmetrie aus."""

    LAYERS = (SEAM_LAYER, UNPAIRED_LAYER, AMBIGUOUS_LAYER)
    LAYER_STYLES = {
        SEAM_LAYER: (SEAM_VERTEX_COLOR, STATE_POINT_SIZE),
        UNPAIRED_LAYER: (UNPAIRED_VERTEX_COLOR, STATE_POINT_SIZE),
        AMBIGUOUS_LAYER: (AMBIGUOUS_VERTEX_COLOR, STATE_POINT_SIZE),
    }

    def __init__(self) -> None:
        super().__init__()
        self.dirty = False

    def sync(self, mesh: Mesh, selection: Selection) -> None:
        report = symmetry_report(mesh)
        for layer, ids in (
            (SEAM_LAYER, report.seam),
            (UNPAIRED_LAYER, report.unpaired),
            (AMBIGUOUS_LAYER, report.ambiguous),
        ):
            self.set_points(layer, [mesh.vertex_position(v) for v in sorted(ids)])
        self.dirty = False


def build_lab_overlays() -> tuple[SymmetryPlaneOverlay, SymmetryStateOverlay]:
    """Die Overlays in Zeichenreihenfolge (Ebene, dann Zustands-Punkte)."""
    return SymmetryPlaneOverlay(), SymmetryStateOverlay()
