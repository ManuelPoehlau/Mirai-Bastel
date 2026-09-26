"""Selection-/Hover-Overlay für den Viewport v0.2.

Adaptiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/selection.py`) auf die reale
`src.core.Selection`-API (V/E/F-Modi, opake IDs) statt der vereinfachten
`set[int]`-Vertexmenge des Experiments.

Architekturprinzip (VIEWPORT_V02_ARCHITECTURE.md §4.7, §11):

    Eine Selection-/Hover-Änderung darf die Base-Geometrie NICHT anfassen.

Diese Klasse hält deshalb ausschließlich eine eigene Overlay-Ressource
(ein Highlight-Flag-Array pro Vertex, 1.0 = selektiert/hovered, 0.0 sonst)
und schreibt NIE in die `positions`/`normals`/`indices`-Ressourcen des
Base-Mesh. `RenderMesh._sync_selection()` patcht ausschließlich die
`highlight_flags`-Ressource.

Hinweis zur Option (VIEWPORT_V02_ARCHITECTURE.md §4.7, "Unresolved
Decisions"): Es wurde **Option A gewählt in vereinfachter Form** — statt
einer komplett separaten Overlay-Geometrie wird ein Highlight-Flag-Buffer
parallel zum Base-Mesh gehalten (kompatibel zum verifizierten Experiment-
Ansatz). Das erfüllt die Kern-Invariante (kein Base-Mesh-Rebuild bei
Selection) mit minimalem Zusatzaufwand. Eine echte separate Overlay-Mesh-
Geometrie (Kugeln an Vertices, Linien an Edges) bleibt für Gate 5b (Display-
Integration) offen, falls visuelle Anforderungen das nötig machen.

2026-09-26 (WP-06 B2b, AD-018 §7 Addendum): Für Vertex-Punkte ist die echte
separate Overlay-Geometrie jetzt umgesetzt. `point_layers()` liefert die
Weltpositionen (selektierte Vertices, gehoverter Vertex) rein headless;
gezeichnet werden sie von `gl_point_overlay.GLPointOverlay`. Der Face-Tint
über `highlight_flags` ist aus dem Shader entfernt (Artist REJECT); die
Flag-Ressource selbst bleibt bis zum dokumentierten Follow-up bestehen.
"""

from __future__ import annotations

from enum import Enum, auto

from core import EdgeId, FaceId, Selection, SelectionMode, VertexId

#: Punkt-Layer der Overlay-Geometrie, in Zeichenreihenfolge (Hover unter
#: der Selektion, wie Playground `window.on_draw`).
HOVER_LAYER = "hover"
SELECTED_LAYER = "selected"
POINT_LAYERS = (HOVER_LAYER, SELECTED_LAYER)


class OverlayElementKind(Enum):
    VERTEX = auto()
    EDGE = auto()
    FACE = auto()


class SelectionOverlay:
    """Hält Selection + Hover als reinen Overlay-Zustand.

    Kapselt keine eigene Selection-Logik (die liegt in `core.Selection`),
    sondern übersetzt deren Zustand in ein Highlight-Flag-Array für die
    GPU-Overlay-Ressource. Hover ist bewusst getrennt von Selektion
    (siehe `core.Selection.hovered`, kein Undo-Eintrag).
    """

    def __init__(self, selection: Selection) -> None:
        self.selection = selection
        # Cache des zuletzt gebauten Highlight-Arrays (Debug/Tests).
        self._last_highlight_flags: list[float] = []

    def build_highlight_flags(self, mesh) -> list[float]:
        """Erzeugt ein 1.0/0.0-Flag-Array über `mesh.all_vertex_ids()`
        (stabile Reihenfolge = Iterationsreihenfolge der Vertex-IDs, siehe
        RenderMesh._vertex_index für die zugehörige Buffer-Position).

        Im Vertex-Modus: selektierte Vertices direkt markiert.
        Im Edge-Modus: beide Endpunkte selektierter Edges markiert.
        Im Face-Modus: alle Vertices selektierter Faces markiert.
        Hover kommt zusätzlich (mit demselben Flag) oben drauf, unabhängig
        vom aktuellen Selection-Modus.
        """
        highlighted: set[VertexId] = set()

        mode = self.selection.mode
        if mode is SelectionMode.VERTEX:
            highlighted.update(self.selection.vertices)
        elif mode is SelectionMode.EDGE:
            for edge_id in self.selection.edges:
                va, vb = mesh.edge_vertices(edge_id)
                highlighted.add(va)
                highlighted.add(vb)
        elif mode is SelectionMode.FACE:
            for face_id in self.selection.faces:
                highlighted.update(mesh.face_vertices(face_id))

        hovered = self.selection.hovered
        if hovered is not None:
            highlighted.update(self._hovered_to_vertices(mesh, hovered))

        flags = [
            1.0 if vertex_id in highlighted else 0.0
            for vertex_id in mesh.all_vertex_ids()
        ]
        self._last_highlight_flags = flags
        return flags

    def _hovered_to_vertices(self, mesh, hovered) -> set[VertexId]:
        if isinstance(hovered, VertexId):
            return {hovered}
        if isinstance(hovered, EdgeId):
            va, vb = mesh.edge_vertices(hovered)
            return {va, vb}
        if isinstance(hovered, FaceId):
            return set(mesh.face_vertices(hovered))
        return set()

    # -- Punkt-Overlay (WP-06 B2b) --------------------------------------------

    def selected_vertex_positions(self, mesh) -> list[tuple[float, float, float]]:
        """Weltpositionen der selektierten Vertices — nur im Vertex-Modus.

        IDs, die in `mesh` nicht (mehr) existieren (z. B. nach einer
        Topology-Änderung), werden übersprungen. Reihenfolge: nach ID
        sortiert (deterministisch, IDs werden nie wiederverwendet)."""
        if self.selection.mode is not SelectionMode.VERTEX:
            return []
        return [
            mesh.vertex_position(vertex_id)
            for vertex_id in sorted(self.selection.vertices)
            if mesh.is_valid_vertex(vertex_id)
        ]

    def hovered_vertex_positions(self, mesh) -> list[tuple[float, float, float]]:
        """Weltposition des gehoverten Vertex (0 oder 1 Eintrag). Edge-/Face-
        Hover erzeugt hier keinen Punkt."""
        hovered = self.selection.hovered
        if isinstance(hovered, VertexId) and mesh.is_valid_vertex(hovered):
            return [mesh.vertex_position(hovered)]
        return []

    def point_layers(self, mesh) -> dict[str, list[tuple[float, float, float]]]:
        """Alle Punkt-Layer (`POINT_LAYERS`) mit ihren aktuellen Weltpositionen."""
        return {
            HOVER_LAYER: self.hovered_vertex_positions(mesh),
            SELECTED_LAYER: self.selected_vertex_positions(mesh),
        }
