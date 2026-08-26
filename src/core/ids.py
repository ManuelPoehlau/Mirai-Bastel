"""Stabile, opake Element-IDs.

Bezug: V1_SPEC.md §8, Architecture Decision AD-001.

Architekturvertrag (bewusst klein gehalten):

- Eine ID ist ein opakes Handle. Sie darf NIE als Array-/Speicher-Index
  interpretiert werden, auch wenn sie intern ein int ist.
- IDs werden innerhalb einer Session NIEMALS wiederverwendet
  (monotoner Counter, kein Recycling, kein Slotmap/ECS - siehe AD-001).
- Gültigkeit einer ID wird ausschließlich über die jeweilige Element-Tabelle
  im Mesh geprüft (`mesh.is_valid_vertex(id)` etc.), nicht über die ID
  selbst.
- IDs werden 1:1 serialisiert (siehe serialization.py).

Diese Datei bewusst NICHT enthalten: Generational Slotmap, Recycling-Pool,
Arena-Allocator. Das wären mögliche spätere Performance-Optimierungen,
keine V1-Anforderung.
"""

from __future__ import annotations


class ElementId(int):
    """Basisklasse für opake Element-IDs.

    Erbt von int nur aus Bequemlichkeit (Hashing, Vergleich, einfache
    Serialisierung als Zahl) - wird bewusst nicht arithmetisch verwendet.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - reine Debug-Hilfe
        return f"{self.__class__.__name__}({int(self)})"


class VertexId(ElementId):
    __slots__ = ()


class EdgeId(ElementId):
    __slots__ = ()


class FaceId(ElementId):
    __slots__ = ()


class IdAllocator:
    """Monotoner Counter-Allocator für einen einzelnen Element-Typ.

    Kein Recycling: Sobald eine ID vergeben wurde, wird sie nie wieder
    ausgegeben - auch nicht nach dem Löschen des zugehörigen Elements.
    """

    def __init__(self, id_type: type[ElementId], start: int = 0) -> None:
        self._id_type = id_type
        self._next = start

    def allocate(self) -> ElementId:
        new_id = self._id_type(self._next)
        self._next += 1
        return new_id

    def peek_next(self) -> int:
        """Nächster zu vergebender Rohwert - wird für Serialisierung benötigt."""
        return self._next

    def restore_counter(self, value: int) -> None:
        """Für Deserialisierung: Counter darf nur vorwärts gesetzt werden,
        damit künftig erzeugte IDs nicht mit geladenen IDs kollidieren.
        """
        if value > self._next:
            self._next = value
