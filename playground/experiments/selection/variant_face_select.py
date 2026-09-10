"""AP-03 Phase 1 — Face Select (Replace-Modus, Baseline).

LMB-Click wählt die getroffene Face aus (Replace). Miss leert die Selektion.
Kein Add/Remove/Toggle — explizit `SelectMode.REPLACE`.
"""

from playground.experiment import Experiment
from playground.selector import SelectMode


class FaceSelectExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Face Select (Replace)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.select_mode = SelectMode.REPLACE

    def deactivate(self) -> None:
        pass
