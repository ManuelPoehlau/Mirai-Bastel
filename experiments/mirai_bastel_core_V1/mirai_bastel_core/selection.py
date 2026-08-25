"""Selection: eigenständiger Domain-State, unabhängig von Mesh-Mutation.

Bezug: V1_SPEC.md §2 (Selection Modes), §3 (Selection).

Architekturvertrag:

- Selection kennt nur stabile IDs, keine Mesh-Internals.
- Selection ist NICHT Teil des Modeling-History-Stacks (§3: "Ein Klick
  soll keinen Modeling-Undo-Schritt verbrauchen"). Deshalb hat diese
  Klasse absichtlich keine Verbindung zu HistoryStack.
- Die Benennung ist bewusst nicht mesh-spezifisch verankert (§15 Punkt 6):
  `SelectionMode` ist generisch gehalten, auch wenn V1 nur V/E/F/OBJECT
  kennt. Ein späteres BoneSelection- oder KeyframeSelection-System kann
  strukturell demselben Muster folgen, ohne dass diese Klasse geändert
  werden muss.
"""

from __future__ import annotations

from enum import Enum, auto

from .ids import VertexId, EdgeId, FaceId


class SelectionMode(Enum):
    VERTEX = auto()
    EDGE = auto()
    FACE = auto()
    OBJECT = auto()


class Selection:
    def __init__(self) -> None:
        self.mode: SelectionMode = SelectionMode.VERTEX
        self.vertices: set[VertexId] = set()
        self.edges: set[EdgeId] = set()
        self.faces: set[FaceId] = set()
        # Hover ist explizit getrennt von "Selektion" - reiner
        # UI-Zustand, nicht Teil der eigentlichen Auswahl (§3).
        self.hovered: VertexId | EdgeId | FaceId | None = None

    def _active_set(self) -> set:
        return {
            SelectionMode.VERTEX: self.vertices,
            SelectionMode.EDGE: self.edges,
            SelectionMode.FACE: self.faces,
        }.get(self.mode, set())

    def set(self, ids: set) -> None:
        """Ersetzt die aktuelle Auswahl im aktiven Selection Mode (Single/Multi Select)."""
        self._active_set().clear()
        self._active_set().update(ids)

    def add(self, ids: set) -> None:
        self._active_set().update(ids)

    def remove(self, ids: set) -> None:
        self._active_set().difference_update(ids)

    def toggle(self, id_) -> None:
        target = self._active_set()
        if id_ in target:
            target.discard(id_)
        else:
            target.add(id_)

    def clear(self) -> None:
        self.vertices.clear()
        self.edges.clear()
        self.faces.clear()

    def is_empty(self) -> bool:
        return not (self.vertices or self.edges or self.faces)
