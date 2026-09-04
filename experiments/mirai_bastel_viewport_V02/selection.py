"""Selection-Zustand und Overlay-Highlight für das V0.2 Experiment.

Selection ist vom Base-Mesh getrennt. Eine Selection-Änderung darf die
Base-Geometrie NICHT neu aufbauen — sie aktualisiert nur eine eigene
Highlight-Ressource (ein Set selektierter Vertex-IDs plus ein dazu
gehörender Overlay-Buffer im RenderMesh).

Hier wird bewusst kein allgemeines Production-Selection-System gebaut,
sondern der minimale Zustand, der die Hypothese sauber testet:
    selection change -> nur highlight-Ressource anfassen
"""
from __future__ import annotations

from typing import Iterable


class SelectionState:
    def __init__(self) -> None:
        self.selected_vertices: set[int] = set()

    def set(self, vertices: Iterable[int]) -> None:
        self.selected_vertices = set(int(v) for v in vertices)

    def add(self, vid: int) -> None:
        self.selected_vertices.add(int(vid))

    def clear(self) -> None:
        self.selected_vertices.clear()

    def toggle(self, vid: int) -> bool:
        """Fügt hinzu/entfernt; gibt True zurück, wenn sich etwas änderte."""
        if vid in self.selected_vertices:
            self.selected_vertices.discard(vid)
            return True
        self.selected_vertices.add(vid)
        return True

    def is_selected(self, vid: int) -> bool:
        return vid in self.selected_vertices

    def build_highlight_flags(self, n_vertices: int) -> list[float]:
        """Erzeugt ein 1.0/0.0-Flag-Array (Overlay), getrennt vom Base-Mesh."""
        return [1.0 if v in self.selected_vertices else 0.0 for v in range(n_vertices)]
