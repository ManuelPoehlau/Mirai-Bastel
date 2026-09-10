"""Update-Kategorien und Dirty-State für den Viewport v0.2.

Portiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/category.py`, 10/10 Tests bestanden).

Zentrale Idee (siehe VIEWPORT_V02_ARCHITECTURE.md §3, §6):

    event -> Update-Kategorie -> inkrementelles Update

Jede Änderung gehört genau einer Update-Kategorie an. Der Dirty-State hält
fest, welche Kategorien seit dem letzten `sync()` verändert wurden
(Interleaving mehrerer Kategorien im selben Frame ist erlaubt), plus die
Menge der modifizierten Vertex-IDs für Geometrie-Änderungen.

Abweichung vom Experiment: `active_categories()` enthielt dort einen Tippfehler
(`TOPLOGY` statt `TOPOLOGY`), der bei Aufruf einen NameError ausgelöst hätte.
Hier korrigiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core import VertexId

# --- Update-Kategorien -------------------------------------------------
CAMERA = "camera"
GEOMETRY = "geometry"
SELECTION = "selection"
MATERIAL = "material"
TOPOLOGY = "topology"  # strukturelle Änderungen; erlaubt Structural Rebuild

ALL_CATEGORIES = (CAMERA, GEOMETRY, SELECTION, MATERIAL, TOPOLOGY)


@dataclass
class DirtyState:
    """Dirty-Flags pro Kategorie + Menge der modifizierten Vertices.

    Erlaubt Interleaving: mehrere Kategorien können im selben Frame aktiv
    sein (z. B. Camera-Orbit während eines Vertex-Drags). Die Revision pro
    Kategorie zählt monoton, wie oft sie seit App-Start verändert wurde
    (fürs Reporting/Benchmarking, siehe `benchmark.py`).
    """

    camera: bool = False
    geometry: bool = False
    selection: bool = False
    material: bool = False
    topology: bool = False

    camera_rev: int = 0
    geometry_rev: int = 0
    selection_rev: int = 0
    material_rev: int = 0
    topology_rev: int = 0

    # Nur Geometrie: modifizierte Vertex-IDs seit letztem sync().
    # Wiederholte Änderungen an derselben Vertex-ID werden dedupliziert.
    modified_vertices: set[VertexId] = field(default_factory=set)

    def reset(self) -> None:
        """Setzt alle Flags + die modifizierten Vertices zurück (nach sync())."""
        self.camera = False
        self.geometry = False
        self.selection = False
        self.material = False
        self.topology = False
        self.modified_vertices.clear()

    def is_any_geometry_work(self) -> bool:
        return self.geometry or self.topology

    def active_categories(self) -> list[str]:
        order = (CAMERA, SELECTION, MATERIAL, GEOMETRY, TOPOLOGY)
        return [c for c in order if getattr(self, c)]
