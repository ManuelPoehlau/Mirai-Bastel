"""Lab-Overlay auf dem Production-Viewport (WP-SYM-LAB-03 Slice 1b/2/3, Hook H1).

Seit AD-SYM-04 Slice A2 (2026-10-14) zeichnet die **App** Ebenen-Umriss und Zustands-Marker
(Seam grün, ohne Partner magenta, mehrdeutig weiß), seit Slice A3 (2026-10-24) auch die
Re-Symmetrize-Vorschau: `mirai.symmetry_display.SymmetryDisplay` mit der GL-Senke
`viewport.gl_symmetry_overlay.GLSymmetryOverlay`, die das Lab über `src_main.GL_TYPES` mitbekommt
(L-9). Dorthin **verschoben** (K-2) sind Befund, Umriss, `geometry_signature`, `ReportCache`, der
Aufschub während eines Transforms und die frühere `ResymPreviewLineOverlay` samt den
Vorschau-Layern; nichts wird doppelt gezeichnet. Hier bleibt, was S-2 nicht in die App bringt:

- `LabPointOverlay` (`GLPointOverlay`): die gespiegelten Partner von Hover und Auswahl türkis
  (`mirai.symmetry.mirrored_selection`, nur im Vertex-Modus). Ohne Depth-Test wie alle Punkte.

Farbe = der Wert aus dem alten `lab_render.py` (README-Farblegende). Die Partner-Marker sind so
groß wie die Auswahl der App, damit ein Partner neben dem gelben Original gleich gewichtet aussieht.

Zeichenreihenfolge (README „Zeichenreihenfolge"): der Viewport zeichnet die Zusatz-Overlays in
der Reihenfolge ihres Anhängens nach den Tool-Linien und vor seinem Punkt-Overlay. Das Overlay
der App hängt `init_scene` an, das Lab-Overlay danach: Ebene → Zustands-Marker → Vorschau-Linien
→ Vorschau-Punkte (App) → Hover-Partner → Auswahl-Partner (Lab) → Hover und Auswahl der App obenauf.

Neu berechnet wird nur, was sich geändert hat (Slice 2, Plan A3). Die Partner hängen an Auswahl
bzw. Hover und an der Geometrie (`geometry_signature`); beide werden getrennt neu bestimmt. Die
Zuordnung kommt aus dem Befund-Cache des Labs (`SymmetryAppLab.reports`, eine `ReportCache` der
App-Klasse, geteilt mit der HUD-Zeile). **Während eines laufenden Transforms** (`defer()` wahr)
bleiben die Partner-IDs die vom Drag-Start, nur ihre Positionen folgen den bewegten Vertices;
solange etwas aufgeschoben ist, hält das Overlay `dirty` gesetzt.
"""

from __future__ import annotations

from typing import Optional

from core import Mesh, Selection, VertexId
from core.selection import SelectionMode
from mirai.symmetry import mirrored_selection
from mirai.symmetry_display import (
    ReportCache,
    SymmetryReport,
    geometry_signature,
    only_positions_differ,
)
from viewport.gl_point_overlay import SELECTED_POINT_SIZE, GLPointOverlay

HOVER_PARTNER_LAYER = "symmetry_hover_partner"
SELECTION_PARTNER_LAYER = "symmetry_selection_partner"

# Wert aus lab_render.py (Stand 2026-10-03).
MIRRORED_VERTEX_COLOR = (0.1, 0.85, 0.95, 1.0)
PARTNER_POINT_SIZE = SELECTED_POINT_SIZE


class _Partners:
    """Gespiegelte Partner einer Vertex-Menge (`mirrored_selection`), mit den IDs
    der letzten Ableitung und der Geometrie, zu der sie gehören."""

    def __init__(self) -> None:
        self.source: object = None
        self.signature: object = None
        self.ids: frozenset = frozenset()

    def update(
        self,
        mesh: Mesh,
        source: frozenset,
        signature: tuple,
        defer: bool,
        report: SymmetryReport,
    ) -> bool:
        """True = `mirrored_selection` lief. Bei gleicher Quelle und laufendem
        Transform bleiben die IDs (Modul-Docstring). Die Zuordnung kommt aus dem
        Befund (`report.correspondence`), nicht aus einer neuen Ableitung: ein
        Hover-Wechsel kostet so einen Dict-Lookup statt einer Zuordnung des ganzen
        Mesh (Plan A3, Referenz-PC 17 ms je Hover-Wechsel auf
        `man_with_shoes_basemesh`). Der Befund gehört zur selben Geometrie wie
        `signature`, außer während eines Transforms, wo ein symmetrischer Move die
        Paarung erhält (Modul-Docstring)."""
        if source == self.source and (
            signature == self.signature
            or (defer and only_positions_differ(self.signature, signature))
        ):
            return False
        self.ids = (
            frozenset(mirrored_selection(mesh, source, report.correspondence))
            if source
            else frozenset()
        )
        self.source = source
        self.signature = signature
        return bool(source)


class LabPointOverlay(GLPointOverlay):
    """Hover- und Auswahl-Partner; alles leer bei Symmetrie aus (bis AD-SYM-04 A2
    `SymmetryStateOverlay`, bis A3 auch die Punkte der Re-Symmetrize-Vorschau)."""

    LAYERS = (HOVER_PARTNER_LAYER, SELECTION_PARTNER_LAYER)
    LAYER_STYLES = {
        HOVER_PARTNER_LAYER: (MIRRORED_VERTEX_COLOR, PARTNER_POINT_SIZE),
        SELECTION_PARTNER_LAYER: (MIRRORED_VERTEX_COLOR, PARTNER_POINT_SIZE),
    }

    def __init__(self, reports: Optional[ReportCache] = None) -> None:
        super().__init__()
        self.dirty = False
        #: Befund-Cache des Labs (Zuordnung für die Partner); sein `defer` gilt auch für die Partner.
        self.reports = reports if reports is not None else ReportCache()
        self._hover = _Partners()
        self._selection = _Partners()
        #: Anzahl der Partner-Ableitungen (je `mirrored_selection`-Aufruf).
        self.partner_recomputes = 0

    @property
    def hover_partners(self) -> frozenset:
        return self._hover.ids

    @property
    def selection_partners(self) -> frozenset:
        return self._selection.ids

    def sync(self, mesh: Mesh, selection: Selection) -> None:
        defer = self.reports.defer()
        signature = geometry_signature(mesh)
        report = self.reports.get(mesh, signature)

        vertex_mode = selection.mode is SelectionMode.VERTEX
        hovered = selection.hovered if vertex_mode else None
        # Edge-/Face-IDs sind ebenfalls ints: nur ein echter Vertex hat einen Partner.
        hover_source = frozenset({hovered}) if isinstance(hovered, VertexId) else frozenset()
        selection_source = frozenset(selection.vertices) if vertex_mode else frozenset()
        # Positionen immer aus dem aktuellen Mesh: während eines Transforms wandern die
        # Partner mit, auch wenn ihre IDs vom Drag-Start stammen.
        for partners, source, layer in (
            (self._hover, hover_source, HOVER_PARTNER_LAYER),
            (self._selection, selection_source, SELECTION_PARTNER_LAYER),
        ):
            if partners.update(mesh, source, signature, defer, report):
                self.partner_recomputes += 1
            self.set_points(layer, _positions(mesh, partners.ids))
        self.dirty = defer and (
            self.reports.stale(signature)
            or self._hover.signature != signature
            or self._selection.signature != signature
        )


def _positions(mesh: Mesh, ids) -> list:
    return [mesh.vertex_position(v) for v in sorted(ids, key=int)]


def build_lab_overlays(reports: Optional[ReportCache] = None) -> tuple[LabPointOverlay]:
    """Das Lab-Overlay (Partner); es hängt nach dem Symmetrie-Overlay der App (Ebene,
    Zustands-Marker, Vorschau). `reports` = der Befund-Cache des Labs (HUD und Partner teilen
    denselben Lauf, sein `defer` gilt für die Partner)."""
    return (LabPointOverlay(reports),)
