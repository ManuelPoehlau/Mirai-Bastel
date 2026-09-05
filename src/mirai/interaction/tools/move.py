"""MoveTool: Referenz-Tool der Produktions-Application.

Pfad:

    Command.Move
        ↓
    MoveTool
        ↓
    Core-MoveOperation (src/core)
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- MoveTool besitzt temporären Interaktionszustand (Anchor-Vertex, laufende
  MoveOperation, Menge der betroffenen Vertex-IDs).
- Die eigentliche persistente Domain-Mutation macht die bestehende
  `MoveOperation` aus `src.core` — es wird bewusst KEINE zweite
  Move-Mutationslogik gebaut.
- Selection ist kein Tool: Sie bleibt Core-Domain-State. Die Auflösung
  Selection → betroffene Vertex-IDs übernimmt die reine Hilfsfunktion
  `resolve_selection_vertices()`.

Produktions-Design (WP-04): parameterloser `__init__`; `scene`, `camera`
und `vertex_ids` kommen über den Interaktions-Kontext in
`_on_begin(scene=..., camera=..., vertex_ids=...)` (Pattern A/B).

Bewusst pyglet-frei und ohne physische Key-/Button-Konstanten: Pointer-
Bewegung wird als semantisches Pixel-Delta übergeben und erst hier mit der
Kamera-Hilfsfunktion in ein Welt-Delta übersetzt.
"""

from __future__ import annotations

from typing import Any

from core import (
    Mesh,
    MoveOperation,
    OperationContext,
    Selection,
    SelectionMode,
    VertexId,
)

from ..tool import Tool


class _MoveSelectionView:
    """Minimaler Selection-View für die Core-MoveOperation.

    Die Core-Operation benötigt für V1 lediglich die Menge der tatsächlich
    zu bewegenden Vertex-IDs; die sichtbare UI-Selection bleibt unberührt.
    """

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = set(vertex_ids)


def resolve_selection_vertices(
    mesh: Mesh, selection: Selection, mode: SelectionMode
) -> set[VertexId]:
    """Löst die aktuelle Sub-Object-Selection auf betroffene Vertex-IDs auf.

    Vertex-Mode → selektierte Vertices
    Edge-Mode   → Endpunkt-Vertices aller selektierten Edges
    Face-Mode   → Boundary-Vertices aller selektierten Faces

    Bei mehreren Edges/Faces ist das Ergebnis die Vereinigungsmenge — ein
    gemeinsamer Vertex wird nur einmal bewegt.
    """
    if mode == SelectionMode.VERTEX:
        return set(selection.vertices)
    if mode == SelectionMode.EDGE:
        result: set[VertexId] = set()
        for eid in selection.edges:
            result.update(mesh.edge_vertices(eid))
        return result
    if mode == SelectionMode.FACE:
        result = set()
        for fid in selection.faces:
            result.update(mesh.face_vertices(fid))
        return result
    return set()


class MoveTool(Tool):
    """Modal-interaktives Move-Tool auf Basis der bestehenden MoveOperation.

    Lifecycle-Zustellung (ToolManager):

        activate()  → Tool bereit (keine Interaktion)
        begin(scene=..., camera=..., vertex_ids=...) → MoveOperation.begin()
        update(dx, dy, width, height)* → MoveOperation.update(delta=…)
        commit()    → MoveOperation.commit()  (genau eine History-Grenze)
        cancel()    → MoveOperation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren
    """

    def __init__(self) -> None:
        super().__init__()
        self._scene = None
        self._camera = None
        self._operation: MoveOperation | None = None
        self._vertex_ids: set[VertexId] = set()
        self._anchor_vertex: VertexId | None = None

    # -- Beobachtbarkeit für Tests/Integration ------------------------------

    @property
    def operation(self) -> MoveOperation | None:
        return self._operation

    @property
    def moves(self) -> set[VertexId]:
        """Von dieser Interaktion betroffene Vertex-IDs (Live-Daten)."""
        return set(self._vertex_ids)

    # -- Hooks -----------------------------------------------------------------

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, **params: Any
    ) -> None:
        vertex_ids = set(vertex_ids or ())
        if not vertex_ids:
            raise ValueError("MoveTool.begin() benötigt mindestens einen Vertex.")
        self._scene = scene
        self._camera = camera
        self._vertex_ids = vertex_ids
        self._anchor_vertex = min(vertex_ids)
        context = OperationContext(
            target=self._scene.mesh,
            selection=_MoveSelectionView(vertex_ids),
            history=self._scene.history,
        )
        operation = MoveOperation(context)
        operation.begin()
        self._operation = operation

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        # Anchor ist ein Referenz-Punkt der bewegten Auswahl: Das Pixel-Delta
        # wird auf der Bildebene der Kamera durch diesen Punkt in ein Welt-Delta
        # übersetzt.
        anchor_pos = self._scene.mesh.vertex_position(self._anchor_vertex)
        world_delta = self._camera.screen_delta_to_world(
            anchor_pos, dx, dy, width, height
        )
        self._operation.update(delta=world_delta)

    def _on_commit(self) -> Any:
        command = self._operation.commit()
        self._operation = None
        return command

    def _on_cancel(self) -> None:
        self._operation.cancel()
        self._operation = None

    def _on_deactivate(self) -> None:
        self._anchor_vertex = None
        self._scene = None
        self._camera = None