"""Lab-Overlays auf dem Production-Viewport (WP-SYM-LAB-03 Slice 1b/2/3, Hook H1).

Seit AD-SYM-04 Slice A2 (2026-10-14) zeichnet die **App** Ebenen-Umriss und Zustands-Marker
(Seam grün, ohne Partner magenta, mehrdeutig weiß): `mirai.symmetry_display.SymmetryDisplay`
mit der GL-Senke `viewport.gl_symmetry_overlay.GLSymmetryOverlay`, die das Lab über
`src_main.GL_TYPES` mitbekommt (L-9). Befund, Umriss, `geometry_signature`, `ReportCache` und
der Aufschub während eines Transforms sind dorthin **verschoben** (K-2); das frühere
`SymmetryPlaneOverlay` und die Zustands-Layer gibt es hier nicht mehr, nichts wird doppelt
gezeichnet. Hier bleibt, was S-2 nicht in die App bringt bzw. was zu A3 gehört:

- `ResymPreviewLineOverlay` (`FlatColorLayers`, `GL_LINES`, Slice 3): die Linien der
  Re-Symmetrize-Vorschau von der aktuellen zur neuen Position, ohne Depth-Test wie im alten
  Renderer.
- `LabPointOverlay` (`GLPointOverlay`): die Punkte der Re-Symmetrize-Vorschau, dann (Slice 2)
  die gespiegelten Partner von Hover und Auswahl türkis (`mirai.symmetry.mirrored_selection`,
  nur im Vertex-Modus). Ohne Depth-Test wie alle Punkte.

Vorschau (Slice 3, E15): blau = Zielseiten-Vertex wird bewegt, hellgrün = Seam-Vertex
wird auf die Ebene gelegt (beide mit Linie), hellrot = Zielseiten-Vertex ohne Partner
bleibt. Daten aus `lab_resymmetrize.resym_preview_data` zum offenen Plan
(`preview()` = `SymmetryAppLab.preview`); leer ohne Vorschau. Das Mesh kann sich
bei offener Vorschau nicht ändern (Gate), deshalb hängen die Layer nur am Plan
(neu nur bei einem anderen Plan-Objekt); das Lab setzt beim Öffnen und Schließen
`dirty`.

Farben und Punktgröße = die Werte aus dem alten `lab_render.py` (README-Farblegende). Die
Partner-Marker sind so groß wie die Auswahl der App (8 px), damit ein Partner neben dem gelben
Original gleich gewichtet aussieht.

Zeichenreihenfolge (README „Zeichenreihenfolge"): der Viewport zeichnet die Zusatz-Overlays in
der Reihenfolge ihres Anhängens nach den Tool-Linien und vor seinem Punkt-Overlay. Das Overlay
der App hängt `init_scene` an, die Lab-Overlays danach: Ebene → Zustands-Marker (App) →
Vorschau-Linien → Vorschau-Punkte → Hover-Partner → Auswahl-Partner (Lab) → Hover und Auswahl
der App obenauf. Seit A2 liegen die Vorschau-Linien damit wieder **über** den Zustands-Markern,
wie im alten Renderer (`PROVISIONAL`; Verdikt 5 vom 2026-10-03 nahm die umgekehrte
Reihenfolge als „egal" hin).

Neu berechnet wird nur, was sich geändert hat (Slice 2, Plan A3). Die Partner hängen an Auswahl
bzw. Hover und an der Geometrie (`geometry_signature`); beide werden getrennt neu bestimmt. Die
Zuordnung kommt aus dem Befund-Cache des Labs (`SymmetryAppLab.reports`, eine `ReportCache` der
App-Klasse, geteilt mit der HUD-Zeile). **Während eines laufenden Transforms** (`defer()` wahr)
bleiben die Partner-IDs die vom Drag-Start, nur ihre Positionen folgen den bewegten Vertices;
solange etwas aufgeschoben ist, hält das Overlay `dirty` gesetzt.
"""

from __future__ import annotations

from collections.abc import Callable
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
from viewport.gl_line_overlay import FlatColorLayers
from viewport.gl_point_overlay import SELECTED_POINT_SIZE, GLPointOverlay

from .lab_resymmetrize import ResymPlan, resym_preview_data

HOVER_PARTNER_LAYER = "symmetry_hover_partner"
SELECTION_PARTNER_LAYER = "symmetry_selection_partner"
RESYM_MOVE_LAYER = "resym_move"
RESYM_SEAM_LAYER = "resym_seam"
RESYM_KEEP_LAYER = "resym_keep"
RESYM_MOVE_LINE_LAYER = "resym_move_lines"
RESYM_SEAM_LINE_LAYER = "resym_seam_lines"

# Werte aus lab_render.py (Stand 2026-10-03).
MIRRORED_VERTEX_COLOR = (0.1, 0.85, 0.95, 1.0)
RESYM_MOVE_COLOR = (0.25, 0.5, 1.0, 1.0)
RESYM_SEAM_COLOR = (0.75, 1.0, 0.1, 1.0)
RESYM_KEEP_COLOR = (1.0, 0.55, 0.55, 1.0)
PARTNER_POINT_SIZE = SELECTED_POINT_SIZE
#: „groß" in der Legende = die Auswahlgröße; auf dem App-Pfad die der App (8 px),
#: wie die Partner-Marker (Slice 2).
RESYM_POINT_SIZE = SELECTED_POINT_SIZE
RESYM_LINE_WIDTH = 1.0


def _no_preview() -> Optional[ResymPlan]:
    return None


def _triples(flat: list[float]) -> list[tuple[float, float, float]]:
    return [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]


class ResymPreviewLineOverlay(FlatColorLayers):
    """Linien der Re-Symmetrize-Vorschau (Slice 3): blau für die bewegten
    Zielseiten-Vertices, hellgrün für die Seam-Vertices; leer ohne Vorschau."""

    LAYERS = (RESYM_MOVE_LINE_LAYER, RESYM_SEAM_LINE_LAYER)
    LAYER_STYLES = {
        RESYM_MOVE_LINE_LAYER: (RESYM_MOVE_COLOR, RESYM_LINE_WIDTH),
        RESYM_SEAM_LINE_LAYER: (RESYM_SEAM_COLOR, RESYM_LINE_WIDTH),
    }
    NO_DEPTH_LAYERS = frozenset(LAYERS)
    VERTS_PER_ITEM = 2

    def __init__(self, preview: Optional[Callable[[], Optional[ResymPlan]]] = None) -> None:
        super().__init__()
        self.dirty = False
        self.preview = preview or _no_preview
        self._plan: object = None
        self._synced = False

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES

    def sync(self, mesh: Mesh, selection: Selection) -> None:
        self.dirty = False
        plan = self.preview()
        if self._synced and plan is self._plan:
            return
        self._plan = plan
        self._synced = True
        data = resym_preview_data(mesh, plan)
        for layer, flat in (
            (RESYM_MOVE_LINE_LAYER, data.move_lines),
            (RESYM_SEAM_LINE_LAYER, data.seam_lines),
        ):
            points = _triples(flat)
            self._set(layer, list(zip(points[0::2], points[1::2])))

    def segments(self, layer: str) -> list:
        """Die aktuellen Linien eines Layers (Diagnose/Tests)."""
        points = _triples(self._flat[layer])
        return list(zip(points[0::2], points[1::2]))


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
    """Punkte der Re-Symmetrize-Vorschau, dann Hover- und Auswahl-Partner; alles leer bei
    Symmetrie aus (bis AD-SYM-04 A2 `SymmetryStateOverlay`, mit den Zustands-Markern, die
    jetzt die App zeichnet)."""

    LAYERS = (
        RESYM_MOVE_LAYER,
        RESYM_SEAM_LAYER,
        RESYM_KEEP_LAYER,
        HOVER_PARTNER_LAYER,
        SELECTION_PARTNER_LAYER,
    )
    LAYER_STYLES = {
        RESYM_MOVE_LAYER: (RESYM_MOVE_COLOR, RESYM_POINT_SIZE),
        RESYM_SEAM_LAYER: (RESYM_SEAM_COLOR, RESYM_POINT_SIZE),
        RESYM_KEEP_LAYER: (RESYM_KEEP_COLOR, RESYM_POINT_SIZE),
        HOVER_PARTNER_LAYER: (MIRRORED_VERTEX_COLOR, PARTNER_POINT_SIZE),
        SELECTION_PARTNER_LAYER: (MIRRORED_VERTEX_COLOR, PARTNER_POINT_SIZE),
    }

    def __init__(
        self,
        reports: Optional[ReportCache] = None,
        preview: Optional[Callable[[], Optional[ResymPlan]]] = None,
    ) -> None:
        super().__init__()
        self.dirty = False
        #: Befund-Cache des Labs (Zuordnung für die Partner); sein `defer` gilt auch für die Partner.
        self.reports = reports if reports is not None else ReportCache()
        #: Der offene Re-Symmetrize-Plan oder None (Slice 3, Modul-Docstring).
        self.preview = preview or _no_preview
        self._preview_plan: object = None
        self._preview_synced = False
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
        self._sync_preview(mesh)

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

    def _sync_preview(self, mesh: Mesh) -> None:
        plan = self.preview()
        if self._preview_synced and plan is self._preview_plan:
            return
        self._preview_plan = plan
        self._preview_synced = True
        data = resym_preview_data(mesh, plan)
        self.set_points(RESYM_MOVE_LAYER, _triples(data.move_points))
        self.set_points(RESYM_SEAM_LAYER, _triples(data.seam_points))
        self.set_points(RESYM_KEEP_LAYER, _triples(data.keep_points))


def _positions(mesh: Mesh, ids) -> list:
    return [mesh.vertex_position(v) for v in sorted(ids, key=int)]


def build_lab_overlays(
    reports: Optional[ReportCache] = None,
    preview: Optional[Callable[[], Optional[ResymPlan]]] = None,
) -> tuple[ResymPreviewLineOverlay, LabPointOverlay]:
    """Die Lab-Overlays in Zeichenreihenfolge (Vorschau-Linien, dann Punkte); sie hängen
    nach dem Symmetrie-Overlay der App (Ebene, Zustands-Marker). `reports` = der
    Befund-Cache des Labs (HUD und Partner teilen denselben Lauf, sein `defer` gilt für die
    Partner); `preview` = der offene Re-Symmetrize-Plan des Labs."""
    return (
        ResymPreviewLineOverlay(preview),
        LabPointOverlay(reports, preview),
    )
