"""Transform-Tools: gemeinsame Basis für RotateTool/ScaleTool.

Pfad (analog MoveTool, production):

    Command.Rotate / Command.Scale
        ↓
    RotateTool / ScaleTool  (dieses Paket)
        ↓
    RotateOperation / ScaleOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- Das Tool besitzt temporären Interaktionszustand (betroffene Vertex-IDs,
  feste Rotationsachse bzw. Scale-Achsenmaske, kumulierte Drag-Eingabe) und
  übersetzt Pointer-Deltas in semantische Transform-Schritte. Die
  persistente Domain-Mutation macht ausschließlich die Core-Operation —
  keine zweite Mutationslogik im Tool.
- Der Pivot (Selection Center = Zentroid, oder explizit über
  begin(vertex_ids=..., pivot=...)) wird von der Operation in begin() fix
  gesetzt und während der Interaktion nicht verschoben (V1_SPEC §4).

Produktions-Tools haben bewusst einen parameterlosen `__init__` (WP-04
Gate-4-Design): `scene`, `camera` und `vertex_ids` kommen über den
Interaktions-Kontext in `_on_begin(scene=..., camera=..., vertex_ids=...)`.
Konkrete Tools implementieren nur `_create_operation()` und ihre
Gesten-Interpretation (Update-Abbildung); die Snapshot-/Commit-/Cancel-
Maschinerie liegt hier.
"""

from __future__ import annotations

from typing import Any

from core import OperationContext, VertexId

from ..tool import Tool

_WORLD_AXES = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


class _VertexSelectionView:
    """Minimaler Selection-View für die Transform-Operationen.

    Die Core-Operationen benötigen für V1 lediglich die Menge der zu
    transformierenden Vertex-IDs (analog _MoveSelectionView in move.py).
    """

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = set(vertex_ids)


class TransformTool(Tool):
    """Gemeinsame Basis der interaktiven Rotate-/Scale-Tools.

    Lifecycle-Zustellung (ToolManager, unverändert):

        activate()  → Tool bereit (keine Interaktion)
        begin(scene=..., camera=..., vertex_ids=..., [pivot=...]) →
                    Operation.begin() mit fixem Pivot
        update(dx, dy, width, height)* → Operation.update(Schritt)
        commit()    → Operation.commit()  (genau eine History-Grenze)
        cancel()    → Operation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren
    """

    def __init__(self) -> None:
        super().__init__()
        self._scene = None
        self._camera = None
        self._operation = None
        self._vertex_ids: set[VertexId] = set()

    # -- Beobachtbarkeit für Tests/Integration -------------------------------

    @property
    def operation(self):
        return self._operation

    @property
    def vertex_ids(self) -> set[VertexId]:
        """Von dieser Interaktion betroffene Vertex-IDs (Live-Daten)."""
        return set(self._vertex_ids)

    # -- Hooks ------------------------------------------------------------------

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, **params: Any
    ) -> None:
        vertex_ids = set(vertex_ids or ())
        if not vertex_ids:
            raise ValueError("TransformTool.begin() benötigt mindestens einen Vertex.")
        self._scene = scene
        self._camera = camera
        self._vertex_ids = vertex_ids
        context = OperationContext(
            target=scene.mesh,
            selection=_VertexSelectionView(vertex_ids),
            history=scene.history,
            params={"pivot": params.get("pivot")},
        )
        operation = self._create_operation(context)
        operation.begin()
        self._operation = operation

    def _on_commit(self) -> Any:
        command = self._operation.commit()
        self._operation = None
        return command

    def _on_cancel(self) -> None:
        self._operation.cancel()
        self._operation = None

    def _on_deactivate(self) -> None:
        self._scene = None
        self._camera = None

    # -- Von konkreten Tools zu implementieren ------------------------------------

    def _create_operation(self, context: OperationContext):
        """Erzeugt die konkrete Core-Operation für diese Interaktion."""
        raise NotImplementedError


def selection_pivot(mesh, vertex_ids) -> tuple[float, float, float]:
    """Zentroid der betroffenen Vertices (Selection Pivot / Center, V1_SPEC §4)."""
    positions = [mesh.vertex_position(vid) for vid in vertex_ids]
    if not positions:
        raise ValueError("selection_pivot() benötigt mindestens einen Vertex.")
    count = len(positions)
    return (
        sum(p[0] for p in positions) / count,
        sum(p[1] for p in positions) / count,
        sum(p[2] for p in positions) / count,
    )