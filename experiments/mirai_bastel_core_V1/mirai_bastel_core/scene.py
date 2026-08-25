"""Scene: Wurzel-Objekt, das Mesh in den größeren Systemkontext einbettet.

Bezug: V1_SPEC.md §0, §12, §15 Punkt 7.

Architekturvertrag:

- Scene behandelt Mesh NICHT als das gesamte System, sondern als eines
  von mehreren möglichen Kind-Subsystemen. `morph_targets`, `rig` und
  `animation` sind für V1 bewusst `None` - keine Implementierung, aber
  ein fester Platz in der Struktur (§12), damit spätere Subsysteme
  ergänzt statt das Format umgebaut werden muss.
- History und Selection leben auf Scene-Ebene, nicht im Mesh selbst -
  das entspricht §15 Punkt 5/6 (History/Selection nicht mesh-spezifisch
  verankern).
"""

from __future__ import annotations

from .history import HistoryStack
from .mesh import Mesh
from .selection import Selection


class Scene:
    def __init__(self) -> None:
        self.mesh: Mesh = Mesh()
        self.selection: Selection = Selection()
        self.history: HistoryStack = HistoryStack()

        # Bewusst None in V1 - siehe §12/§16. Reservierte Plätze, keine
        # Implementierung.
        self.morph_targets = None
        self.rig = None
        self.animation = None
