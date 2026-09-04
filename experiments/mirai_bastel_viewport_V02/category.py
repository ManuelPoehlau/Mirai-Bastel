"""Update-Kategorien und Dirty-State für das Viewport V0.2 Experiment.

Die zentrale Idee des Proofs:
    ``event -> state + dependencies -> incremental update``

Jede Änderung gehört genau einer Update-Kategorie an. Der Dirty-State hält
fest, welche Kategorien im aktuellen Frame verändert wurden (Interleaving!),
plus die Menge der modifizierten Vertex-IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --- Update-Kategorien -----------------------------------------------------
CAMERA = "camera"
GEOMETRY = "geometry"
SELECTION = "selection"
MATERIAL = "material"
TOPOLOGY = "topology"  # strukturelle Änderungen; darf Rebuild auslösen

ALL_CATEGORIES = (CAMERA, GEOMETRY, SELECTION, MATERIAL, TOPOLOGY)


@dataclass
class DirtyState:
    """Dirty-Flags pro Kategorie + Menge der modifizierten Vertices.

    Erlaubt Interleaving: mehrere Kategorien können im selben Frame aktiv sein.
    Die Referenz-Revision zählt, wie oft eine Kategorie seit einem Sync
    verändert wurde (für Instrumentierung und Test-Assertions).
    """

    camera: bool = False
    geometry: bool = False
    selection: bool = False
    material: bool = False
    topology: bool = False

    # Virtuelle Revision pro Kategorie (monoton wachsend, nur fürs Reporting).
    camera_rev: int = 0
    geometry_rev: int = 0
    selection_rev: int = 0
    material_rev: int = 0
    topology_rev: int = 0

    # Set der modifizierten Vertex-IDs (nur Geometrie). Wiederholte Änderungen
    # an derselben Vertex-ID werden dedupliziert.
    modified_vertices: set = field(default_factory=set)

    def reset(self) -> None:
        self.camera = False
        self.geometry = False
        self.selection = False
        self.material = False
        self.topology = False
        self.modified_vertices.clear()

    def is_any_geometry_work(self) -> bool:
        return self.geometry or self.topology

    def active_categories(self) -> list[str]:
        order = (CAMERA, SELECTION, MATERIAL, GEOMETRY, TOPLOGY)
        return [c for c in order if getattr(self, c)]
