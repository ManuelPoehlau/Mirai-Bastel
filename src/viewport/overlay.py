"""Selection-/Hover-Overlay für den Viewport v0.2.

Adaptiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/selection.py`) auf die reale
`src.core.Selection`-API (V/E/F-Modi, opake IDs) statt der vereinfachten
`set[int]`-Vertexmenge des Experiments.

Architekturprinzip (VIEWPORT_V02_ARCHITECTURE.md §4.7, §11):

    Eine Selection-/Hover-Änderung darf die Base-Geometrie NICHT anfassen.

Diese Klasse liefert deshalb nur Overlay-Geometrie (Punkte, Segmente, Dreiecke,
unten) und schreibt NIE in die `positions`/`normals`/`indices`-Ressourcen des
Base-Mesh. Das frühere Highlight-Flag-Array pro Vertex (`build_highlight_flags`,
die `highlight_flags`-Ressource des `RenderMesh`) las der Shader seit dem Wegfall
des Face-Tints (2026-09-26) nicht mehr; entfernt 2026-11-11 (Audit
`ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md` §I.3), eine Auswahl-Änderung lädt
seitdem nichts mehr in den Mesh-Buffer.

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
Flag-Ressource folgte im Follow-up 2026-11-11.

2026-09-27 (WP-06 B5b, E44): dasselbe für Edges und Faces. `line_layers()`
liefert Segmente (selektierte Edges im Edge-Modus, gehoverte Edge),
`face_layers()` Dreiecke (selektierte Faces im Face-Modus, gehoverte Face;
gleiche Fan-Triangulierung wie `RenderMesh`). Gezeichnet von
`gl_line_overlay.GLLineOverlay` bzw. `gl_triangle_overlay.GLTriangleOverlay`.

2026-09-28 (WP-06 B6 fix): `build_highlight_flags()` (seit 2026-11-11 entfernt) übersprang
ungültige IDs genauso wie die Punkt-/Linien-/Face-Methoden oben. Ursache: eine
Topologie-Mutation (Split/Connect, Undo/Redo, Szenenwechsel) kann die
gehoverte/selektierte ID aus dem Mesh entfernen; `mesh.edge_vertices()` /
`mesh.face_vertices()` werfen dann `KeyError`, und weil der Aufruf mitten im
Draw-Pfad liegt (`_sync_topology` → `_rebuild_resources`), crasht das den
Zeichen-Loop. Der Viewport ist passiv und kann die Zustands-Invarianten der
Application nicht kennen — er überspringt stale IDs, statt zu werfen (AD-001:
eine ungültige ID ist über `mesh.is_valid_*()` erkennbar).
"""

from __future__ import annotations

from enum import Enum, auto

from core import EdgeId, FaceId, Selection, SelectionMode, VertexId

from .derived import triangulate_mesh_face

#: Punkt-Layer der Overlay-Geometrie, in Zeichenreihenfolge (Hover unter
#: der Selektion, wie Playground `window.on_draw`).
HOVER_LAYER = "hover"
SELECTED_LAYER = "selected"
POINT_LAYERS = (HOVER_LAYER, SELECTED_LAYER)

#: Tool-Layer (WP-06 B7): Overlay-Geometrie einer laufenden modalen Tool-
#: Session (derzeit nur Knife), unabhängig von `Selection`. Kein eigener
#: Look: `tool_preview` zeichnet im Hover-Stil (prospektiver Punkt, gehoverte
#: bzw. gelockte Edge, Linien-Preview), `tool_active` im Selected-Stil
#: (Start-Vertex, bisherige Pfad-Edges). Die Positionen kommen fertig vom
#: Aufrufer (`Viewport.set_tool_overlay`); diese Klasse berechnet sie nicht.
TOOL_PREVIEW_LAYER = "tool_preview"
TOOL_ACTIVE_LAYER = "tool_active"

#: Zusatz-Layer des symmetrischen Knife (AD-SYM-03 §10, Slice 6c; PROVISIONAL bis zum Artist-Verdikt).
#: Der Viewport kennt kein Knife und keine Symmetrie: er bekommt auch hier fertige Weltpositionen und
#: zeichnet pro Layer nur Farbe und Tiefenverhalten (`gl_point_overlay` / `gl_line_overlay`).
#: - `tool_mirror` / `tool_mirror_preview`: die Spiegelseite wie die Arbeitsseite gezeichnet (Pfad-Linien
#:   mit Depth-Test, Preview ohne; Variante V-a, bei V-c nur die Punkte);
#: - `tool_mirror_dim`: die Spiegelseite immer sichtbar (ohne Depth-Test) und gedimmt (Variante V-b);
#: - `tool_clipped`: der Teil, der nicht geschnitten wird (neutrales Grau);
#: - `tool_refused`: das Hover-Ziel, das ein Klick ablehnt (Sperrfarbe).
#: Nur die Application füllt sie; ohne Symmetrie bleiben sie leer.
TOOL_MIRROR_LAYER = "tool_mirror"
TOOL_MIRROR_PREVIEW_LAYER = "tool_mirror_preview"
TOOL_MIRROR_DIM_LAYER = "tool_mirror_dim"
TOOL_CLIPPED_LAYER = "tool_clipped"
TOOL_REFUSED_LAYER = "tool_refused"
TOOL_SYMMETRY_LAYERS = (
    TOOL_CLIPPED_LAYER,
    TOOL_MIRROR_LAYER,
    TOOL_MIRROR_DIM_LAYER,
    TOOL_MIRROR_PREVIEW_LAYER,
    TOOL_REFUSED_LAYER,
)
#: Zeichenreihenfolge der Tool-Layer (später = oben): der bisherige Preview-/Active-Stand zuerst.
TOOL_LAYERS = (TOOL_PREVIEW_LAYER, TOOL_ACTIVE_LAYER) + TOOL_SYMMETRY_LAYERS


class OverlayElementKind(Enum):
    VERTEX = auto()
    EDGE = auto()
    FACE = auto()


class SelectionOverlay:
    """Hält Selection + Hover als reinen Overlay-Zustand.

    Kapselt keine eigene Selection-Logik (die liegt in `core.Selection`),
    sondern übersetzt deren Zustand in Punkte, Segmente und Dreiecke für die
    Overlays (`point_layers`, `line_layers`, `face_layers`). Hover ist bewusst getrennt von Selektion
    (siehe `core.Selection.hovered`, kein Undo-Eintrag).
    """

    def __init__(self, selection: Selection) -> None:
        self.selection = selection

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

    # -- Edge-/Face-Overlay (WP-06 B5b) ---------------------------------------

    def line_layers(self, mesh) -> dict[str, list]:
        """Segment-Layer (`POINT_LAYERS`-Namen): je Edge ein `(a, b)`-Paar von
        Weltpositionen. Selektierte Edges nur im Edge-Modus; ungültige IDs
        werden übersprungen, Reihenfolge nach ID."""
        selected: list = []
        if self.selection.mode is SelectionMode.EDGE:
            selected = [
                _edge_segment(mesh, edge_id)
                for edge_id in sorted(self.selection.edges)
                if mesh.is_valid_edge(edge_id)
            ]
        hovered = self.selection.hovered
        hover: list = []
        if isinstance(hovered, EdgeId) and mesh.is_valid_edge(hovered):
            hover = [_edge_segment(mesh, hovered)]
        return {HOVER_LAYER: hover, SELECTED_LAYER: selected}

    def face_layers(self, mesh) -> dict[str, list]:
        """Dreieck-Layer (`POINT_LAYERS`-Namen): je Dreieck drei Weltpositionen.
        Selektierte Faces nur im Face-Modus; ungültige IDs werden
        übersprungen, Reihenfolge nach ID."""
        selected: list = []
        if self.selection.mode is SelectionMode.FACE:
            for face_id in sorted(self.selection.faces):
                if mesh.is_valid_face(face_id):
                    selected.extend(_face_triangles(mesh, face_id))
        hovered = self.selection.hovered
        hover: list = []
        if isinstance(hovered, FaceId) and mesh.is_valid_face(hovered):
            hover = _face_triangles(mesh, hovered)
        return {HOVER_LAYER: hover, SELECTED_LAYER: selected}


def _edge_segment(mesh, edge_id: EdgeId) -> tuple:
    va, vb = mesh.edge_vertices(edge_id)
    return (mesh.vertex_position(va), mesh.vertex_position(vb))


def _face_triangles(mesh, face_id: FaceId) -> list[tuple]:
    return [
        tuple(mesh.vertex_position(vid) for vid in tri)
        for tri in triangulate_mesh_face(mesh, face_id)
    ]
