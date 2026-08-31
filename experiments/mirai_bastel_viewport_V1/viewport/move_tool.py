"""MoveTool: Referenz-Tool für WP-02 (Interaction & Tool Framework).

Pfad (WP-02 §1 / §4.3):

    Command.Move
        ↓
    MoveTool
        ↓
    bestehende Core-MoveOperation
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- MoveTool besitzt temporären Interaktionszustand (Anchor-Vertex, laufende
  MoveOperation, Menge der betroffenen Vertex-IDs).
- Die eigentliche persistente Domain-Mutation macht die bestehende
  `MoveOperation` aus `mirai_bastel_core` — es wird bewusst KEINE zweite
  Move-Mutationslogik gebaut (WP-02 §4.4).
- Selection ist kein Tool: Sie bleibt Core-Domain-State. Die Auflösung
  Selection → betroffene Vertex-IDs übernimmt die reine Hilfsfunktion
  `resolve_selection_vertices()` (WP-02 §4.6).

Bewusst pyglet-frei und ohne physische Key-/Button-Konstanten (WP-02 §4.5):
Pointer-Bewegung wird als semantisches Pixel-Delta übergeben und erst hier
mit der Kamera-Hilfsfunktion in ein Welt-Delta übersetzt.
"""

from __future__ import annotations

from typing import Any

from mirai_bastel_core import (
    Mesh,
    MoveOperation,
    OperationContext,
    Selection,
    SelectionMode,
    VertexId,
)

from . import commands as cmd
from .camera import OrbitCamera
from .tool import Tool
from .transform_tool import RotateTool, ScaleTool


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
    gemeinsamer Vertex wird nur einmal bewegt (WP-02 §4.6, SELECTION_MODES).
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

    Lifecycle-Zustellung (Tool-Manager):

        activate()  → Tool bereit (keine Interaktion)
        begin(vertex_ids=...) → MoveOperation.begin()
        update(dx,dy,width,height)* → MoveOperation.update(delta=…)
        commit()    → MoveOperation.commit()  (genau eine History-Grenze)
        cancel()    → MoveOperation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren
    """

    def __init__(self, scene, camera: OrbitCamera) -> None:
        super().__init__()
        self._scene = scene
        self._camera = camera
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

    # -- Hooks ---------------------------------------------------------------

    def _on_begin(self, vertex_ids: set[VertexId], **params: Any) -> None:
        vertex_ids = set(vertex_ids)
        if not vertex_ids:
            raise ValueError("MoveTool.begin() benötigt mindestens einen Vertex.")
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
        # übersetzt (bestehende Verhaltens-/Kamera-Semantik, keine Constraints).
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


def tool_for_command(command: str) -> type[Tool] | None:
    """Command → Tool-Routing (WP-02 §4.3, testbar und window-unabhängig).

    Nur modale/interaktive Commands brauchen ein Tool. Nicht-interaktive
    Commands (Undo, Display, ...) bleiben weiterhin direkte Aktionen.

    WP-03: Die Transform-Commands Rotate/Scale werden auf die gemeinsame
    TransformTool-Basis geroutet (transform_tool.py) und nutzen dieselben
    Lifecycle-/History-Verträge wie das MoveTool.

    Eine geänderte Input-Bindung (z. B. G statt M → Move) ändert ausschließlich
    die Mapping-Schicht — diese Funktion und die Tools bleiben unverändert.
    """
    if command == cmd.MOVE:
        return MoveTool
    if command == cmd.ROTATE:
        return RotateTool
    if command == cmd.SCALE:
        return ScaleTool
    return None