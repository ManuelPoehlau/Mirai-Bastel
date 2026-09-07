"""Lab-Szene: mehrere Objekte mit jeweils EIGENER `src.core.Scene`.

Jedes Objekt besitzt eine eigene Core-Scene (eigenes Mesh/Selection/History)
und damit eine eigene Domain-Wahrheit. Die Render-Seite wird separat im
Viewport über `CoreRenderBinding` pro Objekt gehalten.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from src.core.scene import Scene  # noqa: E402


@dataclass
class LabObject:
    """Ein Testobjekt im Integration Lab (Cube oder Head-Basemesh)."""

    name: str
    scene: Scene
    asset_path: Optional[Path] = None
    base_color: tuple[float, float, float, float] = (0.62, 0.68, 0.75, 1.0)

    @property
    def mesh(self):
        return self.scene.mesh

    @property
    def is_head_asset(self) -> bool:
        return self.asset_path is not None


class LabScene:
    """Container mit Objekt-Auswahl; das aktive Objekt empfängt Interaktion."""

    def __init__(self) -> None:
        self.objects: list[LabObject] = []
        self.active_index = 0

    def add_object(self, obj: LabObject) -> None:
        self.objects.append(obj)

    def clear(self) -> None:
        self.objects.clear()
        self.active_index = 0

    @property
    def active(self) -> LabObject:
        if not self.objects:
            raise IndexError("LabScene enthält keine Objekte.")
        return self.objects[self.active_index]

    def select(self, index: int) -> LabObject:
        """Aktiviert Objekt `index` (unabhängig von der Render-Seite)."""
        self.active_index = index % len(self.objects)
        return self.active

    def select_by_name(self, name: str) -> LabObject:
        for i, obj in enumerate(self.objects):
            if obj.name == name:
                return self.select(i)
        raise KeyError(f"Objekt {name!r} existiert nicht.")

    def names(self) -> list[str]:
        return [obj.name for obj in self.objects]