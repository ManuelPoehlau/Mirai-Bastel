"""MoveOperation: konkrete Validierung des Interactive-Operation-Lifecycles.

Bezug: V1_SPEC.md §4, Architecture Decision AD-003.

Bewusst die erste und einzige V1-Operation, die den generischen Lifecycle
nutzt - Ziel ist der Nachweis, dass der Vertrag trägt, nicht Feature-
Vollständigkeit (Rotate/Scale folgen demselben Muster und werden hier
nicht dupliziert).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ids import VertexId
from ..mesh import Mesh, Position
from ..operation import Operation, OperationContext


def _add(p: Position, d: Position) -> Position:
    return tuple(a + b for a, b in zip(p, d))


@dataclass
class MoveVerticesCommand:
    """Reversibler History-Eintrag für eine abgeschlossene Verschiebung.

    Speichert bewusst Start- und Endpositionen (kein Delta), damit
    undo()/redo() unabhängig von Rundungsfehlern exakt reproduzierbar
    bleiben.
    """

    mesh: Mesh
    start_positions: dict[VertexId, Position]
    end_positions: dict[VertexId, Position]
    description: str = "Move Vertices"

    def undo(self) -> None:
        for vid, pos in self.start_positions.items():
            self.mesh.set_vertex_position(vid, pos)

    def redo(self) -> None:
        for vid, pos in self.end_positions.items():
            self.mesh.set_vertex_position(vid, pos)


class MoveOperation(Operation):
    """Verschiebt die selektierten Vertices um ein in update() übergebenes Delta.

    Soft-Selection-Falloff ist für V1 auf Gewicht 1.0 pro selektiertem
    Vertex vereinfacht (§2: Soft Selection ist unabhängiges Verhalten,
    kein eigener Mode) - die Struktur (`self._weights`) ist so angelegt,
    dass ein späteres Influence-Map-System hier andocken kann, ohne den
    Lifecycle selbst zu ändern.
    """

    def _on_begin(self, context: OperationContext) -> None:
        mesh: Mesh = context.target
        vertex_ids = set(context.selection.vertices)
        self._mesh = mesh
        self._vertex_ids = vertex_ids
        self._weights: dict[VertexId, float] = {vid: 1.0 for vid in vertex_ids}
        self._start_positions: dict[VertexId, Position] = {
            vid: mesh.vertex_position(vid) for vid in vertex_ids
        }

    def _on_update(self, delta: Position) -> None:
        """Verschiebt jedes selektierte Vertex um `delta` relativ zu seiner
        AKTUELLEN (Live-)Position, nicht relativ zur begin()-Snapshot-Position.
        update()-Semantik ist inkrementell (siehe operation.py) - mehrere
        update()-Aufrufe während eines Drags akkumulieren sich."""
        for vid in self._vertex_ids:
            weight = self._weights[vid]
            weighted_delta = tuple(d * weight for d in delta)
            current = self._mesh.vertex_position(vid)
            self._mesh.set_vertex_position(vid, _add(current, weighted_delta))

    def _on_commit(self) -> MoveVerticesCommand | None:
        end_positions = {vid: self._mesh.vertex_position(vid) for vid in self._vertex_ids}
        if end_positions == self._start_positions:
            return None
        return MoveVerticesCommand(
            mesh=self._mesh,
            start_positions=dict(self._start_positions),
            end_positions=end_positions,
        )

    def _on_cancel(self) -> None:
        for vid, pos in self._start_positions.items():
            self._mesh.set_vertex_position(vid, pos)
