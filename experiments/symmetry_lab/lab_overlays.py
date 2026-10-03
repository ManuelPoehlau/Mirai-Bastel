"""Lab-Overlays auf dem Production-Viewport (WP-SYM-LAB-03 Slice 1b/2, Hook H1).

Zwei Unterklassen der `src`-Overlays, angehängt über `Viewport.add_overlay`; `src`
kennt weder diese Layer noch ihre Farben (Plan §3.1 H1, AD-013 I7):

- `SymmetryPlaneOverlay` (`FlatColorLayers`, `GL_LINES`): Umriss der Symmetrie-Ebene
  aus `lab_symmetry.plane_outline_data` (Slice 3), hellblau, mit Depth-Test wie im
  alten Renderer.
- `SymmetryStateOverlay` (`GLPointOverlay`): Seam grün, ohne Partner magenta,
  mehrdeutig weiß (`symmetry_report`), darüber (Slice 3) die Punkte der
  Re-Symmetrize-Vorschau, dann (Slice 2) die gespiegelten Partner von Hover und
  Auswahl türkis (`mirai.symmetry.mirrored_selection`, nur im Vertex-Modus). Ohne
  Depth-Test wie alle Punkte.
- `ResymPreviewLineOverlay` (`FlatColorLayers`, `GL_LINES`, Slice 3): die Linien der
  Vorschau von der aktuellen zur neuen Position, ohne Depth-Test wie im alten
  Renderer (dort lief die Vorschau nach dem Abschalten des Depth-Tests).

Vorschau (Slice 3, E15): blau = Zielseiten-Vertex wird bewegt, hellgrün = Seam-Vertex
wird auf die Ebene gelegt (beide mit Linie), hellrot = Zielseiten-Vertex ohne Partner
bleibt. Daten aus `lab_resymmetrize.resym_preview_data` zum offenen Plan
(`preview()` = `SymmetryAppLab.preview`); leer ohne Vorschau. Das Mesh kann sich
bei offener Vorschau nicht ändern (Gate), deshalb hängen die Layer nur am Plan
(neu nur bei einem anderen Plan-Objekt); das Lab setzt beim Öffnen und Schließen
`dirty`.

Farben und Punktgröße der Zustands-Marker = die Werte aus dem alten `lab_render.py`
(README-Farblegende), kopiert; der alte Renderer ist seit Slice 5 gelöscht. Die Partner-Marker sind so groß wie die Auswahl der App
(8 px), damit ein Partner neben dem gelben Original gleich gewichtet aussieht.

Zeichenreihenfolge (README „Zeichenreihenfolge"): der Viewport zeichnet die
Zusatz-Overlays nach den Tool-Linien und vor seinem Punkt-Overlay, also liegen
Hover und Auswahl der App über allen Lab-Markern; Lab-Overlays in der Reihenfolge
Ebene → Vorschau-Linien → Punkte, innerhalb der Punkte Zustand → Vorschau →
Hover-Partner → Auswahl-Partner (wie im alten Lab). Einzige Abweichung vom alten
Renderer: die Vorschau-Linien liegen unter den Zustands-Markern statt darüber
(Linien und Punkte stecken in verschiedenen Overlay-Klassen).

Neu berechnet wird nur, was sich geändert hat (Slice 2, Plan A3). Der Viewport ruft
`sync(mesh, selection)` bei jeder Selektions-/Hover-, Positions- oder
Topologie-Meldung (und wenn `dirty` gesetzt ist: ein Shift+S ändert nur die
Definition, das Lab setzt dann `dirty` selbst).

- Ebene und Zustands-Marker hängen nicht an Auswahl oder Hover; sie vergleichen eine
  billige Signatur der Geometrie (`geometry_signature`) und rechnen nur neu, wenn
  sie sich geändert hat. Eine reine Hover- oder Auswahl-Meldung kostet sie nichts.
- Die Partner hängen zusätzlich an Auswahl bzw. Hover; beide werden getrennt
  voneinander neu bestimmt.
- **Während eines laufenden Transforms** (`defer()` wahr, im Lab
  `app.interaction_owner == "transform"`) wird eine reine Positionsänderung nicht
  neu abgeleitet: Befund, Ebenen-Umriss und Partner-IDs bleiben die vom Drag-Start,
  nur die Positionen der gezeigten Marker folgen den bewegten Vertices (eine
  geänderte Definition, Topologie oder Seam wird immer sofort abgeleitet). Ein symmetrischer Move erhält die
  Paarung (Partner exakt gespiegelt, Seam in der Ebene), die IDs bleiben also
  gültig. Gemessen (Container, `probe_drag_cost.py`): ohne das p95 11,5 ms je
  Bewegung auf `man_with_shoes_basemesh`, über der Schwelle von 8 ms (Plan A3).
  Solange etwas aufgeschoben ist, hält das Overlay `dirty` gesetzt; der erste
  `sync()` nach dem Ende (Commit meldet dem Viewport nichts) rechnet dann voll.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from core import Mesh, Selection, VertexId
from core.selection import SelectionMode
from mirai.symmetry import mirrored_selection
from viewport.gl_line_overlay import FlatColorLayers
from viewport.gl_point_overlay import SELECTED_POINT_SIZE, GLPointOverlay

from .lab_resymmetrize import ResymPlan, resym_preview_data
from .lab_symmetry import SymmetryReport, current_axis, plane_outline_data, symmetry_report

PLANE_LAYER = "symmetry_plane"
SEAM_LAYER = "symmetry_seam"
UNPAIRED_LAYER = "symmetry_unpaired"
AMBIGUOUS_LAYER = "symmetry_ambiguous"
HOVER_PARTNER_LAYER = "symmetry_hover_partner"
SELECTION_PARTNER_LAYER = "symmetry_selection_partner"
RESYM_MOVE_LAYER = "resym_move"
RESYM_SEAM_LAYER = "resym_seam"
RESYM_KEEP_LAYER = "resym_keep"
RESYM_MOVE_LINE_LAYER = "resym_move_lines"
RESYM_SEAM_LINE_LAYER = "resym_seam_lines"

# Werte aus lab_render.py (Stand 2026-10-03).
PLANE_COLOR = (0.4, 0.75, 1.0, 1.0)
SEAM_VERTEX_COLOR = (0.2, 0.9, 0.3, 1.0)
UNPAIRED_VERTEX_COLOR = (0.95, 0.2, 0.85, 1.0)
AMBIGUOUS_VERTEX_COLOR = (1.0, 1.0, 1.0, 1.0)
MIRRORED_VERTEX_COLOR = (0.1, 0.85, 0.95, 1.0)
RESYM_MOVE_COLOR = (0.25, 0.5, 1.0, 1.0)
RESYM_SEAM_COLOR = (0.75, 1.0, 0.1, 1.0)
RESYM_KEEP_COLOR = (1.0, 0.55, 0.55, 1.0)
STATE_POINT_SIZE = 7.0
PARTNER_POINT_SIZE = SELECTED_POINT_SIZE
#: „groß" in der Legende = die Auswahlgröße; auf dem App-Pfad die der App (8 px),
#: wie die Partner-Marker (Slice 2).
RESYM_POINT_SIZE = SELECTED_POINT_SIZE
PLANE_LINE_WIDTH = 1.0
RESYM_LINE_WIDTH = 1.0


def geometry_signature(mesh: Mesh) -> tuple:
    """Alles, wovon Ebenen-Umriss und Zustands-Marker abhängen: Definition,
    Vertex-IDs mit Positionen und die Endpunkte der Seam-Edges.

    Der Core hat keinen Änderungszähler (`Mesh` exponiert keinen); das hier kostet
    O(V) Tupel-Zugriffe statt O(V) Spiegelungen + Dict-Lookups des Befunds —
    gemessen (Container) 0,05 ms gegen 4 ms auf `man_with_shoes_basemesh`.
    Bleibt die Reihenfolge von `all_vertex_ids()` nicht gleich, wird nur
    unnötig neu gebaut, nie falsch übersprungen.
    """
    ids = tuple(mesh.all_vertex_ids())
    definition = mesh.symmetry_definition
    seam: tuple = ()
    if definition is not None:
        seam = tuple(
            mesh.edge_vertices(e) if mesh.is_valid_edge(e) else None
            for e in sorted(definition.seam_edges)
        )
    return (definition, ids, tuple(map(mesh.vertex_position, ids)), seam)


def only_positions_differ(old: object, new: tuple) -> bool:
    """Unterscheiden sich zwei Signaturen nur in den Positionen? Nur so eine
    Änderung darf während eines Transforms aufgeschoben werden — eine andere
    Definition, Topologie oder Seam nie (z. B. Shift+S kurz vor W ohne Frame dazwischen)."""
    return (
        isinstance(old, tuple)
        and old[0] == new[0]
        and old[1] == new[1]
        and old[3] == new[3]
    )


def _never() -> bool:
    return False


def _no_preview() -> Optional[ResymPlan]:
    return None


def _triples(flat: list[float]) -> list[tuple[float, float, float]]:
    return [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]


class ReportCache:
    """Der `SymmetryReport` zur aktuellen Geometrie, neu nur bei geänderter
    `geometry_signature` — eine reine Positionsänderung nicht, solange `defer()`
    wahr ist (laufender Transform, Modul-Docstring). Eine Instanz teilen sich
    Zustands-Marker und HUD."""

    def __init__(self, defer: Optional[Callable[[], bool]] = None) -> None:
        self.defer = defer or _never
        self._signature: object = None
        self._report: Optional[SymmetryReport] = None
        #: Anzahl der `symmetry_report`-Läufe (Diagnose/Tests, Probe).
        self.recomputes = 0

    def stale(self, signature: tuple) -> bool:
        """Weicht der gelieferte Befund von der Geometrie `signature` ab?"""
        return self._report is None or signature != self._signature

    def get(self, mesh: Mesh, signature: Optional[tuple] = None) -> SymmetryReport:
        if signature is None:
            signature = geometry_signature(mesh)
        if self._report is None or (
            signature != self._signature
            and not (only_positions_differ(self._signature, signature) and self.defer())
        ):
            self._report = symmetry_report(mesh)
            self._signature = signature
            self.recomputes += 1
        return self._report


class SymmetryPlaneOverlay(FlatColorLayers):
    """Ebenen-Umriss (4 Linien), leer bei Symmetrie aus."""

    LAYERS = (PLANE_LAYER,)
    LAYER_STYLES = {PLANE_LAYER: (PLANE_COLOR, PLANE_LINE_WIDTH)}
    VERTS_PER_ITEM = 2

    def __init__(self, defer: Optional[Callable[[], bool]] = None) -> None:
        super().__init__()
        self.dirty = False
        self.defer = defer or _never
        self._signature: object = None
        #: Anzahl der Neuberechnungen (Diagnose/Tests, Probe).
        self.recomputes = 0

    @staticmethod
    def _primitive():
        from pyglet import gl

        return gl.GL_LINES

    def sync(self, mesh: Mesh, selection: Selection) -> None:
        self.dirty = False
        signature = geometry_signature(mesh)
        if self.recomputes and signature == self._signature:
            return
        if self.recomputes and only_positions_differ(self._signature, signature) and self.defer():
            self.dirty = True  # nach dem Transform nachholen
            return
        self._signature = signature
        points = _triples(plane_outline_data(mesh, current_axis(mesh)))
        self._set(PLANE_LAYER, list(zip(points[0::2], points[1::2])))
        self.recomputes += 1

    def segments(self) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
        """Die aktuellen Linien (Diagnose/Tests)."""
        flat = self._flat[PLANE_LAYER]
        points = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        return list(zip(points[0::2], points[1::2]))


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


class SymmetryStateOverlay(GLPointOverlay):
    """Seam / ohne Partner / mehrdeutig, dann Hover- und Auswahl-Partner als Punkte;
    alles leer bei Symmetrie aus."""

    LAYERS = (
        SEAM_LAYER,
        UNPAIRED_LAYER,
        AMBIGUOUS_LAYER,
        RESYM_MOVE_LAYER,
        RESYM_SEAM_LAYER,
        RESYM_KEEP_LAYER,
        HOVER_PARTNER_LAYER,
        SELECTION_PARTNER_LAYER,
    )
    LAYER_STYLES = {
        SEAM_LAYER: (SEAM_VERTEX_COLOR, STATE_POINT_SIZE),
        UNPAIRED_LAYER: (UNPAIRED_VERTEX_COLOR, STATE_POINT_SIZE),
        AMBIGUOUS_LAYER: (AMBIGUOUS_VERTEX_COLOR, STATE_POINT_SIZE),
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
        #: Befund-Cache; sein `defer` gilt auch für die Partner.
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
    def recomputes(self) -> int:
        """Läufe des Symmetrie-Befunds (die teure Hälfte, Plan A3)."""
        return self.reports.recomputes

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
        # Positionen immer aus dem aktuellen Mesh: während eines Transforms
        # wandern die Marker mit, auch wenn ihre IDs vom Drag-Start stammen.
        # `set_points` baut nur neu, wenn sich die Punkte wirklich ändern.
        for layer, ids in (
            (SEAM_LAYER, report.seam),
            (UNPAIRED_LAYER, report.unpaired),
            (AMBIGUOUS_LAYER, report.ambiguous),
        ):
            self.set_points(layer, _positions(mesh, ids))
        self._sync_preview(mesh)

        vertex_mode = selection.mode is SelectionMode.VERTEX
        hovered = selection.hovered if vertex_mode else None
        # Edge-/Face-IDs sind ebenfalls ints: nur ein echter Vertex hat einen Partner.
        hover_source = frozenset({hovered}) if isinstance(hovered, VertexId) else frozenset()
        selection_source = frozenset(selection.vertices) if vertex_mode else frozenset()
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
    defer: Optional[Callable[[], bool]] = None,
    preview: Optional[Callable[[], Optional[ResymPlan]]] = None,
) -> tuple[SymmetryPlaneOverlay, ResymPreviewLineOverlay, SymmetryStateOverlay]:
    """Die Overlays in Zeichenreihenfolge (Ebene, Vorschau-Linien, dann Punkte).
    `reports` = der Befund-Cache des Labs (HUD und Marker teilen denselben Lauf,
    sein `defer` gilt für die Marker); `defer` = dasselbe Prädikat für den
    Ebenen-Umriss; `preview` = der offene Re-Symmetrize-Plan des Labs."""
    return (
        SymmetryPlaneOverlay(defer),
        ResymPreviewLineOverlay(preview),
        SymmetryStateOverlay(reports, preview),
    )
