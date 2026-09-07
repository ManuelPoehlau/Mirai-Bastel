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
"""

from __future__ import annotations

from enum import Enum, auto

from core import EdgeId, FaceId, Selection, SelectionMode, VertexId


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
